#pragma once

// Pump / rotation scheduler.  Pure logic: no Arduino calls, so it builds and
// runs in the [env:native] unit tests.  main.cpp feeds it time, sensor
// readings and the stepper position, and applies the outputs it returns.
//
// Rotation is planned in stepper steps.  The stepper only ever turns forward,
// so its position is also the total distance moved.  Positions are int32 and
// compared by signed difference, so they may wrap.

#include <stdint.h>

namespace sched {

enum RotMode : uint8_t {
  ROT_OFF = 0,
  ROT_INTERVAL = 1,    // rotStepDeg moves, averaging rotDegPerHour
  ROT_CONTINUOUS = 2,  // turn the whole rotation window
};

const char *rotModeName(uint8_t m);
bool rotModeFromString(const char *s, uint8_t &out);

// low-water debounce: trip fast, recover slowly (sloshing / refill)
constexpr uint32_t LOW_WATER_TRIP_S = 5;
constexpr uint32_t LOW_WATER_CLEAR_S = 30;

struct Config {
  // pump cycle, minutes
  uint16_t dayOnMin = 15;
  uint16_t dayOffMin = 15;
  uint16_t nightOnMin = 5;
  uint16_t nightOffMin = 55;
  // day window, minutes after local midnight; start == end means always day
  uint16_t dayStartMin = 6 * 60;
  uint16_t dayEndMin = 20 * 60;
  // rotation
  uint8_t rotMode = ROT_INTERVAL;
  uint16_t rotStepDeg = 15;      // size of one move, degrees of tower rotation
  uint16_t rotDegPerHour = 360;  // average rate in the window (360 = 1 rev/h)
  bool rotAtNight = false;
  // once-per-rev sensor: homing + stall detection
  bool revSensor = false;
  uint16_t stallPct = 130;  // steps without a pulse, % of one tower revolution
  // stepper drive (applied by main.cpp)
  uint16_t motorSpeed = 500;  // half-steps/s
  // manual override auto-timeout
  uint16_t manualTimeoutMin = 10;
  // gearing (compile-time, from config.h; not user settings)
  uint16_t motorStepsPerRev = 4096;  // 28BYJ-48 half-steps per output rev
  uint16_t pinionTeeth = 15;
  uint16_t ringTeeth = 128;
};

// Clamp every field to a sane range.
void sanitize(Config &c);

// minuteOfDay < 0 (clock not synced yet) counts as day.
bool isDay(const Config &c, int minuteOfDay);

// Steps for one tower revolution, rounded (4096 * 128 / 15 = 34953).
int32_t stepsPerTowerRev(const Config &c);
// Steps for `deg` degrees of tower rotation, rounded.  Exact over any
// distance: stepsForDeg(a + b) is not the sum of two rounded parts.
int32_t stepsForDeg(const Config &c, uint32_t deg);
// Seconds between interval moves (for display).
uint32_t moveIntervalS(const Config &c);

struct Inputs {
  uint32_t nowS = 0;         // monotonic seconds since boot
  int minuteOfDay = -1;      // local time, -1 if not synced
  int dayOfYear = -1;        // local day, -1 if not synced
  bool waterLowRaw = false;  // float switch reads "low" right now
  uint32_t revCount = 0;     // total revolution pulses since boot
  int32_t motorPos = 0;      // stepper position, steps
};

enum Manual : uint8_t { MAN_AUTO = 0, MAN_ON = 1, MAN_OFF = 2 };

struct Outputs {
  bool pump = false;
  int32_t motorTarget = 0;  // stepper target position; <= motorPos = stop (decelerate)
  bool motorHalt = false;   // stop at once and de-energise (fault)
};

struct Status {
  bool day = true;
  bool pumpOn = false;
  bool motorBusy = false;      // target is ahead of the position
  bool waterLow = false;       // debounced level
  bool alertLowWater = false;  // latched until clearFaults()
  bool faultStall = false;     // latched until clearFaults(); motor locked off
  uint8_t pumpManual = MAN_AUTO;
  uint8_t motorManual = MAN_AUTO;
  uint32_t pumpManualLeftS = 0;
  uint32_t motorManualLeftS = 0;
  uint32_t pumpPhaseLeftS = 0;  // until the automatic pump cycle flips
  int32_t stepsToGo = 0;
  uint32_t stepsSincePulse = 0;
  uint32_t stepsToday = 0;
  uint32_t stepsTotal = 0;
  bool homed = false;      // a rev pulse has been seen
  bool homing = false;     // turning until the next pulse
  int32_t angleSteps = 0;  // steps past the magnet (valid when homed)
};

class Scheduler {
 public:
  Scheduler() { sanitize(cfg_); }

  // Restarts the pump cycle (with an ON phase).
  void setConfig(const Config &c);
  const Config &config() const { return cfg_; }

  // minutes == 0 uses config().manualTimeoutMin.  MAN_AUTO cancels.
  // Motor ON = turn continuously, OFF = no movement at all.
  void setManualPump(uint8_t mode, uint32_t nowS, uint16_t minutes = 0);
  void setManualMotor(uint8_t mode, uint32_t nowS, uint16_t minutes = 0);

  // One-off moves, applied on the next update().  false = refused.
  bool rotate(uint16_t deg);  // refused while stalled
  bool home();                // turn until the next pulse; needs the sensor

  void clearFaults();

  Outputs update(const Inputs &in);
  const Status &status() const { return st_; }

 private:
  bool autoPump(const Inputs &in, bool day);
  void planMotor(const Inputs &in, bool day, uint32_t dt);
  void expireManual(uint8_t &mode, uint32_t until, uint32_t nowS, uint32_t &left);

  Config cfg_;
  Status st_;
  bool started_ = false;
  uint32_t lastNowS_ = 0;
  // pump cycle
  bool cycleValid_ = false;
  bool cycleDay_ = true;
  uint32_t cycleStartS_ = 0;
  // water
  bool lastRaw_ = false;
  uint32_t rawSinceS_ = 0;
  // motor
  int32_t target_ = 0;
  int32_t lastPos_ = 0;
  uint32_t lastRevSeen_ = 0;
  int lastDoy_ = -1;
  uint64_t credit_ = 0;       // interval budget, degree-seconds per hour
  uint32_t rotDegDone_ = 0;   // degrees planned by interval moves (wraps harmlessly)
  int32_t rotStepsDone_ = 0;  // stepsForDeg(rotDegDone_)
  bool continuous_ = false;
  int32_t jogSteps_ = 0;
  bool homeReq_ = false;
  // manual
  uint32_t pumpManualUntil_ = 0;
  uint32_t motorManualUntil_ = 0;
};

}  // namespace sched
