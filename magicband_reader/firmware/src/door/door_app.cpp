#include "door_app.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <time.h>

#include "config.h"
#include "ha.h"
#include "mb_door.h"
#include "mb_protocol.h"
#include "user_store_nvs.h"

using namespace mb;

static NvsUserStore users;
static DoorCore core(users);
static EventLog eventLog;
static Preferences cfg;

static uint8_t brightness = 96, volume = 60;
static uint32_t unlockMs = UNLOCK_PULSE_MS;
static char newName[NAME_LEN] = "";
static int selected = -1;  // user slot picked in HA

static bool readerOnline = ALL_IN_ONE, readerTamper = false, linkAlarm = false;
static uint32_t linkErrors = 0;
static bool doorOpen = false;
static uint8_t lastFeedback = FB_IDLE;
static uint32_t lastHold = 0;

// ---- helpers ---------------------------------------------------------------------------
static uint32_t nowTs() {
  time_t t = time(nullptr);
  return t > 1600000000 ? (uint32_t)t : millis() / 1000;
}

static void uidText(const Uid &u, char *out) {  // out: 21 bytes
  if (!u.len) {
    strcpy(out, "");
    return;
  }
#if SHOW_FULL_UID
  u.toHex(out);
#else
  snprintf(out, 21, "%02X..%02X", u.b[0], u.b[u.len - 1]);
#endif
}

static bool tampered() { return readerTamper || !readerOnline || linkAlarm; }

static void sendFeedback(uint8_t state, uint32_t holdMs) {
  if (holdMs > 65535) holdMs = 65535;
  lastFeedback = state;
  lastHold = holdMs;
  frontFeedback(state, holdMs);
}

// ---- strike / door -----------------------------------------------------------------------
static bool unlocked = false, openedDuringPulse = false;
static uint32_t unlockUntil = 0;

static void writeStrike(bool unlock) {
  bool energise = STRIKE_ENERGIZE_TO_UNLOCK ? unlock : !unlock;
  digitalWrite(PIN_STRIKE, energise ? HIGH : LOW);
}

static void publishLock() { haPublish("lock/state", unlocked ? "UNLOCKED" : "LOCKED", true); }

static void unlockDoor() {
  unlocked = true;
  openedDuringPulse = false;
  unlockUntil = millis() + unlockMs;
  writeStrike(true);
  publishLock();
}

static void relock() {
  if (!unlocked) return;
  unlocked = false;
  writeStrike(false);
  publishLock();
}

// ---- reporting ------------------------------------------------------------------------------
static void publishEvent(const LogEvent &e, const char *topic, bool retain) {
  JsonDocument d;
  User u;
  bool known = e.slot >= 0 && users.load(e.slot, u);
  char uid[21];
  uidText(e.uid, uid);
  d["seq"] = e.seq;
  d["ts"] = e.t;
  d["method"] = eventKindName(e.kind);
  d["result"] = outcomeName(e.outcome);
  d["reason"] = reasonName(e.reason);
  d["user"] = known ? u.name : "";
  d["uid"] = uid;
  if (e.kind == EV_FINGER) d["finger"] = e.page;
  haPublishJson(topic, d, retain);
}

static void logEvent(uint8_t kind, const Decision &dec, const Uid *uid, uint16_t page) {
  LogEvent e;
  e.t = nowTs();
  e.kind = kind;
  e.outcome = dec.outcome;
  e.reason = dec.reason;
  e.slot = (int8_t)dec.slot;
  if (uid) e.uid = *uid;
  e.page = page;
  eventLog.add(e);
  const LogEvent &l = eventLog.latest();
  publishEvent(l, "log", false);
  if (kind == EV_BAND || kind == EV_FINGER || kind == EV_FINGER_NOMATCH || kind == EV_TIMEOUT || kind == EV_REMOTE ||
      kind == EV_REX) {
    publishEvent(l, "scan", true);
    const char *et = dec.outcome == OUT_GRANT         ? "granted"
                     : dec.outcome == OUT_NEED_FINGER ? "need_finger"
                     : dec.outcome == OUT_LOCKED      ? "locked_out"
                                                      : "denied";
    JsonDocument d;
    User u;
    d["event_type"] = et;
    d["method"] = eventKindName(kind);
    d["reason"] = reasonName(dec.reason);
    d["user"] = dec.slot >= 0 && users.load(dec.slot, u) ? u.name : "";
    if (dec.outcome != OUT_NONE) haPublishJson("access", d, false);
  }
  log_i("%s -> %s (%s) slot %d", eventKindName(kind), outcomeName(dec.outcome), reasonName(dec.reason), dec.slot);
}

