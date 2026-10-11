#include "audio.h"

#include <driver/i2s.h>
#include <freertos/ringbuf.h>
#include <math.h>

#include "config.h"

namespace audio {

static const i2s_port_t SPK_PORT = I2S_NUM_0;
static const i2s_port_t MIC_PORT = I2S_NUM_1;

static RingbufHandle_t micRb = nullptr;
static RingbufHandle_t spkRb = nullptr;
static SemaphoreHandle_t spkLock = nullptr;  // guards I2S0 reconfiguration

static volatile bool micOn = false;
static volatile uint8_t micCh = 1;
static volatile float micGain = 0;       // linear, includes 24->16 bit scaling
static volatile float micGainDbV = MIC_GAIN_DB_DEFAULT;
static volatile float micLvl = 0;

static volatile uint32_t spkRate = SPK_DEFAULT_RATE;
static volatile uint8_t vol = VOLUME_DEFAULT;
static volatile int32_t volQ15 = 0;
static volatile float spkLvl = 0;
static volatile bool spkBusy = false;
static volatile uint32_t spkLastMs = 0;

static inline int16_t clamp16(float v) {
  if (v > 32767.f) return 32767;
  if (v < -32768.f) return -32768;
  return (int16_t)v;
}

// ---------------------------------------------------------------------------
// microphones (I2S1, 32-bit slots, 24-bit data, stereo L/R)
// ---------------------------------------------------------------------------
static void micTask(void *) {
  const size_t FRAMES = 256;
  static int32_t raw[FRAMES * 2];
  static int16_t out[FRAMES * 2];
  float pxL = 0, pyL = 0, pxR = 0, pyR = 0;  // DC-blocking high-pass state

  for (;;) {
    size_t got = 0;
    if (i2s_read(MIC_PORT, raw, sizeof(raw), &got, portMAX_DELAY) != ESP_OK) continue;
    const size_t frames = got / 8;
    const uint8_t ch = micCh;
    const float g = micGain;
    float acc = 0;
    size_t o = 0;
    for (size_t i = 0; i < frames; i++) {
      float l = (float)(raw[2 * i] >> 8);      // 24-bit signed
      float r = (float)(raw[2 * i + 1] >> 8);
      float yl = l - pxL + 0.995f * pyL;
      pxL = l;
      pyL = yl;
      float yr = r - pxR + 0.995f * pyR;
      pxR = r;
      pyR = yr;
      yl *= g;
      yr *= g;
      if (ch == 1) {
        float m = 0.5f * (yl + yr);
        out[o++] = clamp16(m);
        acc += m * m;
      } else {
        out[o++] = clamp16(yl);
        out[o++] = clamp16(yr);
        acc += 0.5f * (yl * yl + yr * yr);
      }
    }
    if (frames) {
      float rms = sqrtf(acc / frames) / 32768.f;
      micLvl = micLvl * 0.7f + rms * 0.3f;
    }
    if (micOn && o) xRingbufferSend(micRb, out, o * sizeof(int16_t), 0);  // drop if full
  }
}

static bool micBegin() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
  cfg.sample_rate = MIC_SAMPLE_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 6;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;

  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = PIN_MIC_SCK;
  pins.ws_io_num = PIN_MIC_WS;
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = PIN_MIC_SD;

  if (i2s_driver_install(MIC_PORT, &cfg, 0, nullptr) != ESP_OK) return false;
  if (i2s_set_pin(MIC_PORT, &pins) != ESP_OK) return false;
  i2s_zero_dma_buffer(MIC_PORT);
  return true;
}

void setMicEnabled(bool enabled) {
  micOn = enabled;
  if (!enabled) flushMic();
}
bool micEnabled() { return micOn; }
void setMicChannels(uint8_t ch) {
  micCh = (ch == 2) ? 2 : 1;
  flushMic();
}
uint8_t micChannels() { return micCh; }
void setMicGainDb(float db) {
  if (db < -20) db = -20;
  if (db > 40) db = 40;
  micGainDbV = db;
  micGain = powf(10.f, db / 20.f) / 256.f;  // 24-bit -> 16-bit plus gain
}
float micGainDb() { return micGainDbV; }

size_t readMic(uint8_t *out, size_t maxBytes) {
  size_t got = 0;
  while (got < maxBytes) {
    size_t n = 0;
    void *p = xRingbufferReceiveUpTo(micRb, &n, 0, maxBytes - got);
    if (!p) break;
    memcpy(out + got, p, n);
    vRingbufferReturnItem(micRb, p);
    got += n;
  }
  return got;
}

void flushMic() {
  if (!micRb) return;
  size_t n;
  void *p;
  while ((p = xRingbufferReceiveUpTo(micRb, &n, 0, MIC_RING_BYTES)) != nullptr)
    vRingbufferReturnItem(micRb, p);
}

float micLevel() { return micLvl; }

