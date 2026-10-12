// Host unit tests for the pure scheduler.  Run: pio test -e native

#include <unity.h>

#include "scheduler.h"

using namespace sched;

void setUp() {}
void tearDown() {}

static const int32_t REV = 34953;  // 4096 * 128 / 15, rounded

// Steps the scheduler one second at a time like the firmware loop would,
// with a simple stepper + tower model: the stepper moves up to `speed` steps
// per second toward the target, and the magnet passes the reed switch once
// per tower revolution unless the tower is jammed.
struct Sim {
  Scheduler s;
  Inputs in;
  Outputs out;
  int32_t speed = 500;   // half-steps per simulated second
  bool jammed = false;   // tower stuck: stepper skips, no rev pulses
  int32_t tower = 0;     // steps the tower really turned
  int32_t nextPulse;     // tower position of the next magnet pass

  explicit Sim(const Config &c = Config(), int32_t magnetAt = 20000) : nextPulse(magnetAt) {
    s.setConfig(c);
    in.minuteOfDay = 12 * 60;  // noon: day
    out = s.update(in);
  }
  void run(uint32_t seconds) {
    for (uint32_t i = 0; i < seconds; i++) {
      in.nowS++;
      int32_t go = out.motorTarget - in.motorPos;
      if (!out.motorHalt && go > 0) {
        int32_t n = go < speed ? go : speed;
        in.motorPos += n;
        if (!jammed) {
          tower += n;
          while (tower >= nextPulse) {
            in.revCount++;
            nextPulse += REV;
          }
        }
      }
      out = s.update(in);
    }
  }
};

static Config noRotation() {
  Config c;
  c.rotMode = ROT_OFF;
  return c;
}

// ---- day / night window -----------------------------------------------------
void test_day_window_normal() {
  Config c;  // 06:00-20:00
  TEST_ASSERT_TRUE(isDay(c, 6 * 60));
  TEST_ASSERT_TRUE(isDay(c, 19 * 60 + 59));
  TEST_ASSERT_FALSE(isDay(c, 20 * 60));
  TEST_ASSERT_FALSE(isDay(c, 5 * 60 + 59));
  TEST_ASSERT_FALSE(isDay(c, 0));
}

void test_day_window_wraps_midnight() {
  Config c;
  c.dayStartMin = 22 * 60;
  c.dayEndMin = 4 * 60;
  TEST_ASSERT_TRUE(isDay(c, 23 * 60));
  TEST_ASSERT_TRUE(isDay(c, 60));
  TEST_ASSERT_FALSE(isDay(c, 12 * 60));
}

void test_unknown_time_is_day() {
  Config c;
  TEST_ASSERT_TRUE(isDay(c, -1));
  c.dayStartMin = c.dayEndMin = 300;  // equal = always day
  TEST_ASSERT_TRUE(isDay(c, 0));
}

// ---- pump cycle -------------------------------------------------------------
void test_day_cycle_timing() {
  Sim sim(noRotation());  // 15 on / 15 off
  TEST_ASSERT_TRUE(sim.out.pump);
  TEST_ASSERT_EQUAL_UINT32(15 * 60, sim.s.status().pumpPhaseLeftS);
  sim.run(15 * 60 - 1);
  TEST_ASSERT_TRUE(sim.out.pump);
  sim.run(1);
  TEST_ASSERT_FALSE(sim.out.pump);
  sim.run(15 * 60 - 1);
  TEST_ASSERT_FALSE(sim.out.pump);
  sim.run(1);
  TEST_ASSERT_TRUE(sim.out.pump);
}

void test_night_cycle_timing() {
  Sim sim(noRotation());
  sim.in.minuteOfDay = 23 * 60;  // night: 5 on / 55 off, restarts with ON
  sim.run(1);
  TEST_ASSERT_FALSE(sim.s.status().day);
  TEST_ASSERT_TRUE(sim.out.pump);
  sim.run(5 * 60 - 1);
  TEST_ASSERT_TRUE(sim.out.pump);
  sim.run(1);
  TEST_ASSERT_FALSE(sim.out.pump);
  sim.run(55 * 60 - 1);
  TEST_ASSERT_FALSE(sim.out.pump);
  sim.run(1);
  TEST_ASSERT_TRUE(sim.out.pump);
}

void test_no_clock_uses_day_cycle() {
  Config c = noRotation();
  Scheduler s;
  s.setConfig(c);
  Inputs in;  // minuteOfDay = -1
  s.update(in);
  TEST_ASSERT_TRUE(s.status().day);
  in.nowS = 15 * 60;
  TEST_ASSERT_FALSE(s.update(in).pump);  // day cycle: off after 15 min
}

