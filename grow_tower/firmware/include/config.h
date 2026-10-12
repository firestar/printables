#pragma once

#define FW_VERSION "0.1.0"

// ---- pins (see README.md wiring table) --------------------------------------
// Avoids strapping pins (0, 2*, 5, 12, 15), flash pins (6-11) and the
// input-only pins (34-39, no internal pull-ups).  *GPIO2 = onboard LED only.
#define PIN_PUMP 25      // MOSFET module SIG -> 12 V pump, active HIGH
#define PIN_FOG 26       // MOSFET module SIG -> ultrasonic fogger, active HIGH
#define PIN_FAN 27       // MOSFET module SIG -> 12 V duct fan, active HIGH
#define PIN_STEP_IN1 16  // ULN2003 IN1 (28BYJ-48 blue)
#define PIN_STEP_IN2 17  // ULN2003 IN2 (pink)
#define PIN_STEP_IN3 18  // ULN2003 IN3 (yellow)
#define PIN_STEP_IN4 19  // ULN2003 IN4 (orange)
#define PIN_FLOAT 32     // low-water float switch to GND, INPUT_PULLUP
#define PIN_REV 33       // reed / hall switch to GND, one pulse per revolution
#define PIN_ONEWIRE 4    // DS18B20 data, 4.7 k pull-up to 3V3
#define PIN_LED 2        // onboard blue LED

// Float switch polarity.  1 = contact CLOSED (reads LOW) while the water is
// OK, so a broken wire or unplugged float reads as "low water" and the pump
// stays off (fail-safe).  0 = contact closes when the water is low.
#define WATER_OK_WHEN_CLOSED 1

// ---- stepper -------------------------------------------------------------------
// 28BYJ-48 (12 V) on a ULN2003 board, half-step.  Pinion 15T -> ring 128T:
// one tower revolution = 4096 * 128 / 15 = 34953 half-steps.
#define STEPPER_HALF_STEPS_PER_REV 4096
#define PINION_TEETH 15
#define RING_TEETH 128
#define MOTOR_SPEED_DEFAULT 500  // half-steps/s; above ~600 the 28BYJ-48 skips
#define MOTOR_ACCEL 250          // half-steps/s^2
#define STEPPER_TICK_US 250      // stepper service period (esp_timer)

// ---- sensors ------------------------------------------------------------------
#define REV_DEBOUNCE_MS 2000     // a tower revolution takes >= 40 s; ignore re-triggers
#define TEMP_INTERVAL_MS 10000   // DS18B20 read period
#define TEMP_CONVERT_MS 800      // 12-bit conversion time

// ---- network ------------------------------------------------------------------
#define HOSTNAME "growtower"     // mDNS: growtower.local
#define HTTP_PORT 80
#define OTA_PASSWORD ""          // empty = no OTA password
#define PORTAL_TIMEOUT_S 180     // setup AP closes after this if Wi-Fi is saved
#define WIFI_RETRY_S 30          // reconnect attempt interval
#define NTP_SERVER_1 "pool.ntp.org"
#define NTP_SERVER_2 "time.nist.gov"
#define TZ_DEFAULT "UTC0"        // POSIX TZ string, set yours in the web UI

// ---- fail-safe ----------------------------------------------------------------
#define WDT_TIMEOUT_S 30
