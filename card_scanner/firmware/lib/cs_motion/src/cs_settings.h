#pragma once
// Tunables, settable over the link (`set` / `get`) and persisted in NVS.
// Key names are the wire names and the NVS keys (<= 15 chars).

#include <stdint.h>

namespace cs {

struct Settings {
  // ---- motion: mm/s, mm/s^2, mm ----
  float accel = 1500;
  float home_speed = 10;       // homing seek speed, every axis
  float elev_speed = 6;        // stack raise speed
  float elev_max_mm = 150;     // elevator travel above home
  float pick_speed = 120;
  float pick_travel_mm = 30;   // pick arm stroke: stack -> roller nip (CAD PICK_STROKE: edge 8 mm into the nip)
  float feed_speed = 150;
  float feed_max_mm = 220;     // feed: give up (jam) if scan_stop not hit within this
  float insert_speed = 80;
  float insert_mm = 70;        // sleeve: feed this far after sleeve_mouth trips
  float insert_max_mm = 200;   // sleeve: give up if sleeve_mouth never trips (scan stop -> mouth sensor = 168 mm)
  float reject_mm = 240;       // eject_reject: scan station -> trailing edge past the sleeve entry nip (232 mm)
  float tongue_speed = 60;
  float tongue_depth_mm = 18;  // tongue stroke into the sleeve mouth (CAD: tips -3 -> +15)
  // ---- TMC2209 run current, mA RMS ----
  float cur_elev = 800;
  float cur_pick = 600;
  float cur_feed = 600;
  float cur_tongue = 500;
  // ---- pneumatics ----
  float vac_grip_kpa = 25;     // grip = vacuum >= this.  0 = no sensor: skip the checks
  float cup_dwell_ms = 250;    // minimum time a cup is open before checking the grip
  float vac_timeout_ms = 1500; // grip not reached within this -> pick_fail / sleeve_open_fail
  float puff_ms = 150;         // stack air knife pulse before picking (0 = off)
  float jet_ms = 120;          // sleeve mouth jet pulse
  // ---- sleeve pick (N20 friction wheels: magazine -> platen) ----
  float sleeve_pick_ms = 400;  // max wheel run waiting for sleeve_present
  float sleeve_push_ms = 60;   // wheels keep running this long after sleeve_present: sleeve flush on the fence
  // ---- servos: degrees, settle time ----
  float servo_ms = 350;
  float lift_down_deg = 35;
  float lift_up_deg = 110;
  float pusher_rest_deg = 10;  // pawl at -20 (behind the trailing edge of a 70 mm-in card)
  float pusher_seat_deg = 65;  // pawl at +0.3: card seated in the sleeve (sleeve job)
  float pusher_seat_ms = 400;  // dwell at the seat angle before the tongues retract
  float pusher_out_deg = 160;  // pawl at +36: sleeved card into the exit nip (sort job)
  float div0_deg = 48;         // tray on the servo spline: 90 -/+ 42 deg (CAD DIV_ANGS)
  float div1_deg = 90;
  float div2_deg = 132;
  // ---- timeouts ----
  float exit_timeout_ms = 3000;  // pusher out -> exit beam trip, and trip -> clear
};

struct SettingDef {
  const char *key;
  float Settings::*field;
  float lo, hi;
  bool integer;
};

int settingCount();
const SettingDef &settingAt(int i);
const SettingDef *findSetting(const char *key);

// Persistence backend (NVS on the board, memory in tests).
class SettingsStore {
 public:
  virtual ~SettingsStore() {}
  virtual bool load(const char *key, float &v) = 0;
  virtual void save(const char *key, float v) = 0;
};

}  // namespace cs
