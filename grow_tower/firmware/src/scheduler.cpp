#include "scheduler.h"

#include <string.h>

namespace sched {

static const char *const ROT_NAMES[] = {"off", "interval", "continuous"};

const char *rotModeName(uint8_t m) { return m <= ROT_CONTINUOUS ? ROT_NAMES[m] : "off"; }

bool rotModeFromString(const char *s, uint8_t &out) {
  for (uint8_t i = 0; i <= ROT_CONTINUOUS; i++) {
    if (strcmp(s, ROT_NAMES[i]) == 0) {
      out = i;
      return true;
    }
  }
  return false;
}

template <typename T>
static void clampField(T &v, T lo, T hi) {
  if (v < lo) v = lo;
  if (v > hi) v = hi;
}

void sanitize(Config &c) {
  clampField<uint16_t>(c.dayOnMin, 0, 1440);
  clampField<uint16_t>(c.dayOffMin, 0, 1440);
  clampField<uint16_t>(c.nightOnMin, 0, 1440);
  clampField<uint16_t>(c.nightOffMin, 0, 1440);
  clampField<uint16_t>(c.dayStartMin, 0, 1439);
  clampField<uint16_t>(c.dayEndMin, 0, 1439);
  if (c.rotMode > ROT_CONTINUOUS) c.rotMode = ROT_OFF;
  clampField<uint16_t>(c.rotStepDeg, 1, 360);
  clampField<uint16_t>(c.rotDegPerHour, 1, 3600);
  clampField<uint16_t>(c.stallPct, 110, 300);
  clampField<uint16_t>(c.motorSpeed, 50, 800);
  clampField<uint16_t>(c.manualTimeoutMin, 1, 240);
  if (c.motorStepsPerRev == 0) c.motorStepsPerRev = 4096;
  if (c.pinionTeeth == 0) c.pinionTeeth = 1;
  if (c.ringTeeth == 0) c.ringTeeth = 1;
}

bool isDay(const Config &c, int minuteOfDay) {
  if (minuteOfDay < 0) return true;  // no clock yet: use the day cycle
  if (c.dayStartMin == c.dayEndMin) return true;
  if (c.dayStartMin < c.dayEndMin)
    return minuteOfDay >= c.dayStartMin && minuteOfDay < c.dayEndMin;
  return minuteOfDay >= c.dayStartMin || minuteOfDay < c.dayEndMin;  // wraps midnight
}

int32_t stepsForDeg(const Config &c, uint32_t deg) {
  uint64_t num = (uint64_t)deg * c.motorStepsPerRev * c.ringTeeth;
  uint64_t den = 360ULL * c.pinionTeeth;
  return (int32_t)((num + den / 2) / den);
}

int32_t stepsPerTowerRev(const Config &c) { return stepsForDeg(c, 360); }

uint32_t moveIntervalS(const Config &c) {
  return (uint32_t)c.rotStepDeg * 3600 / c.rotDegPerHour;
}

static int32_t ahead(int32_t target, int32_t pos) { return (int32_t)((uint32_t)target - (uint32_t)pos); }

void Scheduler::setConfig(const Config &c) {
  cfg_ = c;
  sanitize(cfg_);
  cycleValid_ = false;
}

void Scheduler::setManualPump(uint8_t mode, uint32_t nowS, uint16_t minutes) {
  if (mode > MAN_OFF) return;
  uint32_t m = minutes ? minutes : cfg_.manualTimeoutMin;
  st_.pumpManual = mode;
  pumpManualUntil_ = nowS + m * 60;
  st_.pumpManualLeftS = mode == MAN_AUTO ? 0 : m * 60;
}

void Scheduler::setManualMotor(uint8_t mode, uint32_t nowS, uint16_t minutes) {
  if (mode > MAN_OFF) return;
  uint32_t m = minutes ? minutes : cfg_.manualTimeoutMin;
  st_.motorManual = mode;
  motorManualUntil_ = nowS + m * 60;
  st_.motorManualLeftS = mode == MAN_AUTO ? 0 : m * 60;
}

bool Scheduler::rotate(uint16_t deg) {
  if (st_.faultStall || deg == 0) return false;
  jogSteps_ += stepsForDeg(cfg_, deg);
  return true;
}

bool Scheduler::home() {
  if (!cfg_.revSensor || st_.faultStall) return false;
  homeReq_ = true;
  return true;
}

void Scheduler::clearFaults() {
  st_.alertLowWater = st_.waterLow;  // stays set while the tank is still low
  st_.faultStall = false;
  st_.stepsSincePulse = 0;
}

void Scheduler::expireManual(uint8_t &mode, uint32_t until, uint32_t nowS, uint32_t &left) {
  if (mode == MAN_AUTO || (int32_t)(until - nowS) <= 0) {
    mode = MAN_AUTO;
    left = 0;
    return;
  }
  left = until - nowS;
}

bool Scheduler::autoPump(const Inputs &in, bool day) {
  if (!cycleValid_ || day != cycleDay_) {  // new cycle starts with an ON phase
    cycleValid_ = true;
    cycleDay_ = day;
    cycleStartS_ = in.nowS;
  }
  uint32_t onS = (uint32_t)(day ? cfg_.dayOnMin : cfg_.nightOnMin) * 60;
  uint32_t offS = (uint32_t)(day ? cfg_.dayOffMin : cfg_.nightOffMin) * 60;
  if (onS == 0 || offS == 0) {
    st_.pumpPhaseLeftS = 0;
    return onS > 0;
  }
  uint32_t period = onS + offS;
  uint32_t pos = (in.nowS - cycleStartS_) % period;
  if (pos < onS) {
    st_.pumpPhaseLeftS = onS - pos;
    return true;
  }
  st_.pumpPhaseLeftS = period - pos;
  return false;
}

void Scheduler::planMotor(const Inputs &in, bool day, uint32_t dt) {
  const int32_t pos = in.motorPos;
  const int32_t rev = stepsPerTowerRev(cfg_);
  const bool window = day || cfg_.rotAtNight;
  const uint8_t man = st_.motorManual;

  // after a decelerating stop the motor coasts past the target: never go back
  if (ahead(target_, pos) < 0) target_ = pos;

  if (man == MAN_OFF) {
    target_ = pos;
    credit_ = 0;
    jogSteps_ = 0;
    homeReq_ = st_.homing = false;
    continuous_ = false;
    return;
  }

  // interval moves: earn credit while in the window, spend it in rotStepDeg moves
  if (man == MAN_AUTO && cfg_.rotMode == ROT_INTERVAL && window) {
    const uint64_t cost = (uint64_t)cfg_.rotStepDeg * 3600;
    credit_ += (uint64_t)dt * cfg_.rotDegPerHour;
    while (credit_ >= cost) {
      credit_ -= cost;
      rotDegDone_ += cfg_.rotStepDeg;
      int32_t total = stepsForDeg(cfg_, rotDegDone_);
      target_ += total - rotStepsDone_;
      rotStepsDone_ = total;
      // stay small: steps for 360 * pinionTeeth degrees are a whole number
      const uint32_t period = 360u * cfg_.pinionTeeth;
      if (rotDegDone_ >= period) {
        rotDegDone_ -= period;
        rotStepsDone_ -= stepsForDeg(cfg_, period);
      }
    }
    // don't let missed moves pile up into a long run
    if (ahead(target_, pos) > rev) target_ = pos + rev;
  } else {
    credit_ = 0;
  }

  if (jogSteps_ > 0) {
    target_ += jogSteps_;
    jogSteps_ = 0;
  }
  if (homeReq_) {
    homeReq_ = false;
    st_.homing = true;
    if (ahead(target_, pos) < 2 * rev) target_ = pos + 2 * rev;  // stall check ends it if no pulse
  }

  bool cont = man == MAN_ON || (man == MAN_AUTO && cfg_.rotMode == ROT_CONTINUOUS && window);
  if (cont) {
    const int32_t lead = rev / 8;  // keep the target ahead while turning
    if (ahead(target_, pos) < lead) target_ = pos + lead;
  } else if (continuous_ && !st_.homing) {
    target_ = pos;  // continuous run ended: decelerate and stop
  }
  continuous_ = cont;
}

Outputs Scheduler::update(const Inputs &in) {
  const uint32_t now = in.nowS;
  if (!started_) {
    started_ = true;
    lastNowS_ = now;
    lastRaw_ = in.waterLowRaw;
    rawSinceS_ = now;
    st_.waterLow = in.waterLowRaw;  // trust the first reading: no dry run at boot
    lastRevSeen_ = in.revCount;
    lastDoy_ = in.dayOfYear;
    lastPos_ = target_ = in.motorPos;
  }
  const uint32_t dt = now - lastNowS_;
  lastNowS_ = now;

  // water level, debounced with hysteresis
  if (in.waterLowRaw != lastRaw_) {
    lastRaw_ = in.waterLowRaw;
    rawSinceS_ = now;
  }
  if (lastRaw_ != st_.waterLow &&
      now - rawSinceS_ >= (lastRaw_ ? LOW_WATER_TRIP_S : LOW_WATER_CLEAR_S))
    st_.waterLow = lastRaw_;
  if (st_.waterLow) st_.alertLowWater = true;

  // distance moved and revolution pulses
  int32_t moved = ahead(in.motorPos, lastPos_);
  if (moved < 0) moved = 0;
  lastPos_ = in.motorPos;
  const int32_t rev = stepsPerTowerRev(cfg_);
  if (in.dayOfYear >= 0 && in.dayOfYear != lastDoy_) {
    lastDoy_ = in.dayOfYear;
    st_.stepsToday = 0;
  }
  st_.stepsToday += moved;
  st_.stepsTotal += moved;

  const bool pulse = in.revCount != lastRevSeen_;
  lastRevSeen_ = in.revCount;
  if (!cfg_.revSensor) {
    st_.stepsSincePulse = 0;
    st_.homed = st_.homing = false;
    homeReq_ = false;
  } else if (pulse) {
    st_.stepsSincePulse = 0;
    st_.homed = true;
    st_.angleSteps = 0;
    if (st_.homing) {
      st_.homing = false;
      target_ = in.motorPos;  // found the magnet: stop here
    }
  } else {
    st_.stepsSincePulse += moved;
    st_.angleSteps = (st_.angleSteps + moved) % rev;
  }

  const bool day = isDay(cfg_, in.minuteOfDay);
  st_.day = day;
  expireManual(st_.pumpManual, pumpManualUntil_, now, st_.pumpManualLeftS);
  expireManual(st_.motorManual, motorManualUntil_, now, st_.motorManualLeftS);

  // pump: manual beats schedule, low water beats everything
  const bool ap = autoPump(in, day);
  bool pump = st_.pumpManual == MAN_ON || (st_.pumpManual == MAN_AUTO && ap);
  if (st_.waterLow) pump = false;

  // motor: stall fault beats everything
  const uint32_t stallSteps = (uint32_t)rev * cfg_.stallPct / 100;
  if (cfg_.revSensor && st_.stepsSincePulse >= stallSteps) st_.faultStall = true;
  Outputs o;
  if (st_.faultStall) {
    target_ = in.motorPos;
    credit_ = 0;
    jogSteps_ = 0;
    homeReq_ = st_.homing = false;
    continuous_ = false;
    o.motorHalt = true;
  } else {
    planMotor(in, day, dt);
  }

  st_.pumpOn = pump;
  st_.stepsToGo = ahead(target_, in.motorPos);
  st_.motorBusy = st_.stepsToGo > 0;
  o.pump = pump;
  o.motorTarget = target_;
  return o;
}

}  // namespace sched
