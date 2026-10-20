#include "audio.h"

#include <Arduino.h>
#include <driver/i2s.h>
#include <math.h>

#include "config.h"

static const i2s_port_t PORT = I2S_NUM_0;
static QueueHandle_t cues;
static volatile uint8_t volume = AUDIO_VOLUME_DEFAULT;

struct Note {
  float hz;
  uint16_t atMs;   // start offset
  uint16_t tauMs;  // exponential decay time constant
  float h2, h3;    // 2nd / 3rd harmonic level (timbre)
};

struct Sound {
  const Note *notes;
  uint8_t n;
  uint16_t lengthMs;
  float level;
};

// Original cues.  GRANTED is a bright rising C-major arpeggio with a bell-like
// 2nd harmonic; DENIED two soft low tones falling a fourth.
static const Note GRANTED[] = {{1046.5f, 0, 350, 0.25f, 0}, {1318.5f, 70, 350, 0.25f, 0},
                               {1568.0f, 140, 350, 0.25f, 0}, {2093.0f, 210, 700, 0.2f, 0}};
static const Note DENIED[] = {{329.6f, 0, 220, 0.1f, 0.2f}, {246.9f, 260, 320, 0.1f, 0.2f}};
static const Note NEED_FINGER[] = {{1568.0f, 0, 90, 0.2f, 0}, {1568.0f, 160, 90, 0.2f, 0}};
static const Note READ[] = {{2637.0f, 0, 35, 0, 0}};
static const Note ERR[] = {{220.0f, 0, 110, 0, 0.3f}, {220.0f, 250, 110, 0, 0.3f}, {220.0f, 500, 110, 0, 0.3f}};
static const Note ENROLL_OK[] = {{1318.5f, 0, 200, 0.2f, 0}, {1760.0f, 120, 300, 0.2f, 0}};

#define SND(a, len, lvl) {a, sizeof(a) / sizeof(a[0]), len, lvl}
static const Sound SOUNDS[] = {
    SND(READ, 120, 0.3f),         // CUE_READ
    SND(NEED_FINGER, 450, 0.5f),  // CUE_NEED_FINGER
    SND(GRANTED, 2000, 0.6f),     // CUE_GRANTED
    SND(DENIED, 1300, 0.7f),      // CUE_DENIED
    SND(ERR, 900, 0.6f),          // CUE_ERROR
    SND(ENROLL_OK, 1200, 0.6f),   // CUE_ENROLL_OK
};

static void task(void *) {
  static int16_t buf[256];
  const float dt = 1.0f / AUDIO_SAMPLE_RATE;
  const Sound *cur = nullptr;
  uint32_t pos = 0, end = 0;
  for (;;) {
    uint8_t c;
    if (xQueueReceive(cues, &c, cur ? 0 : portMAX_DELAY) == pdTRUE && c < sizeof(SOUNDS) / sizeof(SOUNDS[0])) {
      cur = &SOUNDS[c];
      pos = 0;
      end = (uint32_t)cur->lengthMs * AUDIO_SAMPLE_RATE / 1000;
    }
    if (!cur) continue;
    float v = volume / 100.0f;
    float gain = cur->level * v * v * 32767.0f;  // square-law volume
    for (int i = 0; i < 256; i++, pos++) {
      float s = 0;
      for (uint8_t k = 0; k < cur->n; k++) {
        const Note &n = cur->notes[k];
        float t = pos * dt - n.atMs * 0.001f;
        if (t < 0) continue;
        float env = (t < 0.004f ? t / 0.004f : 1.0f) * expf(-t / (n.tauMs * 0.001f));
        float ph = 2.0f * (float)M_PI * n.hz * t;
        s += env * (sinf(ph) + n.h2 * sinf(2 * ph) + n.h3 * sinf(3 * ph));
      }
      s *= gain / (float)cur->n;
      buf[i] = (int16_t)(s > 32767 ? 32767 : s < -32767 ? -32767 : s);
    }
    size_t w;
    i2s_write(PORT, buf, sizeof(buf), &w, portMAX_DELAY);
    if (pos >= end) {
      cur = nullptr;
      i2s_zero_dma_buffer(PORT);  // silence, no hum between cues
    }
  }
}

void audioBegin() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = AUDIO_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = 0;
  cfg.dma_buf_count = 4;
  cfg.dma_buf_len = 256;
  cfg.tx_desc_auto_clear = true;  // underrun = silence
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = PIN_I2S_BCLK;
  pins.ws_io_num = PIN_I2S_LRC;
  pins.data_out_num = PIN_I2S_DOUT;
  pins.data_in_num = I2S_PIN_NO_CHANGE;
  if (i2s_driver_install(PORT, &cfg, 0, nullptr) != ESP_OK || i2s_set_pin(PORT, &pins) != ESP_OK) {
    log_e("I2S init failed");
    return;
  }
  cues = xQueueCreate(4, 1);
  xTaskCreatePinnedToCore(task, "audio", 4096, nullptr, 2, nullptr, 1);
}

void audioPlay(Cue c) {
  if (!cues) return;
  uint8_t v = c;
  xQueueSend(cues, &v, 0);
}

void audioSetVolume(uint8_t v) { volume = v > 100 ? 100 : v; }
