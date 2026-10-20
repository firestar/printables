#pragma once
// Access policy engine, enrollment state machine and event log.  Pure
// logic driven by events + a millisecond clock, so it is unit tested on the
// host.  No Arduino headers.

#include <stdint.h>

#include "mb_users.h"

namespace mb {

// ---- access decisions -------------------------------------------------------------
struct AccessConfig {
  uint32_t fingerTimeoutMs = 8000;     // band -> finger window (BAND_AND_FINGER)
  uint8_t maxFailures = 5;             // consecutive failures before a lockout
  uint32_t lockoutMs = 30000;          // first lockout; doubles each time
  uint32_t lockoutMaxMs = 15 * 60000;  // cap
};

enum Outcome : uint8_t { OUT_NONE, OUT_GRANT, OUT_DENY, OUT_NEED_FINGER, OUT_LOCKED };

enum Reason : uint8_t {
  WHY_OK,
  WHY_UNKNOWN_BAND,
  WHY_UNKNOWN_FINGER,
  WHY_NO_MATCH,  // R503 found no template
  WHY_DISABLED,
  WHY_WRONG_USER,  // finger belongs to someone else than the band
  WHY_TIMEOUT,     // no finger within fingerTimeoutMs
  WHY_POLICY,      // valid credential, but not enough for this user's policy
  WHY_LOCKOUT,
  WHY_RETRY,     // finger not matched yet, still inside the window
  WHY_TAMPER,    // controller refused: reader hatch open or link lost
  WHY_NO_FP_HW,  // user's policy needs a finger but the reader has no fingerprint sensor
};

struct Decision {
  Outcome outcome = OUT_NONE;
  Reason reason = WHY_OK;
  int slot = -1;  // user involved, -1 if unknown
};

const char *outcomeName(uint8_t o);
const char *reasonName(uint8_t r);

class AccessEngine {
 public:
  AccessEngine(const UserStore &users, const AccessConfig &cfg = AccessConfig()) : users_(users), cfg_(cfg) {}
  void setConfig(const AccessConfig &cfg) { cfg_ = cfg; }
  // false = no fingerprint sensor (reader capability).  Users whose policy
  // needs a finger are then denied with WHY_NO_FP_HW, never let in on the
  // band alone.  Cancels a pending band+finger attempt.
  void setFingerHw(bool hw);
  bool fingerHw() const { return fingerHw_; }
  // True if some enabled user can't get in because there is no finger sensor.
  bool fingerProblem() const;

  Decision onBand(const Uid &uid, uint32_t now);
  Decision onFinger(uint16_t page, uint32_t now);
  Decision onFingerNoMatch(uint32_t now);
  // Call often: expires a pending band+finger attempt.
  Decision tick(uint32_t now);

  bool pending() const { return pendingSlot_ >= 0; }
  int pendingSlot() const { return pendingSlot_; }
  bool lockedOut(uint32_t now) const;
  uint32_t lockoutRemaining(uint32_t now) const;
  uint8_t failures() const { return failures_; }
  void cancel() { pendingSlot_ = -1; }
  void clearLockout();

 private:
  Decision grant(int slot);
  Decision fail(Reason r, int slot, uint32_t now);
  static Decision make(Outcome o, Reason r, int slot);

