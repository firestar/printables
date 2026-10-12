#pragma once

// Pump / fogger / fan / rotation scheduler.  Pure logic: no Arduino calls, so
// it builds and runs in the [env:native] unit tests.  main.cpp feeds it time,
// sensor readings and the stepper position, and applies the outputs it returns.
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

enum FeedMode : uint8_t {
  FEED_AERO = 0,  // pump day/night cycle; fogger and fan never on
  FEED_FOG = 1,   // fogger day/night cycle + fan; pump only does short flushes
};

const char *feedModeName(uint8_t m);
bool feedModeFromString(const char *s, uint8_t &out);

// low-water debounce: trip fast, recover slowly (sloshing / refill)
constexpr uint32_t LOW_WATER_TRIP_S = 5;
constexpr uint32_t LOW_WATER_CLEAR_S = 30;

// fogger over-temperature: off above fogMaxTempC, back on at or below max - 1
constexpr float FOG_TEMP_HYST_C = 1.0f;

struct Config {
  // pump cycle, minutes (aero mode)
  uint16_t dayOnMin = 15;
  uint16_t dayOffMin = 15;
  uint16_t nightOnMin = 5;
  uint16_t nightOffMin = 55;
  // feed mode; the rest of this block only applies in FEED_FOG
  uint8_t feedMode = FEED_AERO;
  uint16_t fogDayOnMin = 10;   // fogger cycle, minutes
  uint16_t fogDayOffMin = 5;
  uint16_t fogNightOnMin = 5;
  uint16_t fogNightOffMin = 15;
  uint16_t fanRunOnS = 60;     // fan keeps going after the fogger stops, seconds
  uint16_t fogMaxTempC = 28;   // no fogging above this water temp (DS18B20 needed)
  uint16_t flushOnMin = 2;     // pump flush, minutes, day and night alike
  uint16_t flushOffMin = 118;  // 2 min every 2 h
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
  bool tempValid = false;    // DS18B20 present and read
  float tempC = 0;           // water temperature
};

enum Manual : uint8_t { MAN_AUTO = 0, MAN_ON = 1, MAN_OFF = 2 };

struct Outputs {
  bool pump = false;
  bool fog = false;
  bool fan = false;
  int32_t motorTarget = 0;  // stepper target position; <= motorPos = stop (decelerate)
  bool motorHalt = false;   // stop at once and de-energise (fault)
};

struct Status {
  bool day = true;
  bool pumpOn = false;
  bool fogOn = false;
  bool fanOn = false;
  bool fogTempHold = false;    // water too warm: fogger held off
  bool motorBusy = false;      // target is ahead of the position
  bool waterLow = false;       // debounced level
  bool alertLowWater = false;  // latched until clearFaults()
  bool faultStall = false;     // latched until clearFaults(); motor locked off
  uint8_t pumpManual = MAN_AUTO;
  uint8_t motorManual = MAN_AUTO;
  uint8_t fogManual = MAN_AUTO;
  uint8_t fanManual = MAN_AUTO;
  uint32_t pumpManualLeftS = 0;
  uint32_t motorManualLeftS = 0;
  uint32_t fogManualLeftS = 0;
  uint32_t fanManualLeftS = 0;
  uint32_t pumpPhaseLeftS = 0;  // until the automatic pump cycle flips
  uint32_t fogPhaseLeftS = 0;   // until the automatic fogger cycle flips
  uint32_t fanRunOnLeftS = 0;   // fan run-on after the fogger stopped
  int32_t stepsToGo = 0;
  uint32_t stepsSincePulse = 0;
  uint32_t stepsToday = 0;
  uint32_t stepsTotal = 0;
  bool homed = false;      // a rev pulse has been seen
  bool homing = false;     // turning until the next pulse
  int32_t angleSteps = 0;  // steps past the magnet (valid when homed)
};

// ON/OFF cycle in seconds.  Restarts with an ON phase when `period` changes
// (day <-> night) or after reset().  onS == 0: always off; offS == 0: always on.
struct Cycle {
  bool valid = false;
  bool period = true;
  uint32_t startS = 0;
  void reset() { valid = false; }
  bool run(uint32_t nowS, bool p, uint32_t onS, uint32_t offS, uint32_t &leftS);
};

class Scheduler {
 public:
  Scheduler() { sanitize(cfg_); }

  // Restarts the pump and fogger cycles (with an ON phase).
  void setConfig(const Config &c);
  const Config &config() const { return cfg_; }

  // minutes == 0 uses config().manualTimeoutMin.  MAN_AUTO cancels.
  // Motor ON = turn continuously, OFF = no movement at all.
  // Fog / fan only act in FEED_FOG; low water (and over-temp for the fogger)
  // still wins over manual ON.
  void setManualPump(uint8_t mode, uint32_t nowS, uint16_t minutes = 0);
  void setManualMotor(uint8_t mode, uint32_t nowS, uint16_t minutes = 0);
  void setManualFog(uint8_t mode, uint32_t nowS, uint16_t minutes = 0);
  void setManualFan(uint8_t mode, uint32_t nowS, uint16_t minutes = 0);

  // One-off moves, applied on the next update().  false = refused.
  bool rotate(uint16_t deg);  // refused while stalled
  bool home();                // turn until the next pulse; needs the sensor

  void clearFaults();

  Outputs update(const Inputs &in);
  const Status &status() const { return st_; }

 private:
  bool autoPump(const Inputs &in, bool day);
  void planFog(const Inputs &in, bool day, bool &fog, bool &fan);
  void planMotor(const Inputs &in, bool day, uint32_t dt);
  void setManual(uint8_t mode, uint32_t nowS, uint16_t minutes, uint8_t &st, uint32_t &until,
                 uint32_t &left);
  void expireManual(uint8_t &mode, uint32_t until, uint32_t nowS, uint32_t &left);

  Config cfg_;
  Status st_;
  bool started_ = false;
  uint32_t lastNowS_ = 0;
  // pump / fogger cycles, fan run-on
  Cycle pumpCycle_;
  Cycle fogCycle_;
  bool fogWasOn_ = false;
  uint32_t fanUntilS_ = 0;  // fan run-on ends here
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
  uint32_t fogManualUntil_ = 0;
  uint32_t fanManualUntil_ = 0;
};

}  // namespace sched
