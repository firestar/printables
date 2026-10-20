#pragma once
// Halo ring + optional Mickey backlight: one animation per feedback state,
// rendered from loop() at ~60 Hz with a brightness and current cap.

#include <stdint.h>

void ledsBegin();
void ledsSetState(uint8_t feedbackState);  // mb::Feedback
void ledsSetBrightness(uint8_t b);         // clamped to LED_MAX_BRIGHTNESS
void ledsLoop();
