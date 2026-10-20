#pragma once
// Door decision core shared by the split controller and the all-in-one
// reader: turns reader events (band, finger, enroll result), exit button,
// remote commands and timers into actions (unlock, feedback state, log
// entry, HA enrollment status, R503 commands).  Pure logic, no Arduino
// headers, so the whole local decision path is unit tested on the host.
// The caller executes the returned DoorAction.

#include <stdint.h>

#include "mb_access.h"
#include "mb_protocol.h"  // FB_* feedback states, ENROLL_* status codes

namespace mb {

struct DoorConfig {
  uint32_t grantedHoldMs = 1500;  // feedback hold for GRANTED
  uint32_t deniedHoldMs = 2000;
  uint32_t enrollHoldMs = 2000;   // ENROLL_OK / ENROLL_FAIL
  bool tamperDenies = true;       // TAMPER_DENIES_ACCESS
};

// HA enrollment sensor values that are not EnrollEvent names
static const char *const ENROLL_ST_IDLE = "idle";
static const char *const ENROLL_ST_WAIT_BAND = "waiting_band";
static const char *const ENROLL_ST_WAIT_FINGER = "waiting_finger";
static const char *const ENROLL_ST_FULL = "full";
static const char *const ENROLL_ST_NO_FP = "no_fingerprint_hw";

struct DoorAction {
  bool unlock = false;           // pulse the strike
  bool feedback = false;         // show fbState on the reader for fbHoldMs (0 = stay)
  uint8_t fbState = FB_IDLE;
  uint32_t fbHoldMs = 0;
  bool resendFeedback = false;   // ack only: repeat the last feedback
  bool log = false;              // add `decision` to the event log / MQTT
  uint8_t kind = EV_BAND;        // EventKind of the log entry
  Decision decision;
  Uid uid;
  uint16_t page = 0;
  EnrollResultEv enroll;         // event != ENR_NONE: an enrollment finished
  const char *enrollStatus = nullptr;  // new HA enrollment sensor value
  int enrollFingerPage = -1;     // >= 0: run the R503 two-touch enrollment into this page
  int deleteFingerPage = -1;     // >= 0: delete this R503 template (orphan)
  bool enrollOk() const {
    return enroll.event == ENR_USER_CREATED || enroll.event == ENR_BAND_ADDED || enroll.event == ENR_FINGER_ADDED;
  }
};

class DoorCore {
 public:
  explicit DoorCore(UserStore &users) : users_(users), engine_(users), enroll_(users) {}
  void setConfig(const DoorConfig &d, const AccessConfig &a, const EnrollConfig &e);

  // Reader capability (HELLO.caps & CAP_FINGERPRINT, or HAS_FINGERPRINT in
  // the all-in-one build).  Losing it cancels a pending finger enrollment.
  DoorAction setFingerHw(bool hw);
  bool fingerHw() const { return engine_.fingerHw(); }
  // Enabled users exist whose policy needs a finger, but there is no sensor.
  bool fingerProblem() const { return engine_.fingerProblem(); }
  // Hatch open / reader offline / link alarm: scans are refused (tamperDenies).
  void setTampered(bool t) { tampered_ = t; }
  bool tampered() const { return tampered_; }

  // Reader events
  DoorAction band(const Uid &uid, uint32_t now);
  DoorAction finger(uint16_t page, uint32_t now);
  DoorAction fingerNoMatch(uint32_t now);
  DoorAction enrollResult(uint16_t page, uint8_t status, uint32_t now);
  // Timers: band->finger window, enrollment timeouts.  Call every loop.
  DoorAction tick(uint32_t now);

  // Local / remote commands
  DoorAction rex();           // exit button: always opens, no feedback
  DoorAction remoteUnlock();  // HA lock entity / {"cmd":"unlock"}
  DoorAction startEnrollBand(int slot, const char *name, uint32_t now);  // slot -1 = new user
  DoorAction startEnrollFinger(int slot, uint32_t now);
  DoorAction cancelEnroll();
  DoorAction clearLockout();

  // What the reader should show after it (re)connects.
  uint8_t restingFeedback() const;
  const char *enrollStatusNow() const;

  AccessEngine &engine() { return engine_; }
  EnrollFlow &enrollFlow() { return enroll_; }

 private:
  DoorAction decide(uint8_t kind, const Decision &d, const Uid *uid, uint16_t page, uint32_t now);
  DoorAction enrollDone(const EnrollResultEv &r);
  static void show(DoorAction &a, uint8_t state, uint32_t holdMs);

  UserStore &users_;
  AccessEngine engine_;
  EnrollFlow enroll_;
  DoorConfig cfg_;
  uint32_t fingerTimeoutMs_ = 8000;
  uint32_t enrollBandTimeoutMs_ = 30000;
  bool tampered_ = false;
};

}  // namespace mb
