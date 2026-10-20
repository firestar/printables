#include "link_port.h"

#include <driver/gpio.h>

#include "config.h"
#include "mb_sha256.h"

// ---- NvsCounterStore ---------------------------------------------------------------
void NvsCounterStore::begin(const uint8_t key[mb::KEY_LEN]) {
  prefs_.begin("mblink", false);
  uint8_t d[mb::SHA256_LEN];
  mb::sha256(key, mb::KEY_LEN, d);  // only a fingerprint, the key never goes to flash here
  uint32_t fp = (uint32_t)d[0] | (uint32_t)d[1] << 8 | (uint32_t)d[2] << 16 | (uint32_t)d[3] << 24;
  if (prefs_.getUInt("kfp", 0) != fp) {
    prefs_.clear();
    prefs_.putUInt("kfp", fp);
    log_i("link key changed: counters reset");
  }
}

bool NvsCounterStore::load(const char *key, uint32_t &v) {
  if (!prefs_.isKey(key)) return false;
  v = prefs_.getUInt(key, 0);
  return true;
}

void NvsCounterStore::save(const char *key, uint32_t v) { prefs_.putUInt(key, v); }

bool parseKeyHex(const char *hex, uint8_t out[mb::KEY_LEN]) {
  if (strlen(hex) != 2 * mb::KEY_LEN) return false;
  for (size_t i = 0; i < mb::KEY_LEN; i++) {
    char b[3] = {hex[2 * i], hex[2 * i + 1], 0};
    char *end;
    out[i] = (uint8_t)strtoul(b, &end, 16);
    if (*end) return false;
  }
  return true;
}

// ---- LinkPort ---------------------------------------------------------------------------
static mb::LinkConfig linkConfig() {
  mb::LinkConfig c;
  c.txReserveBlock = TX_RESERVE_BLOCK;
  c.rxWindow = RX_WINDOW;
  c.rxPersistStep = RX_PERSIST_STEP;
  return c;
}

LinkPort::LinkPort(uint8_t self) : link_(self, key_, store_, linkConfig()) {}

void LinkPort::begin(HardwareSerial &serial, int rxPin, int txPin, int dePin, uint32_t baud) {
  if (!parseKeyHex(LINK_KEY_HEX, key_)) {
    log_e("LINK_KEY_HEX is not 64 hex digits");
    memset(key_, 0, sizeof(key_));
  }
  {  // mbedtls HMAC must agree with the unit-tested portable one
    uint8_t a[mb::SHA256_LEN], b[mb::SHA256_LEN];
    static const uint8_t msg[] = "what do ya want for nothing?";
    mb::hmacSha256(key_, sizeof(key_), msg, sizeof(msg) - 1, a);
    mb::hmacSha256Portable(key_, sizeof(key_), msg, sizeof(msg) - 1, b);
    if (memcmp(a, b, sizeof(a)) != 0) log_e("HMAC self-test FAILED");
  }
  store_.begin(key_);
  link_.begin();
  de_ = dePin;
  pinMode(de_, OUTPUT);
  digitalWrite(de_, LOW);  // receive
  s_ = &serial;
  s_->begin(baud, SERIAL_8N1, rxPin, txPin);
  gpio_pullup_en((gpio_num_t)rxPin);  // RO floats while DE is high on some modules
}

bool LinkPort::pumpOne(mb::Frame &out) {
  while (s_->available()) {
    uint8_t b = (uint8_t)s_->read();
    uint32_t now = millis();
    lastRxByte_ = now;
    mb::RxStatus st = link_.push(b, now, out);
    if (st == mb::RX_OK) {
      lastValid_ = now;
      everValid_ = true;
      return true;
    }
    if (st != mb::RX_NONE) log_w("link: rejected %s ctr=%u (%d)", mb::msgName(out.type), out.ctr, st);
  }
  return false;
}

bool LinkPort::poll(mb::Frame &out) {
  if (qn_ > 0) {
    out = q_[0];
    for (int i = 1; i < qn_; i++) q_[i - 1] = q_[i];
    qn_--;
    return true;
  }
  return pumpOne(out);
}

bool LinkPort::send(uint8_t type, const uint8_t *payload, size_t len) {
  uint8_t buf[mb::MAX_FRAME];
  size_t n = link_.build(type, payload, len, buf, sizeof(buf));
  if (!n) return false;
  // Listen before talk: wait for a quiet bus plus a little jitter so both
  // ends do not start at the same instant.  Frames arriving meanwhile are queued.
  uint32_t start = millis();
  for (;;) {
    mb::Frame f;
    if (pumpOne(f) && qn_ < QLEN) q_[qn_++] = f;
    if (millis() - lastRxByte_ >= BUS_IDLE_MS) {
      delayMicroseconds(random(200, 1500));
      if (!s_->available()) break;
    }
    if (millis() - start > 50) break;  // bus stuck busy: send anyway
  }
  digitalWrite(de_, HIGH);
  s_->write(buf, n);
  s_->flush();  // waits until the last stop bit is out
  digitalWrite(de_, LOW);
  return true;
}

bool LinkPort::peerOnline() const { return everValid_ && millis() - lastValid_ < PEER_TIMEOUT_MS; }

uint32_t LinkPort::rejected() const {
  const mb::FrameDecoder &d = link_.decoder();
  return d.badTag + link_.stats.replay + link_.stats.window + link_.stats.wrongSrc;
}
