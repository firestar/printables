#include "leds.h"

#include <Adafruit_NeoPixel.h>
#include <Arduino.h>
#include <math.h>

#include "config.h"
#include "mb_protocol.h"

static const int N = LED_HALO_COUNT + LED_MICKEY_COUNT;
static Adafruit_NeoPixel strip(N, PIN_LED_DATA, NEO_GRB + NEO_KHZ800);
static uint8_t state = mb::FB_IDLE;
static uint32_t since = 0;
static uint8_t bright = LED_BRIGHTNESS_DEFAULT;
static uint32_t lastFrame = 0;

struct Rgb {
  float r, g, b;
};
static Rgb px[N > 0 ? N : 1];

static const Rgb WHITE = {1.0f, 0.85f, 0.7f};  // warm-ish white, kinder to the eye than 255/255/255
static const Rgb BLUE = {0.0f, 0.25f, 1.0f};
static const Rgb GREEN = {0.0f, 1.0f, 0.15f};
static const Rgb RED = {1.0f, 0.0f, 0.05f};
static const Rgb AMBER = {1.0f, 0.45f, 0.0f};
static const Rgb PURPLE = {0.6f, 0.0f, 1.0f};
static const Rgb ICE = {0.45f, 0.65f, 1.0f};  // NEED_FINGER: pale blue-white

static Rgb scale(Rgb c, float k) { return {c.r * k, c.g * k, c.b * k}; }
static void halo(Rgb c) {
  for (int i = 0; i < LED_HALO_COUNT; i++) px[i] = c;
}
static void mickey(Rgb c) {
  for (int i = LED_HALO_COUNT; i < N; i++) px[i] = c;
}
// 0..1..0 over `period` ms
static float breathe(uint32_t t, uint32_t period) {
  return 0.5f - 0.5f * cosf(2.0f * (float)M_PI * (float)(t % period) / (float)period);
}
// Comet: head at `pos` (0..1 around the ring) with a fading tail.
static void comet(Rgb c, float pos, float tail) {
  for (int i = 0; i < LED_HALO_COUNT; i++) {
    float d = pos - (float)i / LED_HALO_COUNT;
    if (d < 0) d += 1.0f;
    float k = d < tail ? 1.0f - d / tail : 0.0f;
    px[i] = scale(c, 0.05f + 0.95f * k * k);
  }
}

static void render(uint32_t t) {
  switch (state) {
    case mb::FB_IDLE:
      halo(scale(WHITE, 0.08f + 0.25f * breathe(t, 4000)));
      mickey(scale(WHITE, 0.12f));
      break;
    case mb::FB_READING:
      comet(BLUE, (float)(t % 700) / 700.0f, 0.35f);
      mickey(scale(BLUE, 0.3f));
      break;
    case mb::FB_NEED_FINGER:
      halo(scale(ICE, 0.15f + 0.6f * breathe(t, 2000)));
      mickey(scale(WHITE, 0.2f));
      break;
    case mb::FB_GRANTED:
      halo(GREEN);
      mickey(GREEN);
      break;
    case mb::FB_DENIED: {
      // alternating blue / red pulses ("see a cast member")
      uint32_t ph = t % 800;
      Rgb c = ph < 400 ? BLUE : RED;
      float k = breathe(ph % 400, 400);
      halo(scale(c, 0.1f + 0.9f * k));
      mickey(scale(c, 0.5f));
      break;
    }
    case mb::FB_ERROR:
    case mb::FB_OFFLINE: {
      float k = (t % 1000) < 500 ? 0.8f : 0.05f;
      halo(scale(AMBER, k));
      mickey(scale(AMBER, k * 0.5f));
      break;
    }
    case mb::FB_LOCKOUT:
      halo(scale(RED, 0.1f + 0.5f * breathe(t, 3000)));
      mickey(scale(RED, 0.2f));
      break;
    case mb::FB_ENROLL_BAND:
      comet(PURPLE, (float)(t % 1200) / 1200.0f, 0.5f);
      mickey(scale(PURPLE, 0.4f));
      break;
    case mb::FB_ENROLL_FINGER:
      halo(scale(PURPLE, 0.15f + 0.7f * breathe(t, 1500)));
      mickey(scale(PURPLE, 0.4f));
      break;
    case mb::FB_ENROLL_OK:
      halo((t / 150) % 2 ? PURPLE : GREEN);
      mickey(GREEN);
      break;
    case mb::FB_ENROLL_FAIL:
      halo((t / 150) % 2 ? PURPLE : RED);
      mickey(RED);
      break;
  }
}

static void show() {
  // brightness cap, then an estimated-current cap (all channels at full = 3 x LED_MA_PER_CHANNEL)
  float k = (float)bright / 255.0f;
  float ma = 0;
  for (int i = 0; i < N; i++) ma += (px[i].r + px[i].g + px[i].b) * k * LED_MA_PER_CHANNEL;
  if (ma > LED_CURRENT_LIMIT_MA) k *= LED_CURRENT_LIMIT_MA / ma;
  for (int i = 0; i < N; i++) {
    auto ch = [k](float v) -> uint8_t {
      float o = v * k * 255.0f + 0.5f;
      return o > 255.0f ? 255 : o < 0 ? 0 : (uint8_t)o;
    };
    strip.setPixelColor(i, ch(px[i].r), ch(px[i].g), ch(px[i].b));
  }
  strip.show();
}

void ledsBegin() {
  strip.begin();
  strip.clear();
  strip.show();
  since = millis();
}

void ledsSetState(uint8_t s) {
  if (s == state) return;
  state = s;
  since = millis();
}

void ledsSetBrightness(uint8_t b) { bright = b > LED_MAX_BRIGHTNESS ? LED_MAX_BRIGHTNESS : b; }

void ledsLoop() {
  uint32_t now = millis();
  if (now - lastFrame < 16) return;
  lastFrame = now;
  render(now - since);
  show();
}
