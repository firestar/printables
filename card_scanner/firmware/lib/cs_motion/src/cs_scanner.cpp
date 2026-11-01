#include "cs_scanner.h"

#include <math.h>
#include <string.h>

namespace cs {

namespace {

const float BACKOFF_MM = 3.0f;      // move off a home switch before seeking it
const float HOME_EXTRA_MM = 20.0f;  // seek this far past the nominal travel
const uint32_t DEBOUNCE_MS = 20;    // estop / lid / magazine_low event inputs
const uint32_t SETTLE_MS = 1000;    // a hard-stopped axis must report idle within this

// Homing order: tongue first (it reaches into the sleeve), then pick arm, then elevator.
const Axis HOME_ORDER[] = {AX_TONGUE, AX_PICK, AX_ELEV};
const int HOME_AXES = 3;

enum Phase : uint8_t {
  P_NONE,
  P_HOME_SERVOS, P_HOME_BACKOFF, P_HOME_SEEK, P_HOME_SETTLE,
  P_FEED_RAISE, P_FEED_PUFF, P_FEED_GRIP, P_FEED_PICK, P_FEED_RUN,
  P_SLV_PICK, P_SLV_PICK_PUSH, P_SLV_PLATEN, P_SLV_LIFT_DOWN, P_SLV_LIFT_GRIP, P_SLV_LIFT_UP, P_SLV_JET,
  P_SLV_TONGUE_IN, P_SLV_FEED, P_SLV_SEAT, P_SLV_TONGUE_OUT, P_SLV_RELEASE,
  P_SORT_DIVERT, P_REJ_FEED, P_SORT_PUSH, P_SORT_CLEAR, P_SORT_RETURN,
};

Sensor homeSwitch(Axis a) {
  switch (a) {
    case AX_TONGUE: return SN_TONGUE_HOME;
    case AX_PICK: return SN_PICK_HOME;
    default: return SN_ELEV_HOME;
  }
}

uint8_t deg(float v) { return (uint8_t)(v < 0 ? 0 : v > 180 ? 180 : lroundf(v)); }

}  // namespace

const char *axisName(Axis a) {
  switch (a) {
    case AX_ELEV: return "elevator";
    case AX_PICK: return "pick";
    case AX_FEED: return "feed";
    case AX_TONGUE: return "tongue";
    default: return "?";
  }
}

const char *sensorName(Sensor s) {
  static const char *const N[SN_COUNT] = {
      "stack_top", "double_feed", "scan_stop", "sleeve_mouth", "sleeve_present", "exit",     "elev_home",
      "elev_limit", "pick_home",   "tongue_home", "mag_low",   "mag_empty",      "estop",    "lid_open"};
  return s < SN_COUNT ? N[s] : "?";
}

const char *stateName(State s) {
  switch (s) {
    case ST_UNHOMED: return "unhomed";
    case ST_IDLE: return "idle";
    case ST_HOMING: return "homing";
    case ST_FEEDING: return "feeding";
    case ST_SLEEVING: return "sleeving";
    case ST_SORTING: return "sorting";
    case ST_EJECTING: return "ejecting";
    case ST_ESTOP: return "estop";
  }
  return "?";
}

Scanner::Scanner(Hal &hal, LineSink &out, SettingsStore *store, const char *fwVersion)
    : hal_(hal), out_(out), store_(store), fw_(fwVersion) {}

void Scanner::begin() {
  if (store_) {
    for (int i = 0; i < settingCount(); i++) {
      const SettingDef &d = settingAt(i);
      float v;
      if (store_->load(d.key, v) && v >= d.lo && v <= d.hi) s_.*d.field = v;
    }
  }
  applyCurrents();
  pneumaticsOff();
  hal_.lights(0, 0);
  hal_.servo(SV_LIFT, deg(s_.lift_up_deg));
  hal_.servo(SV_PUSHER, deg(s_.pusher_rest_deg));
  hal_.servo(SV_DIVERTER, deg(s_.div0_deg));

  uint32_t now = hal_.millis();
  estopIn_.raw = estopIn_.stable = hal_.sensor(SN_ESTOP);
  lidIn_.raw = lidIn_.stable = hal_.sensor(SN_LID_OPEN);
  magLowIn_.raw = magLowIn_.stable = hal_.sensor(SN_MAG_LOW);
  estopIn_.since = lidIn_.since = magLowIn_.since = now;
  if (estopIn_.stable || lidIn_.stable) {
    enterEstop(estopIn_.stable ? "input" : "lid", estopIn_.stable);
    if (lidIn_.stable) event("lid_open");
  } else {
    hal_.enableMotors(true);
  }
}

State Scanner::state() const {
  if (estop_) return ST_ESTOP;
  switch (job_) {
    case JOB_HOME: return ST_HOMING;
    case JOB_FEED: return ST_FEEDING;
    case JOB_SLEEVE: return ST_SLEEVING;
    case JOB_SORT: return ST_SORTING;
    case JOB_REJECT: return ST_EJECTING;
    case JOB_NONE: break;
  }
  return homed_ ? ST_IDLE : ST_UNHOMED;
}

// ---- output ---------------------------------------------------------------------

void Scanner::send(JsonWriter &w) { out_.sendLine(w.c_str()); }

void Scanner::replyOk(int32_t id) {
  char buf[64];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", id).boolean("ok", true).close();
  send(w);
}

void Scanner::replyErr(int32_t id, Err e, const char *msg) {
  char buf[192];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", id).boolean("ok", false).str("err", errName(e)).str("msg", msg).close();
  send(w);
}

void Scanner::event(const char *name, const char *key, const char *val) {
  char buf[96];
  JsonWriter w(buf, sizeof(buf));
  w.open().str("evt", name);
  if (key) w.str(key, val);
  w.close();
  send(w);
}

// ---- command dispatch -----------------------------------------------------------

void Scanner::handleLine(const char *line) {
  const char *p = line;
  while (*p == ' ' || *p == '\t' || *p == '\r') p++;
  if (!*p) return;  // blank line

  JsonObject req;
  if (!req.parse(line)) {
    replyErr(-1, ERR_BAD_CMD, "malformed json");
    return;
  }
  int32_t id;
  if (!req.getInt("id", id)) {
    replyErr(-1, ERR_BAD_CMD, "missing integer id");
    return;
  }
  const char *cmd = req.getStr("cmd");
  if (!cmd) {
    replyErr(id, ERR_BAD_CMD, "missing cmd");
    return;
  }

  if (!strcmp(cmd, "ping")) {
    char buf[96];
    JsonWriter w(buf, sizeof(buf));
    w.open().integer("id", id).boolean("ok", true).str("fw", fw_).close();
    send(w);
  } else if (!strcmp(cmd, "status")) {
    cmdStatus(id);
  } else if (!strcmp(cmd, "lights")) {
    cmdLights(id, req);
  } else if (!strcmp(cmd, "set")) {
    cmdSet(id, req);
  } else if (!strcmp(cmd, "get")) {
    cmdGet(id, req);
  } else if (!strcmp(cmd, "estop")) {
    enterEstop("cmd", true);
    replyOk(id);
  } else if (!strcmp(cmd, "reset")) {
    cmdReset(id);
  } else if (!strcmp(cmd, "home")) {
    cmdHome(id);
  } else if (!strcmp(cmd, "feed")) {
    cmdFeed(id);
  } else if (!strcmp(cmd, "sleeve")) {
    cmdSleeve(id);
  } else if (!strcmp(cmd, "sort")) {
    cmdSort(id, req, false);
  } else if (!strcmp(cmd, "eject_reject")) {
    cmdSort(id, req, true);
  } else {
    replyErr(id, ERR_BAD_CMD, "unknown cmd");
  }
}

void Scanner::cmdStatus(int32_t id) {
  char buf[REPLY_MAX_LEN];
  JsonWriter w(buf, sizeof(buf));
  bool hopperEmpty = hopperEmpty_ || (hal_.sensor(SN_ELEV_LIMIT) && !hal_.sensor(SN_STACK_TOP));
  w.open().integer("id", id).boolean("ok", true);
  w.str("state", stateName(state()));
  w.boolean("homed", homed_);
  w.boolean("hopper_empty", hopperEmpty);
  w.boolean("magazine_empty", hal_.sensor(SN_MAG_EMPTY));
  w.boolean("sleeved_card", sleeved_);
  w.open("sensors");
  for (int i = 0; i < SN_COUNT; i++) w.boolean(sensorName((Sensor)i), hal_.sensor((Sensor)i));
  w.close();
  w.num("vacuum_kpa", hal_.vacuumKpa(), 1);
  w.open("lights").integer("top", lightTop_).integer("bottom", lightBottom_).close();
  w.close();
  send(w);
}

void Scanner::cmdLights(int32_t id, const JsonObject &req) {
  int32_t top = lightTop_, bottom = lightBottom_;
  if ((req.has("top") && !req.getInt("top", top)) || (req.has("bottom") && !req.getInt("bottom", bottom)) ||
      top < 0 || top > 255 || bottom < 0 || bottom > 255) {
    replyErr(id, ERR_BAD_CMD, "top/bottom must be integers 0-255");
    return;
  }
  lightTop_ = (uint8_t)top;
  lightBottom_ = (uint8_t)bottom;
  hal_.lights(lightTop_, lightBottom_);
  char buf[96];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", id).boolean("ok", true).integer("top", top).integer("bottom", bottom).close();
  send(w);
}

void Scanner::cmdSet(int32_t id, const JsonObject &req) {
  const SettingDef *d = findSetting(req.getStr("key"));
  double v;
  if (!d) {
    replyErr(id, ERR_BAD_CMD, "unknown key");
    return;
  }
  if (!req.getNum("value", v)) {
    replyErr(id, ERR_BAD_CMD, "value must be a number");
    return;
  }
  if (v < d->lo || v > d->hi || (d->integer && v != floor(v))) {
    replyErr(id, ERR_BAD_CMD, "value out of range");
    return;
  }
  s_.*d->field = (float)v;
  if (store_) store_->save(d->key, (float)v);
  if (!strncmp(d->key, "cur_", 4)) applyCurrents();
  cmdGet(id, req);
}

void Scanner::cmdGet(int32_t id, const JsonObject &req) {
  const SettingDef *d = findSetting(req.getStr("key"));
  if (!d) {
    replyErr(id, ERR_BAD_CMD, "unknown key");
    return;
  }
  char buf[128];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", id).boolean("ok", true).str("key", d->key).num("value", s_.*d->field).close();
  send(w);
}

void Scanner::cmdReset(int32_t id) {
  if (job_ != JOB_NONE) {
    replyErr(id, ERR_BUSY, "a job is running; use estop to abort it");
    return;
  }
  if (hal_.sensor(SN_ESTOP)) {
    replyErr(id, ERR_ESTOP, "e-stop button still pressed");
    return;
  }
  if (hal_.sensor(SN_LID_OPEN)) {
    replyErr(id, ERR_ESTOP, "lid open");
    return;
  }
  if (estop_) {
    estop_ = false;
    hal_.enableMotors(true);
  }
  char buf[96];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", id).boolean("ok", true).str("state", stateName(state())).close();
  send(w);
}

bool Scanner::canStart(int32_t id, bool needHome) {
  if (estop_) {
    replyErr(id, ERR_ESTOP, "e-stop / lid: send reset");
    return false;
  }
  if (job_ != JOB_NONE) {
    replyErr(id, ERR_BUSY, stateName(state()));
    return false;
  }
  if (needHome && !homed_) {
    replyErr(id, ERR_NOT_HOMED, "send home first");
    return false;
  }
  return true;
}

void Scanner::cmdHome(int32_t id) {
  if (!canStart(id, false)) return;
  startJob(JOB_HOME, id);
  homed_ = false;
  hal_.enableMotors(true);
  pneumaticsOff();
  hal_.servo(SV_LIFT, deg(s_.lift_up_deg));
  hal_.servo(SV_PUSHER, deg(s_.pusher_rest_deg));
  hal_.servo(SV_DIVERTER, deg(s_.div0_deg));
  enter(P_HOME_SERVOS, 0);
}

void Scanner::cmdFeed(int32_t id) {
  if (!canStart(id, true)) return;
  if (hal_.sensor(SN_SCAN_STOP)) {
    replyErr(id, ERR_BAD_CMD, "card already at the scan station");
    return;
  }
  if (sleeved_) {  // sort runs the exit rollers, which share the feed loop with the scan station
    replyErr(id, ERR_BAD_CMD, "sleeved card still on the platen: sort it first");
    return;
  }
  startJob(JOB_FEED, id);
  doubleSeen_ = false;
  scanHit_ = false;
  if (hal_.sensor(SN_STACK_TOP)) {
    startPuff();
  } else if (hal_.sensor(SN_ELEV_LIMIT)) {
    if (!hopperEmpty_) event("hopper_empty");
    hopperEmpty_ = true;
    failJob(ERR_HOPPER_EMPTY, "elevator at the top, no card at stack_top", false);
  } else {
    moveAbs(AX_ELEV, s_.elev_max_mm, s_.elev_speed);
    enter(P_FEED_RAISE, motionMs(s_.elev_max_mm - hal_.position(AX_ELEV), s_.elev_speed));
  }
}

void Scanner::cmdSleeve(int32_t id) {
  if (!canStart(id, true)) return;
  if (sleeved_) {
    replyErr(id, ERR_BAD_CMD, "sleeved card still on the platen: sort it first");
    return;
  }
  if (!hal_.sensor(SN_SCAN_STOP)) {
    replyErr(id, ERR_BAD_CMD, "no card at the scan station");
    return;
  }
  if (!sleeveStaged_ && hal_.sensor(SN_MAG_EMPTY)) {
    replyErr(id, ERR_MAGAZINE_EMPTY, "sleeve magazine empty");
    return;
  }
  startJob(JOB_SLEEVE, id);
  if (sleeveStaged_) {
    startPlaten();  // the last picked sleeve is still on the platen
  } else {
    hal_.output(OUT_SLEEVE_PICK, true);  // 0. pick wheels: bottom sleeve onto the platen
    enter(P_SLV_PICK, (uint32_t)s_.sleeve_pick_ms);
  }
}

void Scanner::cmdSort(int32_t id, const JsonObject &req, bool reject) {
  int32_t bin = 2;
  if (!reject && (!req.getInt("bin", bin) || bin < 0 || bin > 2)) {
    replyErr(id, ERR_BAD_CMD, "bin must be 0, 1 or 2");
    return;
  }
  if (!canStart(id, true)) return;
  if (reject) {
    if (sleeved_) {
      replyErr(id, ERR_BAD_CMD, "sleeved card still on the platen: sort it first");
      return;
    }
    if (!hal_.sensor(SN_SCAN_STOP)) {
      replyErr(id, ERR_BAD_CMD, "no card at the scan station");
      return;
    }
  } else if (hal_.sensor(SN_SCAN_STOP)) {
    // the exit rollers share the feed loop: they would carry this card along
    replyErr(id, ERR_BAD_CMD, "card at the scan station: sleeve or eject_reject it first");
    return;
  }
  startJob(reject ? JOB_REJECT : JOB_SORT, id);
  bin_ = (uint8_t)bin;
  hal_.servo(SV_DIVERTER, divAngle(bin_));
  enter(P_SORT_DIVERT, 0);
}

// ---- job plumbing ---------------------------------------------------------------

void Scanner::startJob(Job j, int32_t id) {
  job_ = j;
  jobId_ = id;
}

void Scanner::enter(uint8_t phase, uint32_t timeoutMs) {
  phase_ = phase;
  t0_ = hal_.millis();
  timeout_ = timeoutMs;
}

uint32_t Scanner::elapsed() { return hal_.millis() - t0_; }

bool Scanner::expired() { return timeout_ && elapsed() >= timeout_; }

void Scanner::finishOk() {
  char buf[96];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", jobId_).boolean("ok", true);
  if (job_ == JOB_SORT || job_ == JOB_REJECT) w.integer("bin", bin_);
  w.close();
  job_ = JOB_NONE;
  phase_ = P_NONE;
  send(w);
}

// Stop everything, drop the vacuum, park the pusher, reply with the error.
void Scanner::failJob(Err e, const char *msg, bool needHome) {
  stopAll(true);
  pneumaticsOff();
  hal_.servo(SV_PUSHER, deg(s_.pusher_rest_deg));
  if (needHome) homed_ = false;
  if (e == ERR_SLEEVE_INSERT_FAIL) sleeveStaged_ = false;  // the operator clears the station
  int32_t id = jobId_;
  job_ = JOB_NONE;
  phase_ = P_NONE;
  replyErr(id, e, msg);
}

void Scanner::enterEstop(const char *source, bool emitEvent) {
  stopAll(true);
  hal_.enableMotors(false);
  pneumaticsOff();
  if (job_ != JOB_NONE) {
    int32_t id = jobId_;
    job_ = JOB_NONE;
    phase_ = P_NONE;
    replyErr(id, ERR_ESTOP, !strcmp(source, "lid") ? "lid opened" : "e-stop");
  }
  estop_ = true;
  homed_ = false;
  if (emitEvent) event("estop", "source", source);
}

bool Scanner::debounce(Debounce &d, bool raw, uint32_t now) {
  if (raw != d.raw) {
    d.raw = raw;
    d.since = now;
  }
  if (d.stable != d.raw && now - d.since >= DEBOUNCE_MS) {
    d.stable = d.raw;
    return d.stable;
  }
  return false;
}

void Scanner::tick() {
  uint32_t now = hal_.millis();
  if (debounce(estopIn_, hal_.sensor(SN_ESTOP), now)) enterEstop("input", true);
  if (debounce(lidIn_, hal_.sensor(SN_LID_OPEN), now)) {
    enterEstop("lid", false);
    event("lid_open");
  }
  if (debounce(magLowIn_, hal_.sensor(SN_MAG_LOW), now)) event("magazine_low");
  if (job_ != JOB_NONE) step();
}

void Scanner::step() {
  switch (job_) {
    case JOB_HOME: stepHome(); break;
    case JOB_FEED: stepFeed(); break;
    case JOB_SLEEVE: stepSleeve(); break;
    case JOB_SORT:
    case JOB_REJECT: stepSort(); break;
    case JOB_NONE: break;
  }
}

// ---- home -----------------------------------------------------------------------

void Scanner::startHomeAxis() {
  Axis a = HOME_ORDER[homeIdx_];
  hal_.zero(a);  // positions are relative to here until the switch is found
  if (hal_.sensor(homeSwitch(a))) {
    moveRel(a, BACKOFF_MM, s_.home_speed);
    enter(P_HOME_BACKOFF, motionMs(BACKOFF_MM, s_.home_speed));
  } else {
    float travel = (a == AX_TONGUE ? s_.tongue_depth_mm : a == AX_PICK ? s_.pick_travel_mm : s_.elev_max_mm) +
                   HOME_EXTRA_MM;
    moveRel(a, -travel, s_.home_speed);
    enter(P_HOME_SEEK, motionMs(travel, s_.home_speed));
  }
}

void Scanner::stepHome() {
  Axis a = HOME_ORDER[homeIdx_ < HOME_AXES ? homeIdx_ : 0];
  bool sw = hal_.sensor(homeSwitch(a));
  switch (phase_) {
    case P_HOME_SERVOS:
      if (elapsed() >= (uint32_t)s_.servo_ms) {
        homeIdx_ = 0;
        startHomeAxis();
      }
      break;
    case P_HOME_BACKOFF:
      if (!hal_.moving(a)) {
        if (sw) return failJob(ERR_JAM, a == AX_ELEV ? "elevator home switch stuck"
                                         : a == AX_PICK ? "pick home switch stuck" : "tongue home switch stuck",
                               true);
        startHomeAxis();
      } else if (expired()) {
        failJob(ERR_JAM, "home backoff timeout", true);
      }
      break;
    case P_HOME_SEEK:
      if (sw) {
        hal_.stop(a, true);
        enter(P_HOME_SETTLE, SETTLE_MS);
      } else if (!hal_.moving(a) || expired()) {
        failJob(ERR_JAM, a == AX_ELEV ? "elevator home switch not found"
                         : a == AX_PICK ? "pick home switch not found" : "tongue home switch not found",
                true);
      }
      break;
    case P_HOME_SETTLE:
      if (!hal_.moving(a)) {
        hal_.zero(a);
        if (++homeIdx_ >= HOME_AXES) {
          homed_ = true;
          hopperEmpty_ = false;
          sleeved_ = false;
          finishOk();
        } else {
          startHomeAxis();
        }
      } else if (expired()) {
        failJob(ERR_JAM, "axis did not stop", true);
      }
      break;
  }
}

// ---- feed -----------------------------------------------------------------------

void Scanner::startPuff() {
  if (s_.puff_ms > 0) {
    hal_.output(OUT_PUFF_PUMP, true);
    hal_.output(OUT_STACK_PUFF, true);
    enter(P_FEED_PUFF, 0);
  } else {
    startGrip();
  }
}

void Scanner::startGrip() {
  hal_.output(OUT_VAC_PUMP, true);
  hal_.output(OUT_PICK_CUP, true);
  enter(P_FEED_GRIP, vacTimeout());
}

void Scanner::feedWatch() {
  if (hal_.sensor(SN_DOUBLE_FEED)) doubleSeen_ = true;
  if (!scanHit_ && hal_.sensor(SN_SCAN_STOP)) {
    hal_.stop(AX_FEED, true);
    scanHit_ = true;
  }
}

void Scanner::stepFeed() {
  switch (phase_) {
    case P_FEED_RAISE:
      if (hal_.sensor(SN_STACK_TOP)) {
        hal_.stop(AX_ELEV, true);
        hopperEmpty_ = false;
        startPuff();
      } else if (hal_.sensor(SN_ELEV_LIMIT) || !hal_.moving(AX_ELEV)) {
        hal_.stop(AX_ELEV, true);
        if (!hopperEmpty_) event("hopper_empty");
        hopperEmpty_ = true;
        failJob(ERR_HOPPER_EMPTY, "elevator at the top, no card at stack_top", false);
      } else if (expired()) {
        failJob(ERR_JAM, "elevator raise timeout", true);
      }
      break;
    case P_FEED_PUFF:
      if (elapsed() >= (uint32_t)s_.puff_ms) {
        hal_.output(OUT_STACK_PUFF, false);
        hal_.output(OUT_PUFF_PUMP, false);
        startGrip();
      }
      break;
    case P_FEED_GRIP:
      if (elapsed() >= (uint32_t)s_.cup_dwell_ms && gripped()) {
        moveRel(AX_PICK, s_.pick_travel_mm, s_.pick_speed);
        moveRel(AX_FEED, s_.feed_max_mm, s_.feed_speed);
        enter(P_FEED_PICK, motionMs(s_.pick_travel_mm, s_.pick_speed));
      } else if (expired()) {
        failJob(ERR_PICK_FAIL, "pick cup did not grip", false);
      }
      break;
    case P_FEED_PICK:
      feedWatch();
      if (!hal_.moving(AX_PICK)) {
        hal_.output(OUT_PICK_CUP, false);
        hal_.output(OUT_VAC_PUMP, false);
        moveAbs(AX_PICK, 0, s_.pick_speed);
        enter(P_FEED_RUN, motionMs(s_.feed_max_mm, s_.feed_speed) + motionMs(s_.pick_travel_mm, s_.pick_speed));
      } else if (expired()) {
        failJob(ERR_JAM, "pick arm stroke timeout", true);
      }
      break;
    case P_FEED_RUN:
      feedWatch();
      if (scanHit_) {
        if (!hal_.moving(AX_FEED) && !hal_.moving(AX_PICK)) {
          if (doubleSeen_) return failJob(ERR_DOUBLE_FEED, "double feed: card held at the scan station", false);
          finishOk();
        } else if (expired()) {
          failJob(ERR_JAM, "pick arm return timeout", true);
        }
      } else if (!hal_.moving(AX_FEED) || expired()) {
        failJob(ERR_JAM, "card did not reach scan_stop", false);
      }
      break;
  }
}

// ---- sleeve ---------------------------------------------------------------------

void Scanner::startPlaten() {
  hal_.output(OUT_VAC_PUMP, true);
  hal_.output(OUT_PLATEN, true);
  enter(P_SLV_PLATEN, vacTimeout());
}

void Scanner::stepSleeve() {
  switch (phase_) {
    case P_SLV_PICK:  // 0. run until sleeve_present, then sleeve_push_ms more; sleeve_pick_ms is the max run
      if (hal_.sensor(SN_SLEEVE_PRESENT)) {
        enter(P_SLV_PICK_PUSH, 0);
      } else if (expired()) {
        hal_.output(OUT_SLEEVE_PICK, false);
        failJob(ERR_SLEEVE_OPEN_FAIL, "no sleeve at sleeve_present (wheels slipped, or misfeed)", false);
      }
      break;
    case P_SLV_PICK_PUSH:  // sleeve_present trips a few mm short of the fence: push it flush, then brake
      if (elapsed() >= (uint32_t)s_.sleeve_push_ms) {
        hal_.output(OUT_SLEEVE_PICK, false);
        startPlaten();
      }
      break;
    case P_SLV_PLATEN:  // 1. platen vacuum (2nd check): only a sleeve covering every hole reaches grip
      if (elapsed() >= (uint32_t)s_.cup_dwell_ms && gripped()) {
        sleeveStaged_ = true;
        hal_.servo(SV_LIFT, deg(s_.lift_down_deg));
        enter(P_SLV_LIFT_DOWN, 0);
      } else if (expired()) {
        sleeveStaged_ = false;  // nothing there: the next sleeve picks again
        failJob(ERR_SLEEVE_OPEN_FAIL, "platen vacuum low (no sleeve picked, or leak)", false);
      }
      break;
    case P_SLV_LIFT_DOWN:  // 2. lift cup down, then suck
      if (elapsed() >= (uint32_t)s_.servo_ms) {
        hal_.output(OUT_LIFT_CUP, true);
        enter(P_SLV_LIFT_GRIP, vacTimeout());
      }
      break;
    case P_SLV_LIFT_GRIP:
      if (elapsed() >= (uint32_t)s_.cup_dwell_ms && gripped()) {
        hal_.servo(SV_LIFT, deg(s_.lift_up_deg));
        enter(P_SLV_LIFT_UP, 0);
      } else if (expired()) {
        failJob(ERR_SLEEVE_OPEN_FAIL, "lift cup did not seal on the top ply", false);
      }
      break;
    case P_SLV_LIFT_UP:  // mouth open; the ply must still be held
      if (elapsed() >= (uint32_t)s_.servo_ms) {
        if (!gripped()) return failJob(ERR_SLEEVE_OPEN_FAIL, "lift cup lost the top ply", false);
        hal_.output(OUT_PUFF_PUMP, true);  // 3. mouth jet
        hal_.output(OUT_MOUTH_JET, true);
        enter(P_SLV_JET, 0);
      }
      break;
    case P_SLV_JET:
      if (elapsed() >= (uint32_t)s_.jet_ms) {
        hal_.output(OUT_MOUTH_JET, false);
        hal_.output(OUT_PUFF_PUMP, false);
        moveAbs(AX_TONGUE, s_.tongue_depth_mm, s_.tongue_speed);  // 4. tongue in
        enter(P_SLV_TONGUE_IN, motionMs(s_.tongue_depth_mm, s_.tongue_speed));
      }
      break;
    case P_SLV_TONGUE_IN:
      if (!hal_.moving(AX_TONGUE)) {
        mouthSeen_ = false;  // 5. feed until sleeve_mouth + insert_mm
        moveRel(AX_FEED, s_.insert_max_mm, s_.insert_speed);
        enter(P_SLV_FEED, motionMs(s_.insert_max_mm + s_.insert_mm, s_.insert_speed));
      } else if (expired()) {
        failJob(ERR_SLEEVE_INSERT_FAIL, "tongue did not extend", true);
      }
      break;
    case P_SLV_FEED:
      if (!mouthSeen_ && hal_.sensor(SN_SLEEVE_MOUTH)) {
        mouthSeen_ = true;
        moveRel(AX_FEED, s_.insert_mm, s_.insert_speed);  // retargets the running move
      }
      if (!hal_.moving(AX_FEED)) {
        if (!mouthSeen_) return failJob(ERR_SLEEVE_INSERT_FAIL, "card never reached the sleeve mouth", true);
        hal_.servo(SV_PUSHER, deg(s_.pusher_seat_deg));  // 6. pawl seats the card (70 mm in -> full)
        enter(P_SLV_SEAT, 0);
      } else if (expired()) {
        failJob(ERR_SLEEVE_INSERT_FAIL, "insert timeout", true);
      }
      break;
    case P_SLV_SEAT:  // the pawl stays at the seat angle: it holds the card while the tongues retract
      if (elapsed() >= (uint32_t)(s_.servo_ms + s_.pusher_seat_ms)) {
        moveAbs(AX_TONGUE, 0, s_.tongue_speed);  // 7. tongue out
        enter(P_SLV_TONGUE_OUT, motionMs(s_.tongue_depth_mm, s_.tongue_speed));
      }
      break;
    case P_SLV_TONGUE_OUT:
      if (!hal_.moving(AX_TONGUE)) {
        hal_.output(OUT_LIFT_CUP, false);  // 8. release cups
        hal_.output(OUT_PLATEN, false);
        hal_.output(OUT_VAC_PUMP, false);
        sleeved_ = true;
        sleeveStaged_ = false;
        enter(P_SLV_RELEASE, 0);
      } else if (expired()) {
        failJob(ERR_SLEEVE_INSERT_FAIL, "tongue did not retract", true);
      }
      break;
    case P_SLV_RELEASE:
      if (elapsed() >= (uint32_t)s_.cup_dwell_ms) finishOk();
      break;
  }
}

// ---- sort / eject_reject ----------------------------------------------------------

void Scanner::startPush() {
  hal_.servo(SV_PUSHER, deg(s_.pusher_out_deg));     // from rest or seat: pawl to +36, into the exit nip
  moveRel(AX_FEED, s_.feed_max_mm, s_.feed_speed);  // exit rollers (feed loop) take the card
  enter(P_SORT_PUSH, (uint32_t)s_.exit_timeout_ms);
}

void Scanner::stepSort() {
  switch (phase_) {
    case P_SORT_DIVERT:
      if (elapsed() >= (uint32_t)s_.servo_ms) {
        if (job_ == JOB_REJECT) {
          moveRel(AX_FEED, s_.reject_mm, s_.feed_speed);
          enter(P_REJ_FEED, motionMs(s_.reject_mm, s_.feed_speed));
        } else {
          startPush();
        }
      }
      break;
    case P_REJ_FEED:
      if (!hal_.moving(AX_FEED)) {
        if (hal_.sensor(SN_SCAN_STOP)) return failJob(ERR_JAM, "card still at the scan station", false);
        startPush();
      } else if (expired()) {
        failJob(ERR_JAM, "reject feed timeout", false);
      }
      break;
    case P_SORT_PUSH:
      if (hal_.sensor(SN_EXIT)) {
        enter(P_SORT_CLEAR, (uint32_t)s_.exit_timeout_ms);
      } else if (expired()) {
        failJob(ERR_EXIT_TIMEOUT, "card did not reach the exit beam", false);
      }
      break;
    case P_SORT_CLEAR:
      if (!hal_.sensor(SN_EXIT)) {
        hal_.stop(AX_FEED, false);
        hal_.servo(SV_PUSHER, deg(s_.pusher_rest_deg));
        sleeved_ = false;
        sleeveStaged_ = false;  // the pawl sweeps the platen clear
        enter(P_SORT_RETURN, 0);
      } else if (expired()) {
        failJob(ERR_JAM, "exit beam blocked", false);
      }
      break;
    case P_SORT_RETURN:
      if (elapsed() >= (uint32_t)s_.servo_ms) finishOk();
      break;
  }
}
// ---- helpers ----------------------------------------------------------------------

bool Scanner::gripped() { return s_.vac_grip_kpa <= 0 || hal_.vacuumKpa() >= s_.vac_grip_kpa; }

uint32_t Scanner::vacTimeout() {
  uint32_t t = (uint32_t)s_.vac_timeout_ms;
  uint32_t min = (uint32_t)s_.cup_dwell_ms + 100;
  return t > min ? t : min;
}

// Generous: 1.5x the cruise time, plus the ramps, plus 0.5 s.
uint32_t Scanner::motionMs(float mm, float speed) {
  float t = fabsf(mm) / speed * 1500.0f + speed / s_.accel * 2000.0f + 500.0f;
  return (uint32_t)t;
}

void Scanner::moveAbs(Axis a, float mm, float speed) { hal_.moveTo(a, mm, speed, s_.accel); }

void Scanner::moveRel(Axis a, float mm, float speed) { moveAbs(a, hal_.position(a) + mm, speed); }

void Scanner::stopAll(bool hard) {
  for (int i = 0; i < AX_COUNT; i++) hal_.stop((Axis)i, hard);
}

void Scanner::pneumaticsOff() {
  for (int i = 0; i < OUT_COUNT; i++) hal_.output((Output)i, false);
}

uint8_t Scanner::divAngle(uint8_t bin) {
  return deg(bin == 0 ? s_.div0_deg : bin == 1 ? s_.div1_deg : s_.div2_deg);
}

void Scanner::applyCurrents() {
  hal_.setCurrent(AX_ELEV, (uint16_t)s_.cur_elev);
  hal_.setCurrent(AX_PICK, (uint16_t)s_.cur_pick);
  hal_.setCurrent(AX_FEED, (uint16_t)s_.cur_feed);
  hal_.setCurrent(AX_TONGUE, (uint16_t)s_.cur_tongue);
}

}  // namespace cs
