#include "leds.h"

#include <Adafruit_NeoPixel.h>
#include <math.h>

#include "audio.h"
#include "config.h"

namespace leds {

static Adafruit_NeoPixel strip(NUM_LEDS, PIN_LED, NEO_GRB + NEO_KHZ800);
static volatile Mode curMode = BOOT;
static volatile uint32_t curColor = 0x0060FF;  // default: blue
static volatile uint8_t curBright = 200;
static volatile uint8_t maxBright = LED_MAX_BRIGHTNESS_DEFAULT;

static const char *NAMES[MODE_COUNT] = {"off",      "boot",     "setup",  "idle",  "listening",
                                        "thinking", "speaking", "error",  "solid", "rainbow"};

static inline uint8_t sc(uint8_t a, uint8_t b) { return ((uint16_t)a * b + 255) >> 8; }

// colour * level (0..255) * effective brightness
static uint32_t shade(uint32_t c, uint8_t level) {
  uint8_t k = sc(sc(curBright, maxBright), level);
  return Adafruit_NeoPixel::Color(sc((c >> 16) & 0xFF, k), sc((c >> 8) & 0xFF, k), sc(c & 0xFF, k));
}

static uint8_t breathe(uint32_t t, uint32_t periodMs, uint8_t lo, uint8_t hi) {
  float ph = (t % periodMs) / (float)periodMs;
  float s = 0.5f - 0.5f * cosf(ph * 2 * PI);
  return lo + (uint8_t)((hi - lo) * s);
}

// comet: head at position `pos` (0..NUM_LEDS), fading tail of `len` LEDs
static uint8_t comet(int i, float pos, int len) {
  float d = pos - i;
  while (d < 0) d += NUM_LEDS;
  while (d >= NUM_LEDS) d -= NUM_LEDS;
  if (d > len) return 0;
  return (uint8_t)(255 * (1.f - d / len));
}

static void render(uint32_t t) {
  const uint32_t c = curColor;
  switch (curMode) {
    case OFF:
      strip.clear();
      break;
    case BOOT: {
      float pos = fmodf(t / 25.f, NUM_LEDS);
      for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, shade(0xFFFFFF, comet(i, pos, 8)));
      break;
    }
    case SETUP: {
      uint8_t b = breathe(t, 2000, 20, 255);
      for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, shade(0xFF8000, b));
      break;
    }
    case IDLE: {
      uint8_t b = breathe(t, 6000, 4, 40);
      for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, shade(c, b));
      break;
    }
    case LISTENING: {
      float lvl = audio::micLevel() * 12.f;
      uint8_t boost = (uint8_t)(120 + 135 * (lvl > 1.f ? 1.f : lvl));
      float pos = fmodf(t / 60.f, NUM_LEDS);
      for (int i = 0; i < NUM_LEDS; i++) {
        uint8_t a = comet(i, pos, NUM_LEDS / 3);
        strip.setPixelColor(i, shade(c, sc(a > 40 ? a : 40, boost)));
      }
      break;
    }
    case THINKING: {
      float pos = fmodf(t / 18.f, NUM_LEDS);
      for (int i = 0; i < NUM_LEDS; i++) {
        uint8_t a = comet(i, pos, 6);
        uint8_t b = comet(i, fmodf(pos + NUM_LEDS / 2.f, NUM_LEDS), 6);
        strip.setPixelColor(i, shade(c, a > b ? a : b));
      }
      break;
    }
    case SPEAKING: {
      float lvl = audio::speakerLevel() * 6.f;
      uint8_t b = (uint8_t)(60 + 195 * (lvl > 1.f ? 1.f : lvl));
      for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, shade(c, b));
      break;
    }
    case ERROR_BLINK: {
      uint8_t b = ((t / 250) & 1) ? 255 : 0;
      for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, shade(0xFF0000, b));
      break;
    }
    case SOLID:
      for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, shade(c, 255));
      break;
    case RAINBOW: {
      uint16_t base = (uint16_t)(t * 12);
      for (int i = 0; i < NUM_LEDS; i++) {
        uint32_t h = Adafruit_NeoPixel::ColorHSV(base + (uint16_t)(i * 65536L / NUM_LEDS));
        strip.setPixelColor(i, shade(Adafruit_NeoPixel::gamma32(h), 255));
      }
      break;
    }
    default:
      strip.clear();
  }
}

static void task(void *) {
  const TickType_t period = pdMS_TO_TICKS(1000 / LED_FPS);
  TickType_t last = xTaskGetTickCount();
  for (;;) {
    render(millis());
    strip.show();
    vTaskDelayUntil(&last, period);
  }
}

void begin() {
  strip.begin();
  strip.clear();
  strip.show();
  xTaskCreatePinnedToCore(task, "leds", 3072, nullptr, 2, nullptr, 1);
}

void setMode(Mode m) {
  if (m < MODE_COUNT) curMode = m;
}
Mode mode() { return curMode; }
void setColor(uint8_t r, uint8_t g, uint8_t b) { curColor = ((uint32_t)r << 16) | ((uint32_t)g << 8) | b; }
uint32_t color() { return curColor; }
void setBrightness(uint8_t b) { curBright = b; }
uint8_t brightness() { return curBright; }
void setMaxBrightness(uint8_t b) { maxBright = b; }
uint8_t maxBrightness() { return maxBright; }

bool modeFromString(const char *s, Mode &out) {
  if (!s) return false;
  for (uint8_t i = 0; i < MODE_COUNT; i++) {
    if (strcmp(s, NAMES[i]) == 0) {
      out = (Mode)i;
      return true;
    }
  }
  return false;
}

const char *modeName(Mode m) { return m < MODE_COUNT ? NAMES[m] : "?"; }

}  // namespace leds
