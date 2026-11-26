#include "leds.h"

#include <Adafruit_NeoPixel.h>
#include <math.h>

#include "audio.h"
#include "config.h"
#include "serial_core.h"

namespace leds {

// Only the LED task touches the strip after begin(): setCount() just requests a
// new length, so the pixel buffer is never reallocated during a render.
static Adafruit_NeoPixel strip(LED_COUNT_DEFAULT, PIN_LED, NEO_GRB + NEO_KHZ800);
static volatile uint16_t wantCount = LED_COUNT_DEFAULT;
static volatile Mode curMode = BOOT;
static volatile uint32_t curColor = 0x0060FF;  // default: blue
static volatile uint8_t curBright = 200;
static volatile uint8_t maxBright = LED_MAX_BRIGHTNESS_DEFAULT;
static volatile uint8_t effMax = LED_MAX_BRIGHTNESS_DEFAULT;  // maxBright within the power budget

static const char *NAMES[MODE_COUNT] = {"off",      "boot",     "setup",  "idle",  "listening",
                                        "thinking", "speaking", "error",  "solid", "rainbow"};

static inline uint8_t sc(uint8_t a, uint8_t b) { return ((uint16_t)a * b + 255) >> 8; }

// colour * level (0..255) * effective brightness
static uint32_t shade(uint32_t c, uint8_t level) {
  uint8_t k = sc(sc(curBright, effMax), level);
  return Adafruit_NeoPixel::Color(sc((c >> 16) & 0xFF, k), sc((c >> 8) & 0xFF, k), sc(c & 0xFF, k));
}

static uint8_t breathe(uint32_t t, uint32_t periodMs, uint8_t lo, uint8_t hi) {
  float ph = (t % periodMs) / (float)periodMs;
  float s = 0.5f - 0.5f * cosf(ph * 2 * PI);
  return lo + (uint8_t)((hi - lo) * s);
}

// comet: head at position `pos` (0..n), fading tail of `len` LEDs
static uint8_t comet(int i, float pos, int len, int n) {
  if (len < 1) len = 1;  // short strips: n / 3 can be 0
  float d = pos - i;
  while (d < 0) d += n;
  while (d >= n) d -= n;
  if (d > len) return 0;
  return (uint8_t)(255 * (1.f - d / len));
}

static void render(uint32_t t) {
  const uint32_t c = curColor;
  const int n = strip.numPixels();
  if (n == 0) return;
  switch (curMode) {
    case OFF:
      strip.clear();
      break;
    case BOOT: {
      float pos = fmodf(t / 25.f, n);
      for (int i = 0; i < n; i++) strip.setPixelColor(i, shade(0xFFFFFF, comet(i, pos, 8, n)));
      break;
    }
    case SETUP: {
      uint8_t b = breathe(t, 2000, 20, 255);
      for (int i = 0; i < n; i++) strip.setPixelColor(i, shade(0xFF8000, b));
      break;
    }
    case IDLE: {
      uint8_t b = breathe(t, 6000, 4, 40);
      for (int i = 0; i < n; i++) strip.setPixelColor(i, shade(c, b));
      break;
    }
    case LISTENING: {
      float lvl = audio::micLevel() * 12.f;
      uint8_t boost = (uint8_t)(120 + 135 * (lvl > 1.f ? 1.f : lvl));
      float pos = fmodf(t / 60.f, n);
      for (int i = 0; i < n; i++) {
        uint8_t a = comet(i, pos, n / 3, n);
        strip.setPixelColor(i, shade(c, sc(a > 40 ? a : 40, boost)));
      }
      break;
    }
    case THINKING: {
      float pos = fmodf(t / 18.f, n);
      for (int i = 0; i < n; i++) {
        uint8_t a = comet(i, pos, 6, n);
        uint8_t b = comet(i, fmodf(pos + n / 2.f, n), 6, n);
        strip.setPixelColor(i, shade(c, a > b ? a : b));
      }
      break;
    }
    case SPEAKING: {
      float lvl = audio::speakerLevel() * 6.f;
      uint8_t b = (uint8_t)(60 + 195 * (lvl > 1.f ? 1.f : lvl));
      for (int i = 0; i < n; i++) strip.setPixelColor(i, shade(c, b));
      break;
    }
    case ERROR_BLINK: {
      uint8_t b = ((t / 250) & 1) ? 255 : 0;
      for (int i = 0; i < n; i++) strip.setPixelColor(i, shade(0xFF0000, b));
      break;
    }
    case SOLID:
      for (int i = 0; i < n; i++) strip.setPixelColor(i, shade(c, 255));
      break;
    case RAINBOW: {
      uint16_t base = (uint16_t)(t * 12);
      for (int i = 0; i < n; i++) {
        uint32_t h = Adafruit_NeoPixel::ColorHSV(base + (uint16_t)(i * 65536L / n));
        strip.setPixelColor(i, shade(Adafruit_NeoPixel::gamma32(h), 255));
      }
      break;
    }
    default:
      strip.clear();
  }
}

// Runs in the LED task. Blanks the current strip first, because LEDs past a
// shorter new length would otherwise hold their last colour.
static void applyCount(uint16_t count) {
  const uint16_t old = strip.numPixels();
  strip.clear();
  strip.show();
  strip.updateLength(count);
  if (strip.numPixels() == 0 && old > 0) {
    // Out of memory: updateLength() left no buffer, so go back to the old length.
    strip.updateLength(old);
    wantCount = strip.numPixels();
    log_e("no memory for %u LEDs", count);
  }
}

static void task(void *) {
  const TickType_t period = pdMS_TO_TICKS(1000 / LED_FPS);
  TickType_t last = xTaskGetTickCount();
  for (;;) {
    const uint16_t want = wantCount;
    if (want != strip.numPixels()) applyCount(want);
    render(millis());
    strip.show();
    vTaskDelayUntil(&last, period);
  }
}

void begin(uint16_t count) {
  // Blank the longest possible strip once: a reboot doesn't power the LEDs down,
  // so any past the configured length would otherwise stay lit.
  strip.updateLength(lumen::LED_COUNT_MAX);
  strip.begin();
  strip.clear();
  strip.show();
  setCount(count);
  strip.updateLength(count);
  xTaskCreatePinnedToCore(task, "leds", 3072, nullptr, 2, nullptr, 1);
}

void setCount(uint16_t count) {
  // The power cap is lowered before the new length is drawn.
  effMax = lumen::powerCappedBrightness(count, maxBright);
  wantCount = count;
}
uint16_t count() { return wantCount; }

void setMode(Mode m) {
  if (m < MODE_COUNT) curMode = m;
}
Mode mode() { return curMode; }
void setColor(uint8_t r, uint8_t g, uint8_t b) { curColor = ((uint32_t)r << 16) | ((uint32_t)g << 8) | b; }
uint32_t color() { return curColor; }
void setBrightness(uint8_t b) { curBright = b; }
uint8_t brightness() { return curBright; }
void setMaxBrightness(uint8_t b) {
  maxBright = b;
  effMax = lumen::powerCappedBrightness(wantCount, b);
}
uint8_t maxBrightness() { return maxBright; }
uint8_t effectiveMaxBrightness() { return effMax; }

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
