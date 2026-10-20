#include "mb_door.h"

namespace mb {

void DoorCore::setConfig(const DoorConfig &d, const AccessConfig &a, const EnrollConfig &e) {
  cfg_ = d;
  engine_.setConfig(a);
  enroll_.setConfig(e);
  fingerTimeoutMs_ = a.fingerTimeoutMs;
  enrollBandTimeoutMs_ = e.bandTimeoutMs;
}

void DoorCore::show(DoorAction &a, uint8_t state, uint32_t holdMs) {
  a.feedback = true;
  a.fbState = state;
  a.fbHoldMs = holdMs;
}

DoorAction DoorCore::setFingerHw(bool hw) {
  DoorAction a;
  bool wasEnrollingFinger = enroll_.state() == ENR_WAIT_FINGER;
  engine_.setFingerHw(hw);
  enroll_.setFingerHw(hw);
  if (!hw && wasEnrollingFinger) {
    a.enrollStatus = ENROLL_ST_NO_FP;
    show(a, FB_ENROLL_FAIL, cfg_.enrollHoldMs);
  }
  return a;
}

DoorAction DoorCore::decide(uint8_t kind, const Decision &d, const Uid *uid, uint16_t page, uint32_t now) {
  DoorAction a;
  switch (d.outcome) {
    case OUT_GRANT:
      a.unlock = true;
      show(a, FB_GRANTED, cfg_.grantedHoldMs);
      break;
    case OUT_NEED_FINGER:
      show(a, FB_NEED_FINGER, fingerTimeoutMs_);
      break;
    case OUT_LOCKED:
      show(a, FB_LOCKOUT, engine_.lockoutRemaining(now));
      break;
    case OUT_DENY:
      show(a, FB_DENIED, cfg_.deniedHoldMs);
      break;
    default:
      return a;
  }
  a.log = true;
  a.kind = kind;
  a.decision = d;
  if (uid) a.uid = *uid;
  a.page = page;
  return a;
}

DoorAction DoorCore::enrollDone(const EnrollResultEv &r) {
  DoorAction a;
  if (r.event == ENR_NONE) return a;
  a.enroll = r;
  bool ok = a.enrollOk();
  show(a, ok ? FB_ENROLL_OK : FB_ENROLL_FAIL, cfg_.enrollHoldMs);
  a.enrollStatus = enrollEventName(r.event);
  a.log = true;
  a.kind = EV_ENROLL;
  a.decision.outcome = ok ? OUT_GRANT : OUT_DENY;
  a.decision.slot = r.slot;
  a.page = r.page;
  return a;
}

static Decision tamperDeny() {
  Decision d;
  d.outcome = OUT_DENY;
  d.reason = WHY_TAMPER;
  return d;
}

DoorAction DoorCore::band(const Uid &uid, uint32_t now) {
  if (enroll_.active()) {
    EnrollResultEv r = enroll_.onBand(uid, now);
    if (r.event != ENR_NONE) return enrollDone(r);
    DoorAction a;  // waiting for a finger: keep showing the enrollment state
    show(a, enroll_.state() == ENR_WAIT_FINGER ? FB_ENROLL_FINGER : FB_ENROLL_BAND, 0);
    return a;
  }
  if (cfg_.tamperDenies && tampered_) return decide(EV_BAND, tamperDeny(), &uid, 0, now);
  return decide(EV_BAND, engine_.onBand(uid, now), &uid, 0, now);
}

DoorAction DoorCore::finger(uint16_t page, uint32_t now) {
  if (enroll_.active()) {
    DoorAction a;
    a.resendFeedback = true;  // ack only
    return a;
  }
  if (cfg_.tamperDenies && tampered_) return decide(EV_FINGER, tamperDeny(), nullptr, page, now);
  return decide(EV_FINGER, engine_.onFinger(page, now), nullptr, page, now);
}

DoorAction DoorCore::fingerNoMatch(uint32_t now) {
  if (enroll_.active()) {
    DoorAction a;
    a.resendFeedback = true;
    return a;
  }
  if (cfg_.tamperDenies && tampered_) return decide(EV_FINGER_NOMATCH, tamperDeny(), nullptr, 0, now);
  return decide(EV_FINGER_NOMATCH, engine_.onFingerNoMatch(now), nullptr, 0, now);
}

DoorAction DoorCore::enrollResult(uint16_t page, uint8_t status, uint32_t now) {
  EnrollResultEv ev = enroll_.onEnrollResult(page, status, now);
  if (ev.event != ENR_NONE) return enrollDone(ev);
  DoorAction a;  // stale result (we timed out / cancelled)
  if (status == ENROLL_OK && users_.findByFinger(page) < 0) a.deleteFingerPage = page;  // drop the orphan
  show(a, FB_IDLE, 0);
  return a;
}

DoorAction DoorCore::tick(uint32_t now) {
  Decision t = engine_.tick(now);
  if (t.outcome != OUT_NONE) return decide(EV_TIMEOUT, t, nullptr, 0, now);
  return enrollDone(enroll_.tick(now));  // an enroll timeout due at the same time fires next call
}

DoorAction DoorCore::rex() {
  DoorAction a;
  a.unlock = true;
  a.log = true;
  a.kind = EV_REX;
  a.decision.outcome = OUT_GRANT;
  return a;
}

DoorAction DoorCore::remoteUnlock() {
  DoorAction a = rex();
  a.kind = EV_REMOTE;
  show(a, FB_GRANTED, cfg_.grantedHoldMs);
  return a;
}

DoorAction DoorCore::startEnrollBand(int slot, const char *name, uint32_t now) {
  DoorAction a;
  bool ok = slot >= 0 ? enroll_.startAddBand(slot, now) : enroll_.startNewUser(name, now);
  if (!ok) {
    a.enrollStatus = ENROLL_ST_FULL;
    return a;
  }
  engine_.cancel();
  show(a, FB_ENROLL_BAND, enrollBandTimeoutMs_);
  a.enrollStatus = ENROLL_ST_WAIT_BAND;
  return a;
}

DoorAction DoorCore::startEnrollFinger(int slot, uint32_t now) {
  DoorAction a;
  int page = enroll_.startFinger(slot, now);
  if (page == ENROLL_START_NO_FP) {
    a.enrollStatus = ENROLL_ST_NO_FP;  // HA: "no_fingerprint_hw", nothing sent to the reader
    show(a, FB_ENROLL_FAIL, cfg_.enrollHoldMs);
    return a;
  }
  if (page < 0) {
    a.enrollStatus = ENROLL_ST_FULL;
    return a;
  }
  engine_.cancel();
  a.enrollFingerPage = page;
  a.enrollStatus = ENROLL_ST_WAIT_FINGER;
  return a;
}

DoorAction DoorCore::cancelEnroll() {
  DoorAction a;
  enroll_.cancel();
  show(a, FB_IDLE, 0);
  a.enrollStatus = ENROLL_ST_IDLE;
  return a;
}

DoorAction DoorCore::clearLockout() {
  DoorAction a;
  engine_.clearLockout();
  show(a, FB_IDLE, 0);
  return a;
}

uint8_t DoorCore::restingFeedback() const {
  switch (enroll_.state()) {
    case ENR_WAIT_BAND: return FB_ENROLL_BAND;
    case ENR_WAIT_FINGER: return FB_ENROLL_FINGER;
    default: return FB_IDLE;
  }
}

const char *DoorCore::enrollStatusNow() const {
  switch (enroll_.state()) {
    case ENR_WAIT_BAND: return ENROLL_ST_WAIT_BAND;
    case ENR_WAIT_FINGER: return ENROLL_ST_WAIT_FINGER;
    default: return ENROLL_ST_IDLE;
  }
}

}  // namespace mb
