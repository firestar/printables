#pragma once

// State shared between main.cpp (hardware, scheduler loop) and web.cpp.

#include <Arduino.h>
#include <time.h>

#include "scheduler.h"

namespace app {

struct Telemetry {
  bool tempValid = false;
  float tempC = 0;
  uint32_t revPulses = 0;     // rev sensor pulses since boot
  bool motorEnergised = false;  // stepper coils powered (moving)
};

extern sched::Scheduler scheduler;
extern Telemetry tele;
extern String tz;  // POSIX TZ string

uint32_t nowS();               // monotonic seconds since boot, no 49-day wrap
bool localTime(struct tm &t);  // false until NTP has synced
void saveConfig();             // persist scheduler config + tz, re-apply tz

}  // namespace app
