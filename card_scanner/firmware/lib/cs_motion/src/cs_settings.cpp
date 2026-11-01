#include "cs_settings.h"

#include <string.h>

namespace cs {

#define S_(k, lo, hi, integer) {#k, &Settings::k, lo, hi, integer}

static const SettingDef DEFS[] = {
    S_(accel, 50, 20000, false),
    S_(home_speed, 1, 50, false),
    S_(elev_speed, 0.5f, 30, false),
    S_(elev_max_mm, 10, 400, false),
    S_(pick_speed, 5, 400, false),
    S_(pick_travel_mm, 5, 150, false),
    S_(feed_speed, 5, 600, false),
    S_(feed_max_mm, 20, 600, false),
    S_(insert_speed, 5, 400, false),
    S_(insert_mm, 0, 200, false),
    S_(insert_max_mm, 10, 400, false),
    S_(reject_mm, 10, 400, false),
    S_(tongue_speed, 2, 200, false),
    S_(tongue_depth_mm, 1, 80, false),
    S_(cur_elev, 100, 1800, true),
    S_(cur_pick, 100, 1800, true),
    S_(cur_feed, 100, 1800, true),
    S_(cur_tongue, 100, 1800, true),
    S_(vac_grip_kpa, 0, 95, false),
    S_(cup_dwell_ms, 0, 5000, true),
    S_(vac_timeout_ms, 50, 20000, true),
    S_(puff_ms, 0, 5000, true),
    S_(jet_ms, 0, 5000, true),
    S_(sleeve_pick_ms, 20, 5000, true),
    S_(sleeve_push_ms, 0, 2000, true),
    S_(servo_ms, 50, 5000, true),
    S_(lift_down_deg, 0, 180, true),
    S_(lift_up_deg, 0, 180, true),
    S_(pusher_rest_deg, 0, 180, true),
    S_(pusher_seat_deg, 0, 180, true),
    S_(pusher_seat_ms, 0, 5000, true),
    S_(pusher_out_deg, 0, 180, true),
    S_(div0_deg, 0, 180, true),
    S_(div1_deg, 0, 180, true),
    S_(div2_deg, 0, 180, true),
    S_(exit_timeout_ms, 100, 60000, true),
};

#undef S_

int settingCount() { return (int)(sizeof(DEFS) / sizeof(DEFS[0])); }

const SettingDef &settingAt(int i) { return DEFS[i]; }

const SettingDef *findSetting(const char *key) {
  if (!key) return nullptr;
  for (const SettingDef &d : DEFS)
    if (!strcmp(d.key, key)) return &d;
  return nullptr;
}

}  // namespace cs
