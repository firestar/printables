#pragma once

// 28BYJ-48 stepper on a ULN2003 board, via AccelStepper (HALF4WIRE).
// Stepping runs from a 250 us esp_timer, so web requests and Wi-Fi in
// loop() don't make it stutter.  Coils are de-energised whenever it stops.

#include <stdint.h>

namespace motor {

void begin();

// Move forward to `target` (absolute steps) with acceleration.  If the target
// is at or behind the position, decelerate and stop (never reverse).
// halt = stop at once and de-energise.
void command(int32_t target, bool halt, uint16_t maxSpeed);

int32_t position();
bool energised();

}  // namespace motor