static void logPlain(uint8_t kind, uint16_t page) {
  Decision d;
  d.outcome = OUT_NONE;
  logEvent(kind, d, nullptr, page);
}

static void publishUsers() {
  JsonDocument d;
  JsonArray arr = d.to<JsonArray>();
  for (int i = 0; i < MAX_USERS; i++) {
    User u;
    if (!users.load(i, u)) continue;
    JsonObject o = arr.add<JsonObject>();
    o["slot"] = i;
    o["name"] = String(u.name);
    o["policy"] = policyName(u.policy);
    o["enabled"] = (bool)u.enabled;
    JsonArray b = o["bands"].to<JsonArray>();
    for (int k = 0; k < u.nBands; k++) {
      char t[21];
      uidText(u.bands[k], t);
      b.add(String(t));
    }
    JsonArray f = o["fingers"].to<JsonArray>();
    for (int k = 0; k < u.nFingers; k++) f.add(u.fingers[k]);
  }
  haPublishJson("users", d, true);
}

static void publishSelected() {
  User u;
  bool ok = selected >= 0 && users.load(selected, u);
  haPublish("user", ok ? u.name : "-", true);
  haPublish("policy", ok ? policyName(u.policy) : "band_and_finger", true);
  haPublish("enabled", ok && u.enabled ? "ON" : "OFF", true);
}

// Problem sensor: users whose policy needs a finger, but the reader has no R503.
static void publishFingerProblem() {
  bool problem = core.fingerProblem();
  haPublish("fp_problem", problem ? "ON" : "OFF", true);
  if (problem) log_w("users need a finger but the reader has no fingerprint sensor: they are denied");
}

static void usersChanged() {
  publishUsers();
  haPublishDiscovery();  // select options
  publishSelected();
  publishFingerProblem();
}

static void publishEnroll(const char *s) { haPublish("enroll", s, true); }

static void publishTamper() { haPublish("tamper", tampered() ? "ON" : "OFF", true); }

static void tamperChanged() {
  core.setTampered(tampered());
  static bool last = false;
  if (tampered() != last) {
    last = tampered();
    publishTamper();
  }
}

void appUserOptions(JsonArray opts) {
  for (int i = 0; i < MAX_USERS; i++) {
    User u;
    if (users.load(i, u)) opts.add(String(u.name));
  }
}

void appOnMqttConnected() {
  publishLock();
  haPublish("door", doorOpen ? "ON" : "OFF", true);
  publishTamper();
  haPublish("reader", readerOnline ? "ON" : "OFF", true);
  usersChanged();
  publishEnroll(core.enrollStatusNow());
  haPublish("new_name", newName, true);
  haPublish("brightness", String(brightness).c_str(), true);
  haPublish("volume", String(volume).c_str(), true);
  haPublish("unlock_time", String(unlockMs / 1000).c_str(), true);
  haPublish("link_errors", String(linkErrors).c_str(), true);
}

// ---- actions ------------------------------------------------------------------------------------
static void run(const DoorAction &a) {
  if (a.deleteFingerPage >= 0) frontDeleteFinger((uint16_t)a.deleteFingerPage);
  if (a.unlock) unlockDoor();
  if (a.feedback) sendFeedback(a.fbState, a.fbHoldMs);
  if (a.resendFeedback) sendFeedback(lastFeedback, lastHold);
  if (a.enrollFingerPage >= 0) frontEnrollFinger((uint16_t)a.enrollFingerPage);
  if (a.enrollStatus) publishEnroll(a.enrollStatus);
  if (a.enroll.event != ENR_NONE && a.enrollOk()) {
    selected = a.enroll.slot;
    usersChanged();
  }
  if (a.log) logEvent(a.kind, a.decision, a.uid.len ? &a.uid : nullptr, a.page);
}

void doorBand(const uint8_t *uid, uint8_t len) { run(core.band(Uid::make(uid, len), millis())); }
void doorFinger(uint16_t page) { run(core.finger(page, millis())); }
void doorFingerNoMatch() { run(core.fingerNoMatch(millis())); }
void doorEnrollResult(uint16_t page, uint8_t status) { run(core.enrollResult(page, status, millis())); }
void doorResendFeedback() { sendFeedback(lastFeedback, lastHold); }
bool doorIsOpen() { return doorOpen; }

void doorReaderOnline(bool online) {
  if (online == readerOnline) return;
  readerOnline = online;
  logPlain(EV_LINK, online);
  haPublish("reader", online ? "ON" : "OFF", true);
  tamperChanged();
  if (online) {
    frontConfig(brightness, volume);
    sendFeedback(core.restingFeedback(), 0);
  }
}

