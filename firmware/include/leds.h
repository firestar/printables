#pragma once
#include <Arduino.h>

// WS2812B halo ring. Animations run in their own task; modes are set by the
// hub (or locally for boot / setup / OTA).
namespace leds {

enum Mode : uint8_t {
  OFF,
  BOOT,       // white comet while starting
  SETUP,      // amber breathing: Wi-Fi setup portal is open
  IDLE,       // very dim breathing in the current colour
  LISTENING,  // spinning arc, brightens with mic level
  THINKING,   // two fast comets
  SPEAKING,   // whole ring follows the output level
  ERROR_BLINK,// red blink
  SOLID,      // steady colour
  RAINBOW,
  MODE_COUNT
};

void begin();
void setMode(Mode m);
Mode mode();
void setColor(uint8_t r, uint8_t g, uint8_t b);
uint32_t color();
void setBrightness(uint8_t b);     // 0..255, requested by the hub
uint8_t brightness();
void setMaxBrightness(uint8_t b);  // power cap, applied on top
uint8_t maxBrightness();

bool modeFromString(const char *s, Mode &out);
const char *modeName(Mode m);

}  // namespace leds