// ---------------------------------------------------------------------------
// speaker (I2S0, 16-bit stereo; mono input duplicated to both slots, the
// MAX98357A outputs (L+R)/2 with SD unconnected)
// ---------------------------------------------------------------------------
static void spkTask(void *) {
  static uint8_t in[514];
  static int16_t st[512];
  size_t carry = 0;  // odd byte left over from a ring-buffer wrap

  for (;;) {
    size_t n = 0;
    void *p = xRingbufferReceiveUpTo(spkRb, &n, pdMS_TO_TICKS(20), 512 - carry);
    if (!p) {
      spkLvl = spkLvl * 0.8f;
      if (spkBusy && millis() - spkLastMs > 120) spkBusy = false;
      continue;
    }
    memcpy(in + carry, p, n);
    vRingbufferReturnItem(spkRb, p);
    size_t bytes = carry + n;
    size_t samples = bytes / 2;
    carry = bytes & 1;

    const int32_t v = volQ15;
    float acc = 0;
    for (size_t i = 0; i < samples; i++) {
      int16_t s = (int16_t)(in[2 * i] | (in[2 * i + 1] << 8));
      int32_t x = ((int32_t)s * v) >> 15;
      st[2 * i] = (int16_t)x;
      st[2 * i + 1] = (int16_t)x;
      acc += (float)x * x;
    }
    if (carry) in[0] = in[bytes - 1];
    if (samples) {
      float rms = sqrtf(acc / samples) / 32768.f;
      spkLvl = spkLvl * 0.7f + rms * 0.3f;
    }

    spkBusy = true;
    xSemaphoreTake(spkLock, portMAX_DELAY);
    size_t written = 0;
    i2s_write(SPK_PORT, st, samples * 4, &written, portMAX_DELAY);
    xSemaphoreGive(spkLock);
    spkLastMs = millis();
  }
}

static bool spkBegin() {
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
  cfg.sample_rate = spkRate;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = ESP_INTR_FLAG_LEVEL1;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  cfg.use_apll = false;
  cfg.tx_desc_auto_clear = true;  // output silence on underrun (no pops/buzz)

  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = PIN_SPK_BCLK;
  pins.ws_io_num = PIN_SPK_LRC;
  pins.data_out_num = PIN_SPK_DIN;
  pins.data_in_num = I2S_PIN_NO_CHANGE;

  if (i2s_driver_install(SPK_PORT, &cfg, 0, nullptr) != ESP_OK) return false;
  if (i2s_set_pin(SPK_PORT, &pins) != ESP_OK) return false;
  i2s_zero_dma_buffer(SPK_PORT);
  return true;
}

bool setSpeakerRate(uint32_t rate) {
  if (rate < 8000 || rate > 48000) return false;
  if (rate == spkRate) return true;
  xSemaphoreTake(spkLock, portMAX_DELAY);
  esp_err_t e = i2s_set_clk(SPK_PORT, rate, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_STEREO);
  xSemaphoreGive(spkLock);
  if (e != ESP_OK) return false;
  spkRate = rate;
  return true;
}
uint32_t speakerRate() { return spkRate; }

size_t pushSpeaker(const uint8_t *pcm, size_t bytes) {
  size_t room = xRingbufferGetCurFreeSize(spkRb);
  size_t n = bytes < room ? bytes : room;
  if (n == 0) return 0;
  if (xRingbufferSend(spkRb, pcm, n, 0) != pdTRUE) return 0;
  return n;
}

size_t speakerFree() { return xRingbufferGetCurFreeSize(spkRb); }
size_t speakerQueued() { return SPK_RING_BYTES - xRingbufferGetCurFreeSize(spkRb); }

void flushSpeaker() {
  size_t n;
  void *p;
  while ((p = xRingbufferReceiveUpTo(spkRb, &n, 0, SPK_RING_BYTES)) != nullptr)
    vRingbufferReturnItem(spkRb, p);
  xSemaphoreTake(spkLock, portMAX_DELAY);
  i2s_zero_dma_buffer(SPK_PORT);
  xSemaphoreGive(spkLock);
}

bool speakerActive() { return spkBusy || speakerQueued() > 0; }

void setVolume(uint8_t pct) {
  if (pct > 100) pct = 100;
  vol = pct;
  float f = pct / 100.f;
  volQ15 = (int32_t)(f * f * 32767.f);  // perceptual (square-law) curve
}
uint8_t volume() { return vol; }
float speakerLevel() { return spkLvl; }

// ---------------------------------------------------------------------------
bool begin() {
  micRb = xRingbufferCreate(MIC_RING_BYTES, RINGBUF_TYPE_BYTEBUF);
  spkRb = xRingbufferCreate(SPK_RING_BYTES, RINGBUF_TYPE_BYTEBUF);
  spkLock = xSemaphoreCreateMutex();
  if (!micRb || !spkRb || !spkLock) return false;
  setMicGainDb(MIC_GAIN_DB_DEFAULT);
  setVolume(vol);
  if (!micBegin() || !spkBegin()) return false;
  xTaskCreatePinnedToCore(micTask, "mic", 4096, nullptr, 5, nullptr, 1);
  xTaskCreatePinnedToCore(spkTask, "spk", 4096, nullptr, 5, nullptr, 1);
  return true;
}

}  // namespace audio