void doorReaderTamper(bool open, bool logIt) {
  readerTamper = open;
  if (logIt) logPlain(EV_TAMPER, open);
  tamperChanged();
}

void doorReaderCaps(uint8_t caps) {
  static int known = -1;
  if (known == caps) return;
  known = caps;
  bool fp = caps & CAP_FINGERPRINT;
  log_i("reader caps 0x%02x: fingerprint %s", caps, fp ? "yes" : "NO");
  run(core.setFingerHw(fp));
  publishFingerProblem();
}

void doorLinkErrors(uint32_t rejected, bool alarm) {
  linkAlarm = alarm;
  if (rejected != linkErrors) {
    linkErrors = rejected;
    haPublish("link_errors", String(rejected).c_str(), true);
  }
  tamperChanged();
}

// ---- MQTT commands ---------------------------------------------------------------------------------
static int userArg(JsonDocument &d) {
  const char *n = d["user"];
  return n ? users.findByName(n) : selected;
}

static void setPolicy(int slot, int p) {
  User u;
  if (p < 0 || !users.load(slot, u)) return;
  u.policy = (uint8_t)p;
  users.save(slot, u);
  usersChanged();  // also re-evaluates the fingerprint problem sensor
}

static void deleteUser(int slot) {
  User u;
  if (!users.load(slot, u)) return;
  if (core.fingerHw())
    for (int k = 0; k < u.nFingers; k++) frontDeleteFinger(u.fingers[k]);  // remove the templates from the R503 too
  users.erase(slot);
  if (selected == slot) selected = -1;
  usersChanged();
}

void appOnMqtt(const char *sub, const char *payload) {
  uint32_t now = millis();
  if (!strcmp(sub, "lock/set")) {
    if (!strcmp(payload, "UNLOCK"))
      run(core.remoteUnlock());
    else if (!strcmp(payload, "LOCK"))
      relock();
  } else if (!strcmp(sub, "new_name/set")) {
    strlcpy(newName, payload, sizeof(newName));
    haPublish("new_name", newName, true);
  } else if (!strcmp(sub, "user/set")) {
    selected = users.findByName(payload);
    publishSelected();
  } else if (!strcmp(sub, "policy/set")) {
    setPolicy(selected, parsePolicy(payload));
  } else if (!strcmp(sub, "enabled/set")) {
    User u;
    if (users.load(selected, u)) {
      u.enabled = !strcmp(payload, "ON");
      users.save(selected, u);
      usersChanged();
    }
  } else if (!strcmp(sub, "brightness/set") || !strcmp(sub, "volume/set") || !strcmp(sub, "unlock_time/set")) {
    int v = atoi(payload);
    if (sub[0] == 'b') {
      brightness = (uint8_t)constrain(v, 0, 255);
      cfg.putUChar("bright", brightness);
      haPublish("brightness", String(brightness).c_str(), true);
    } else if (sub[0] == 'v') {
      volume = (uint8_t)constrain(v, 0, 100);
      cfg.putUChar("vol", volume);
      haPublish("volume", String(volume).c_str(), true);
    } else {
      unlockMs = (uint32_t)constrain(v, 1, 30) * 1000;
      cfg.putUInt("unlock", unlockMs);
      haPublish("unlock_time", String(unlockMs / 1000).c_str(), true);
    }
    frontConfig(brightness, volume);
  } else if (!strcmp(sub, "cmd")) {
    JsonDocument d;
    if (deserializeJson(d, payload)) return;
    const char *cmd = d["cmd"] | "";
    if (!strcmp(cmd, "unlock")) {
      run(core.remoteUnlock());
    } else if (!strcmp(cmd, "enroll_band")) {
      if (d["name"].is<const char *>()) strlcpy(newName, d["name"], sizeof(newName));
      run(core.startEnrollBand(-1, newName, now));
    } else if (!strcmp(cmd, "add_band")) {
      int s = userArg(d);
      if (s >= 0) run(core.startEnrollBand(s, nullptr, now));
    } else if (!strcmp(cmd, "enroll_finger")) {
      int s = userArg(d);
      if (s >= 0) run(core.startEnrollFinger(s, now));  // "no_fingerprint_hw" without an R503
    } else if (!strcmp(cmd, "delete_user")) {
      int s = userArg(d);
      if (s >= 0) deleteUser(s);
    } else if (!strcmp(cmd, "set_policy")) {
      setPolicy(userArg(d), parsePolicy(d["policy"] | ""));
    } else if (!strcmp(cmd, "rename")) {
      User u;
      int s = userArg(d);
      const char *n = d["new_name"];
      if (n && users.load(s, u)) {
        u.setName(n);
        users.save(s, u);
        usersChanged();
      }
    } else if (!strcmp(cmd, "cancel")) {
      run(core.cancelEnroll());
    } else if (!strcmp(cmd, "clear_lockout")) {
      run(core.clearLockout());
    } else if (!strcmp(cmd, "list_users")) {
      publishUsers();
    } else if (!strcmp(cmd, "dump_log")) {
      for (int i = 0; i < eventLog.size(); i++) publishEvent(eventLog.at(i), "log", false);
    }
  }
}