void test_zero_off_means_always_on() {
  Config c = noRotation();
  c.dayOffMin = 0;
  Sim sim(c);
  sim.run(3 * 3600);
  TEST_ASSERT_TRUE(sim.out.pump);
  c.dayOnMin = 0;
  sim.s.setConfig(c);
  sim.run(1);
  TEST_ASSERT_FALSE(sim.out.pump);
}

// ---- low water --------------------------------------------------------------
void test_low_water_at_boot_blocks_pump_immediately() {
  Scheduler s;
  s.setConfig(noRotation());
  Inputs in;
  in.waterLowRaw = true;
  TEST_ASSERT_FALSE(s.update(in).pump);
  TEST_ASSERT_TRUE(s.status().alertLowWater);
}

void test_low_water_lockout_and_recovery() {
  Sim sim(noRotation());
  TEST_ASSERT_TRUE(sim.out.pump);
  sim.in.waterLowRaw = true;
  sim.run(LOW_WATER_TRIP_S);  // low must persist a full TRIP_S after first seen
  TEST_ASSERT_TRUE(sim.out.pump);  // debounce
  sim.run(1);
  TEST_ASSERT_FALSE(sim.out.pump);
  TEST_ASSERT_TRUE(sim.s.status().waterLow);
  TEST_ASSERT_TRUE(sim.s.status().alertLowWater);

  // manual ON must not override dry-run protection
  sim.s.setManualPump(MAN_ON, sim.in.nowS);
  sim.run(1);
  TEST_ASSERT_FALSE(sim.out.pump);
  sim.s.setManualPump(MAN_AUTO, sim.in.nowS);

  // brief slosh back to OK does not clear
  sim.in.waterLowRaw = false;
  sim.run(LOW_WATER_CLEAR_S);
  TEST_ASSERT_TRUE(sim.s.status().waterLow);
  sim.run(1);
  TEST_ASSERT_FALSE(sim.s.status().waterLow);
  TEST_ASSERT_TRUE(sim.s.status().alertLowWater);  // latched
  sim.s.clearFaults();
  TEST_ASSERT_FALSE(sim.s.status().alertLowWater);
}

void test_low_water_glitch_ignored() {
  Sim sim(noRotation());
  sim.in.waterLowRaw = true;
  sim.run(2);
  sim.in.waterLowRaw = false;
  sim.run(10);
  TEST_ASSERT_TRUE(sim.out.pump);
  TEST_ASSERT_FALSE(sim.s.status().alertLowWater);
}

// ---- manual override --------------------------------------------------------
void test_manual_override_times_out() {
  Config c = noRotation();
  c.manualTimeoutMin = 10;
  Sim sim(c);
  sim.s.setManualPump(MAN_OFF, sim.in.nowS);
  sim.run(1);
  TEST_ASSERT_FALSE(sim.out.pump);
  TEST_ASSERT_EQUAL_UINT8(MAN_OFF, sim.s.status().pumpManual);
  sim.run(10 * 60 - 2);
  TEST_ASSERT_EQUAL_UINT8(MAN_OFF, sim.s.status().pumpManual);
  sim.run(1);
  TEST_ASSERT_EQUAL_UINT8(MAN_AUTO, sim.s.status().pumpManual);
}

void test_manual_motor_off_then_on() {
  Sim sim;  // interval mode
  sim.s.setManualMotor(MAN_OFF, sim.in.nowS);  // 10 min hold
  sim.run(600);
  TEST_ASSERT_EQUAL_INT32(0, sim.in.motorPos);  // no interval moves while held
  TEST_ASSERT_EQUAL_UINT8(MAN_AUTO, sim.s.status().motorManual);

  sim.s.setManualMotor(MAN_ON, sim.in.nowS, 1);  // turn for 1 min
  sim.run(10);
  TEST_ASSERT_EQUAL_INT32(4500, sim.in.motorPos);  // commands apply from the next update
  sim.run(50);  // times out: decelerate and stop
  TEST_ASSERT_FALSE(sim.s.status().motorBusy);
  int32_t stopped = sim.in.motorPos;
  TEST_ASSERT_EQUAL_INT32(59 * 500, stopped);
  sim.run(5);
  TEST_ASSERT_EQUAL_INT32(stopped, sim.in.motorPos);
}

// ---- rotation ---------------------------------------------------------------
void test_gearing() {
  Config c;
  TEST_ASSERT_EQUAL_INT32(REV, stepsPerTowerRev(c));
  TEST_ASSERT_EQUAL_INT32(1456, stepsForDeg(c, 15));  // 1456.36
  TEST_ASSERT_EQUAL_INT32(2913, stepsForDeg(c, 30));  // 2912.71
  TEST_ASSERT_EQUAL_INT32(8738, stepsForDeg(c, 90));
  TEST_ASSERT_EQUAL_INT32(524288, stepsForDeg(c, 5400));  // 15 revs = 4096 * 128 exactly
  TEST_ASSERT_EQUAL_UINT32(150, moveIntervalS(c));       // 15 deg at 360 deg/h
}

