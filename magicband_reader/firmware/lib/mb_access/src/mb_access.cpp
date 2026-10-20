#include "mb_access.h"

#include <stdio.h>
#include <string.h>

namespace mb {

namespace {
inline bool reached(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }
}  // namespace

const char *outcomeName(uint8_t o) {
  switch (o) {
    case OUT_NONE: return "none";
    case OUT_GRANT: return "granted";
    case OUT_DENY: return "denied";
    case OUT_NEED_FINGER: return "need_finger";
    case OUT_LOCKED: return "locked_out";
  }
  return "?";
}

const char *reasonName(uint8_t r) {
  switch (r) {
    case WHY_OK: return "ok";
    case WHY_UNKNOWN_BAND: return "unknown_band";
    case WHY_UNKNOWN_FINGER: return "unknown_finger";
    case WHY_NO_MATCH: return "no_match";
    case WHY_DISABLED: return "disabled";
    case WHY_WRONG_USER: return "wrong_user";
    case WHY_TIMEOUT: return "timeout";
    case WHY_POLICY: return "policy";
    case WHY_LOCKOUT: return "lockout";
    case WHY_RETRY: return "retry";
    case WHY_TAMPER: return "tamper";
    case WHY_NO_FP_HW: return "no_fp_hw";
  }
  return "?";
}

// ---- AccessEngine ---------------------------------------------------------------------
Decision AccessEngine::make(Outcome o, Reason r, int slot) {
  Decision d;
  d.outcome = o;
  d.reason = r;
  d.slot = slot;
  return d;
}

bool AccessEngine::lockedOut(uint32_t now) const { return locked_ && !reached(now, lockUntil_); }

uint32_t AccessEngine::lockoutRemaining(uint32_t now) const { return lockedOut(now) ? lockUntil_ - now : 0; }

void AccessEngine::clearLockout() {
  locked_ = false;
  failures_ = 0;
  lockouts_ = 0;
}

void AccessEngine::setFingerHw(bool hw) {
  fingerHw_ = hw;
  if (!hw) pendingSlot_ = -1;
}

bool AccessEngine::fingerProblem() const {
  if (fingerHw_) return false;
  for (int i = 0; i < MAX_USERS; i++) {
    User u;
    if (users_.load(i, u) && u.enabled && u.policy != POLICY_BAND_ONLY) return true;
  }
  return false;
}

Decision AccessEngine::grant(int slot) {
  pendingSlot_ = -1;
  failures_ = 0;
  lockouts_ = 0;
  return make(OUT_GRANT, WHY_OK, slot);
}

Decision AccessEngine::fail(Reason r, int slot, uint32_t now) {
  pendingSlot_ = -1;
  if (++failures_ >= cfg_.maxFailures) {
    uint32_t ms = cfg_.lockoutMs;
    for (uint8_t i = 0; i < lockouts_ && ms < cfg_.lockoutMaxMs; i++) ms *= 2;
    if (ms > cfg_.lockoutMaxMs) ms = cfg_.lockoutMaxMs;
    if (lockouts_ < 31) lockouts_++;
    failures_ = 0;
    locked_ = true;
    lockUntil_ = now + ms;
    return make(OUT_LOCKED, r, slot);
  }
  return make(OUT_DENY, r, slot);
}

Decision AccessEngine::onBand(const Uid &uid, uint32_t now) {
  if (lockedOut(now)) return make(OUT_LOCKED, WHY_LOCKOUT, -1);
  int slot = users_.findByUid(uid);
  User u;
  if (slot < 0 || !users_.load(slot, u)) return fail(WHY_UNKNOWN_BAND, -1, now);
  if (!u.enabled) return fail(WHY_DISABLED, slot, now);
  if (u.policy != POLICY_BAND_ONLY && !fingerHw_) {
    // Configuration problem, not an attack: deny without counting a failure,
    // and never fall back to band-only.
    pendingSlot_ = -1;
    return make(OUT_DENY, WHY_NO_FP_HW, slot);
  }
  switch (u.policy) {
    case POLICY_BAND_ONLY:
      return grant(slot);
    case POLICY_BAND_AND_FINGER:
      pendingSlot_ = slot;  // a new band replaces an older pending one
      deadline_ = now + cfg_.fingerTimeoutMs;
      return make(OUT_NEED_FINGER, WHY_OK, slot);
    default:  // FINGER_ONLY: the band is valid, just not used. Not a failure.
      pendingSlot_ = -1;
      return make(OUT_DENY, WHY_POLICY, slot);
  }
}

Decision AccessEngine::onFinger(uint16_t page, uint32_t now) {
  if (lockedOut(now)) return make(OUT_LOCKED, WHY_LOCKOUT, -1);
  if (!fingerHw_) return make(OUT_DENY, WHY_NO_FP_HW, -1);  // a reader without R503 cannot send this
  Decision t = tick(now);
  if (t.outcome != OUT_NONE) return t;  // the window closed before the finger arrived
  int slot = users_.findByFinger(page);
  User u;
  bool known = slot >= 0 && users_.load(slot, u);
  if (pending()) {
    int want = pendingSlot_;
    if (!known) return fail(WHY_UNKNOWN_FINGER, want, now);
    if (slot != want) return fail(WHY_WRONG_USER, want, now);
    if (!u.enabled) return fail(WHY_DISABLED, slot, now);
    return grant(slot);
  }
  if (!known) return fail(WHY_UNKNOWN_FINGER, -1, now);
  if (!u.enabled) return fail(WHY_DISABLED, slot, now);
  if (u.policy == POLICY_FINGER_ONLY) return grant(slot);
  return make(OUT_DENY, WHY_POLICY, slot);  // band required first; not a failure
}

Decision AccessEngine::onFingerNoMatch(uint32_t now) {
  if (lockedOut(now)) return make(OUT_LOCKED, WHY_LOCKOUT, -1);
  if (!fingerHw_) return make(OUT_DENY, WHY_NO_FP_HW, -1);
  Decision t = tick(now);
  if (t.outcome != OUT_NONE) return t;
  if (pending()) {
    int slot = pendingSlot_;
    Decision d = fail(WHY_NO_MATCH, slot, now);
    if (d.outcome == OUT_LOCKED) return d;
    pendingSlot_ = slot;  // let them try again inside the same window
    return make(OUT_NEED_FINGER, WHY_RETRY, slot);
  }
  return fail(WHY_NO_MATCH, -1, now);
}

Decision AccessEngine::tick(uint32_t now) {
  if (locked_ && reached(now, lockUntil_)) locked_ = false;
  if (pending() && reached(now, deadline_)) return fail(WHY_TIMEOUT, pendingSlot_, now);
  return Decision();
}

// ---- EnrollFlow -------------------------------------------------------------------------
const char *enrollEventName(uint8_t e) {
  switch (e) {
    case ENR_NONE: return "none";
    case ENR_USER_CREATED: return "user_created";
    case ENR_BAND_ADDED: return "band_added";
    case ENR_BAND_KNOWN: return "band_known";
    case ENR_FINGER_ADDED: return "finger_added";
    case ENR_FINGER_FAILED: return "finger_failed";
    case ENR_TIMEOUT: return "timeout";
    case ENR_FULL: return "full";
  }
  return "?";
}

EnrollResultEv EnrollFlow::done(EnrollEvent e) {
  EnrollResultEv r;
  r.event = e;
  r.slot = slot_;
  r.page = page_;
  state_ = ENR_IDLE;
  return r;
}

bool EnrollFlow::startNewUser(const char *name, uint32_t now) {
  if (users_.freeSlot() < 0) return false;
  strncpy(name_, name ? name : "", NAME_LEN - 1);
  name_[NAME_LEN - 1] = 0;
  slot_ = -1;
  state_ = ENR_WAIT_BAND;
  deadline_ = now + cfg_.bandTimeoutMs;
  return true;
}

bool EnrollFlow::startAddBand(int slot, uint32_t now) {
  User u;
  if (!users_.load(slot, u) || u.nBands >= MAX_BANDS) return false;
  slot_ = slot;
  state_ = ENR_WAIT_BAND;
  deadline_ = now + cfg_.bandTimeoutMs;
  return true;
}

int EnrollFlow::startFinger(int slot, uint32_t now) {
  if (!fingerHw_) return ENROLL_START_NO_FP;
  User u;
  if (!users_.load(slot, u) || u.nFingers >= MAX_FINGERS) return ENROLL_START_FULL;
  int page = users_.freeFingerPage(cfg_.fingerPages);
  if (page < 0) return ENROLL_START_FULL;
  slot_ = slot;
  page_ = (uint16_t)page;
  state_ = ENR_WAIT_FINGER;
  deadline_ = now + cfg_.fingerTimeoutMs;
  return page;
}

void EnrollFlow::setFingerHw(bool hw) {
  fingerHw_ = hw;
  if (!hw && state_ == ENR_WAIT_FINGER) state_ = ENR_IDLE;
}

EnrollResultEv EnrollFlow::onBand(const Uid &uid, uint32_t now) {
  if (state_ != ENR_WAIT_BAND) return EnrollResultEv();
  EnrollResultEv t = tick(now);
  if (t.event != ENR_NONE) return t;
  int owner = users_.findByUid(uid);
  if (owner >= 0) {
    int keep = slot_;
    slot_ = owner;
    EnrollResultEv r = done(ENR_BAND_KNOWN);
    slot_ = keep;
    return r;
  }
  if (slot_ >= 0) return done(users_.addBand(slot_, uid) ? ENR_BAND_ADDED : ENR_FULL);
  int slot = users_.freeSlot();
  if (slot < 0) return done(ENR_FULL);
  User u;
  if (name_[0]) {
    u.setName(name_);
  } else {
    char n[NAME_LEN];
    snprintf(n, sizeof(n), "User %d", slot + 1);
    u.setName(n);
  }
  u.policy = fingerHw_ ? cfg_.defaultPolicy : (uint8_t)POLICY_BAND_ONLY;
  u.bands[0] = uid;
  u.nBands = 1;
  slot_ = slot;
  return done(users_.save(slot, u) ? ENR_USER_CREATED : ENR_FULL);
}

EnrollResultEv EnrollFlow::onEnrollResult(uint16_t page, uint8_t status, uint32_t now) {
  if (state_ != ENR_WAIT_FINGER || page != page_) return EnrollResultEv();
  EnrollResultEv t = tick(now);
  if (t.event != ENR_NONE) return t;
  if (status != 0) return done(ENR_FINGER_FAILED);
  return done(users_.addFinger(slot_, page_) ? ENR_FINGER_ADDED : ENR_FULL);
}

EnrollResultEv EnrollFlow::tick(uint32_t now) {
  if (state_ != ENR_IDLE && reached(now, deadline_)) return done(ENR_TIMEOUT);
  return EnrollResultEv();
}

// ---- EventLog ---------------------------------------------------------------------------
const char *eventKindName(uint8_t k) {
  switch (k) {
    case EV_BAND: return "band";
    case EV_FINGER: return "finger";
    case EV_FINGER_NOMATCH: return "finger_nomatch";
    case EV_TIMEOUT: return "timeout";
    case EV_REMOTE: return "remote";
    case EV_REX: return "exit_button";
    case EV_TAMPER: return "tamper";
    case EV_LINK: return "link";
    case EV_ENROLL: return "enroll";
  }
  return "?";
}

uint32_t EventLog::add(LogEvent e) {
  e.seq = ++seq_;
  buf_[head_] = e;
  head_ = (head_ + 1) % CAP;
  if (n_ < CAP) n_++;
  return e.seq;
}

}  // namespace mb