// ---- inputs -----------------------------------------------------------------------------------------
struct Debounced {
  uint8_t pin;
  bool state = false, raw = false;
  uint32_t changed = 0;
  explicit Debounced(uint8_t p) : pin(p) {}
  // Returns true on a debounced change.  `state` true = contact closed (LOW).
  bool update() {
    bool r = digitalRead(pin) == LOW;
    if (r != raw) {
      raw = r;
      changed = millis();
    }
    if (raw != state && millis() - changed >= 30) {
      state = raw;
      return true;
    }
    return false;
  }
};
static Debounced rex(PIN_REX), door(PIN_DOOR), enrollBtn(PIN_ENROLL);
static uint32_t enrollPressedAt = 0;

static void pollInputs() {
  if (rex.update() && rex.state) run(core.rex());
  if (door.update()) {
    doorOpen = !door.state;  // reed closed = door shut
    if (doorOpen && unlocked) openedDuringPulse = true;
    if (!doorOpen && unlocked && openedDuringPulse && RELOCK_ON_DOOR_CLOSE) relock();
    haPublish("door", doorOpen ? "ON" : "OFF", true);
  }
  if (enrollBtn.update()) {
    if (enrollBtn.state) {
      enrollPressedAt = millis();
    } else if (millis() - enrollPressedAt >= 3000) {  // long press: cancel
      run(core.cancelEnroll());
    } else {
      run(core.startEnrollBand(-1, newName, millis()));
    }
  }
}

// ---- setup / loop ------------------------------------------------------------------------------------
void doorBegin() {
  pinMode(PIN_STRIKE, OUTPUT);
  writeStrike(false);
  pinMode(PIN_REX, INPUT_PULLUP);
  pinMode(PIN_DOOR, INPUT_PULLUP);
  pinMode(PIN_ENROLL, INPUT_PULLUP);
  delay(5);  // let the pull-ups settle before sampling
  door.state = door.raw = digitalRead(PIN_DOOR) == LOW;
  doorOpen = !door.state;

  cfg.begin("mbcfg", false);
  brightness = cfg.getUChar("bright", 96);
  volume = cfg.getUChar("vol", 60);
  unlockMs = cfg.getUInt("unlock", UNLOCK_PULSE_MS);

  users.begin();
  DoorConfig dc;
  dc.grantedHoldMs = GRANTED_HOLD_MS;
  dc.deniedHoldMs = DENIED_HOLD_MS;
  dc.tamperDenies = TAMPER_DENIES_ACCESS;
  AccessConfig ac;
  ac.fingerTimeoutMs = FINGER_TIMEOUT_MS;
  ac.maxFailures = MAX_FAILURES;
  ac.lockoutMs = LOCKOUT_MS;
  ac.lockoutMaxMs = LOCKOUT_MAX_MS;
  EnrollConfig ec;
  ec.bandTimeoutMs = ENROLL_BAND_TIMEOUT_MS;
  ec.fingerTimeoutMs = ENROLL_FINGER_TIMEOUT_MS;
  core.setConfig(dc, ac, ec);
  core.setTampered(tampered());

  // Hold ENROLL at power-up: Wi-Fi/MQTT setup portal.  The all-in-one also
  // accepts the exit button, since its enroll button is optional.
  bool portal = digitalRead(PIN_ENROLL) == LOW;
#if ALL_IN_ONE
  portal = portal || digitalRead(PIN_REX) == LOW;
  rex.state = rex.raw = digitalRead(PIN_REX) == LOW;  // the held button is not an exit request
#endif
  haBegin(portal);
  frontConfig(brightness, volume);
  log_i("door app %s up, %d users", FW_VERSION, users.count());
}

void doorLoop() {
  uint32_t now = millis();
  pollInputs();
  DoorAction t = core.tick(now);
  run(t);
  if (unlocked && (int32_t)(now - unlockUntil) >= 0) relock();
  haLoop();
}