void test_interval_one_rev_per_hour() {
  Sim sim;  // 15 deg moves, 360 deg/h
  TEST_ASSERT_EQUAL_INT32(0, sim.out.motorTarget);
  sim.run(149);
  TEST_ASSERT_EQUAL_INT32(0, sim.out.motorTarget);
  sim.run(1);
  TEST_ASSERT_EQUAL_INT32(1456, sim.out.motorTarget);
  sim.run(5);
  TEST_ASSERT_EQUAL_INT32(1456, sim.in.motorPos);
  TEST_ASSERT_FALSE(sim.s.status().motorBusy);  // idle between moves: coils off
  sim.run(3600 - 155);
  TEST_ASSERT_EQUAL_INT32(REV, sim.out.motorTarget);  // 24 moves = exactly 1 rev
  sim.run(100);
  TEST_ASSERT_EQUAL_INT32(REV, sim.in.motorPos);
  TEST_ASSERT_EQUAL_UINT32(REV, sim.s.status().stepsTotal);
}

void test_interval_no_drift_over_many_revs() {
  Sim sim;
  sim.run(15 * 3600 + 100);  // window never closes in the sim
  Config c;
  TEST_ASSERT_EQUAL_INT32(stepsForDeg(c, 15 * 360), sim.in.motorPos);
  sim.run(3600);
  TEST_ASSERT_EQUAL_INT32(stepsForDeg(c, 16 * 360), sim.in.motorPos);
}

void test_rotation_off_at_night_unless_enabled() {
  Config c;
  Sim sim(c);
  sim.in.minuteOfDay = 22 * 60;
  sim.run(3600);
  TEST_ASSERT_EQUAL_INT32(0, sim.in.motorPos);
  c.rotAtNight = true;
  sim.s.setConfig(c);
  sim.run(150);
  TEST_ASSERT_EQUAL_INT32(1456, sim.out.motorTarget);
}

void test_continuous_and_soft_stop() {
  Config c;
  c.rotMode = ROT_CONTINUOUS;
  Sim sim(c);
  sim.run(10);
  TEST_ASSERT_EQUAL_INT32(5000, sim.in.motorPos);
  TEST_ASSERT_TRUE(sim.s.status().motorBusy);
  sim.in.minuteOfDay = 22 * 60;  // window closes
  sim.run(1);
  TEST_ASSERT_FALSE(sim.s.status().motorBusy);
  int32_t stopped = sim.in.motorPos;
  sim.run(5);
  TEST_ASSERT_EQUAL_INT32(stopped, sim.in.motorPos);
}

void test_rotate_jog() {
  Sim sim(noRotation());
  TEST_ASSERT_TRUE(sim.s.rotate(90));
  sim.run(1);
  TEST_ASSERT_EQUAL_INT32(8738, sim.out.motorTarget);
  sim.run(20);
  TEST_ASSERT_EQUAL_INT32(8738, sim.in.motorPos);
}

// ---- rev sensor: homing + stall ---------------------------------------------
void test_home_stops_at_magnet() {
  Config c = noRotation();
  TEST_ASSERT_FALSE(Sim(c).s.home());  // needs the sensor
  c.revSensor = true;
  Sim sim(c, 10000);
  TEST_ASSERT_TRUE(sim.s.home());
  sim.run(20);  // first second: command not applied yet, then 500/s
  TEST_ASSERT_TRUE(sim.s.status().homing);
  TEST_ASSERT_FALSE(sim.s.status().homed);
  sim.run(1);  // reaches 10000: pulse
  TEST_ASSERT_FALSE(sim.s.status().homing);
  TEST_ASSERT_TRUE(sim.s.status().homed);
  TEST_ASSERT_EQUAL_INT32(0, sim.s.status().angleSteps);
  sim.run(5);
  TEST_ASSERT_EQUAL_INT32(10000, sim.in.motorPos);
  sim.s.rotate(90);
  sim.run(20);
  TEST_ASSERT_EQUAL_INT32(8738, sim.s.status().angleSteps);
}