  const UserStore &users_;
  AccessConfig cfg_;
  int pendingSlot_ = -1;
  uint32_t deadline_ = 0;
  uint8_t failures_ = 0;
  uint8_t lockouts_ = 0;
  bool locked_ = false;
  uint32_t lockUntil_ = 0;
  bool fingerHw_ = true;
};

// ---- enrollment --------------------------------------------------------------------
struct EnrollConfig {
  uint32_t bandTimeoutMs = 30000;    // "enroll next band" waits this long
  uint32_t fingerTimeoutMs = 60000;  // reader-side R503 enrollment (two touches)
  uint8_t defaultPolicy = POLICY_BAND_AND_FINGER;
  uint16_t fingerPages = FINGER_PAGES;
};

enum EnrollState : uint8_t { ENR_IDLE, ENR_WAIT_BAND, ENR_WAIT_FINGER };

enum EnrollEvent : uint8_t {
  ENR_NONE,
  ENR_USER_CREATED,   // new user with the scanned band
  ENR_BAND_ADDED,     // band added to an existing user
  ENR_BAND_KNOWN,     // band already belongs to a user: nothing changed
  ENR_FINGER_ADDED,
  ENR_FINGER_FAILED,  // reader reported an R503 error
  ENR_TIMEOUT,
  ENR_FULL,           // no free user slot / band slot / finger page
};

struct EnrollResultEv {
  EnrollEvent event = ENR_NONE;
  int slot = -1;
  uint16_t page = 0;
};

const char *enrollEventName(uint8_t e);

// EnrollFlow::startFinger() errors
static const int ENROLL_START_FULL = -1;   // bad slot, user has MAX_FINGERS, or the R503 is full
static const int ENROLL_START_NO_FP = -2;  // no fingerprint sensor on this reader

class EnrollFlow {
 public:
  EnrollFlow(UserStore &users, const EnrollConfig &cfg = EnrollConfig()) : users_(users), cfg_(cfg) {}

  // Next unknown band creates a new user called `name` ("" = "User <n>").
  bool startNewUser(const char *name, uint32_t now);
  // Next unknown band is added to an existing user.
  bool startAddBand(int slot, uint32_t now);
  // Picks a free R503 page for `slot`; send ENROLL_FINGER(page) to the
  // reader.  Returns the page or ENROLL_START_FULL / ENROLL_START_NO_FP.
  int startFinger(int slot, uint32_t now);
  void setConfig(const EnrollConfig &cfg) { cfg_ = cfg; }
  // false = no fingerprint sensor: finger enrollment is refused, a pending
  // one is cancelled, and new users get POLICY_BAND_ONLY instead of a
  // finger policy they could never satisfy.
  void setFingerHw(bool hw);
  // Band scans go here first while active(); ENR_NONE = not consumed.
  EnrollResultEv onBand(const Uid &uid, uint32_t now);
  EnrollResultEv onEnrollResult(uint16_t page, uint8_t status, uint32_t now);
  EnrollResultEv tick(uint32_t now);

  bool active() const { return state_ != ENR_IDLE; }
  EnrollState state() const { return state_; }
  int slot() const { return slot_; }
  uint16_t page() const { return page_; }
  void cancel() { state_ = ENR_IDLE; }

 private:
  EnrollResultEv done(EnrollEvent e);
  UserStore &users_;
  EnrollConfig cfg_;
  EnrollState state_ = ENR_IDLE;
  int slot_ = -1;  // -1 in WAIT_BAND = create a new user
  uint16_t page_ = 0;
  uint32_t deadline_ = 0;
  char name_[NAME_LEN] = {0};
  bool fingerHw_ = true;
};

// ---- event log -----------------------------------------------------------------------
enum EventKind : uint8_t { EV_BAND, EV_FINGER, EV_FINGER_NOMATCH, EV_TIMEOUT, EV_REMOTE, EV_REX, EV_TAMPER, EV_LINK, EV_ENROLL };

struct LogEvent {
  uint32_t seq = 0;
  uint32_t t = 0;  // unix time if known, else ms since boot
  uint8_t kind = EV_BAND;
  uint8_t outcome = OUT_NONE;
  uint8_t reason = WHY_OK;
  int8_t slot = -1;
  Uid uid;
  uint16_t page = 0;
};

const char *eventKindName(uint8_t k);

// Fixed-size ring buffer: newest overwrites oldest.
class EventLog {
 public:
  static const int CAP = 32;
  uint32_t add(LogEvent e);  // returns the assigned sequence number
  int size() const { return n_; }
  // i = 0 is the oldest kept event.
  const LogEvent &at(int i) const { return buf_[(head_ + CAP - n_ + i) % CAP]; }
  const LogEvent &latest() const { return at(n_ - 1); }

 private:
  LogEvent buf_[CAP];
  int head_ = 0, n_ = 0;
  uint32_t seq_ = 0;
};

}  // namespace mb