void test_stall_jammed_continuous() {
  Config c;
  c.rotMode = ROT_CONTINUOUS;
  c.revSensor = true;  // stall at 130 % of 34953 = 45438 steps
  Sim sim(c);
  sim.jammed = true;
  sim.run(90);
  TEST_ASSERT_FALSE(sim.s.status().faultStall);
  sim.run(1);
  TEST_ASSERT_TRUE(sim.s.status().faultStall);
  TEST_ASSERT_TRUE(sim.out.motorHalt);
  int32_t stopped = sim.in.motorPos;
  sim.run(5);
  TEST_ASSERT_EQUAL_INT32(stopped, sim.in.motorPos);

  // nothing restarts a stalled motor
  sim.s.setManualMotor(MAN_ON, sim.in.nowS);
  TEST_ASSERT_FALSE(sim.s.rotate(90));
  TEST_ASSERT_FALSE(sim.s.home());
  sim.run(5);
  TEST_ASSERT_EQUAL_INT32(stopped, sim.in.motorPos);

  sim.s.clearFaults();
  sim.run(2);
  TEST_ASSERT_FALSE(sim.s.status().faultStall);
  TEST_ASSERT_EQUAL_INT32(stopped + 500, sim.in.motorPos);
}

void test_stall_counts_across_interval_moves() {
  Config c;
  c.revSensor = true;
  Sim sim(c);
  sim.jammed = true;
  sim.run(150 * 31 + 10);  // 31 moves = 465 deg = 45147 steps < 45438
  TEST_ASSERT_FALSE(sim.s.status().faultStall);
  sim.run(150);  // 32nd move crosses the limit
  TEST_ASSERT_TRUE(sim.s.status().faultStall);
  TEST_ASSERT_TRUE(sim.out.motorHalt);
}

void test_pulses_prevent_stall() {
  Config c;
  c.rotMode = ROT_CONTINUOUS;
  c.revSensor = true;
  Sim sim(c, 20000);
  sim.run(3600);  // 1.8 M steps, ~51 revolutions
  TEST_ASSERT_FALSE(sim.s.status().faultStall);
  TEST_ASSERT_TRUE(sim.s.status().homed);
  TEST_ASSERT_EQUAL_UINT32(51, sim.in.revCount);
}

void test_no_stall_without_sensor() {
  Config c;
  c.rotMode = ROT_CONTINUOUS;
  Sim sim(c);
  sim.jammed = true;
  sim.run(3600);
  TEST_ASSERT_FALSE(sim.s.status().faultStall);
  TEST_ASSERT_TRUE(sim.s.status().motorBusy);
}

// ---- config -----------------------------------------------------------------
void test_sanitize_and_names() {
  Config c;
  c.rotMode = 9;
  c.motorSpeed = 5000;
  c.dayStartMin = 5000;
  c.stallPct = 50;
  c.rotStepDeg = 0;
  c.pinionTeeth = 0;
  sanitize(c);
  TEST_ASSERT_EQUAL_UINT8(ROT_OFF, c.rotMode);
  TEST_ASSERT_EQUAL_UINT16(800, c.motorSpeed);
  TEST_ASSERT_EQUAL_UINT16(1439, c.dayStartMin);
  TEST_ASSERT_EQUAL_UINT16(110, c.stallPct);
  TEST_ASSERT_EQUAL_UINT16(1, c.rotStepDeg);
  TEST_ASSERT_EQUAL_UINT16(1, c.pinionTeeth);
  uint8_t m = 0;
  TEST_ASSERT_TRUE(rotModeFromString("continuous", m));
  TEST_ASSERT_EQUAL_UINT8(ROT_CONTINUOUS, m);
  TEST_ASSERT_FALSE(rotModeFromString("revs", m));
  TEST_ASSERT_EQUAL_STRING("interval", rotModeName(ROT_INTERVAL));
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_day_window_normal);
  RUN_TEST(test_day_window_wraps_midnight);
  RUN_TEST(test_unknown_time_is_day);
  RUN_TEST(test_day_cycle_timing);
  RUN_TEST(test_night_cycle_timing);
  RUN_TEST(test_no_clock_uses_day_cycle);
  RUN_TEST(test_zero_off_means_always_on);
  RUN_TEST(test_low_water_at_boot_blocks_pump_immediately);
  RUN_TEST(test_low_water_lockout_and_recovery);
  RUN_TEST(test_low_water_glitch_ignored);
  RUN_TEST(test_manual_override_times_out);
  RUN_TEST(test_manual_motor_off_then_on);
  RUN_TEST(test_gearing);
  RUN_TEST(test_interval_one_rev_per_hour);
  RUN_TEST(test_interval_no_drift_over_many_revs);
  RUN_TEST(test_rotation_off_at_night_unless_enabled);
  RUN_TEST(test_continuous_and_soft_stop);
  RUN_TEST(test_rotate_jog);
  RUN_TEST(test_home_stops_at_magnet);
  RUN_TEST(test_stall_jammed_continuous);
  RUN_TEST(test_stall_counts_across_interval_moves);
  RUN_TEST(test_pulses_prevent_stall);
  RUN_TEST(test_no_stall_without_sensor);
  RUN_TEST(test_sanitize_and_names);
  return UNITY_END();
}
