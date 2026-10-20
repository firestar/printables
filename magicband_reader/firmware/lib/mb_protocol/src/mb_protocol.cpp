#include "mb_protocol.h"

#include <string.h>

#include "mb_sha256.h"

namespace mb {

namespace {

void put16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)v;
  p[1] = (uint8_t)(v >> 8);
}
void put32(uint8_t *p, uint32_t v) {
  for (int i = 0; i < 4; i++) p[i] = (uint8_t)(v >> (8 * i));
}
uint16_t get16(const uint8_t *p) { return (uint16_t)(p[0] | p[1] << 8); }
uint32_t get32(const uint8_t *p) {
  return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

void tagOf(const uint8_t key[KEY_LEN], const uint8_t *buf, size_t n, uint8_t tag[TAG_LEN]) {
  uint8_t mac[SHA256_LEN];
  hmacSha256(key, KEY_LEN, buf, n, mac);
  memcpy(tag, mac, TAG_LEN);
}

}  // namespace

// ---- framing ----------------------------------------------------------------------
size_t encodeFrame(const uint8_t key[KEY_LEN], uint8_t src, uint8_t type, uint32_t ctr,
                   const uint8_t *payload, size_t len, uint8_t *out, size_t cap) {
  size_t total = HEADER_LEN + len + TAG_LEN;
  if (len > MAX_PAYLOAD || cap < total) return 0;
  out[0] = SOF;
  out[1] = (uint8_t)len;
  out[2] = src;
  out[3] = type;
  put32(out + 4, ctr);
  if (len) memcpy(out + HEADER_LEN, payload, len);
  tagOf(key, out, HEADER_LEN + len, out + HEADER_LEN + len);
  return total;
}

ParseResult parseFrame(const uint8_t key[KEY_LEN], const uint8_t *buf, size_t n, Frame &out,
                       size_t *consumed) {
  if (n < 1) return PARSE_NEED_MORE;
  if (buf[0] != SOF) return PARSE_BAD_SOF;
  if (n < 2) return PARSE_NEED_MORE;
  size_t len = buf[1];
  if (len > MAX_PAYLOAD) return PARSE_BAD_LEN;
  size_t total = HEADER_LEN + len + TAG_LEN;
  if (n < total) return PARSE_NEED_MORE;
  uint8_t tag[TAG_LEN];
  tagOf(key, buf, HEADER_LEN + len, tag);
  if (!ctEqual(tag, buf + HEADER_LEN + len, TAG_LEN)) return PARSE_BAD_TAG;
  out.len = (uint8_t)len;
  out.src = buf[2];
  out.type = buf[3];
  out.ctr = get32(buf + 4);
  memset(out.payload, 0, sizeof(out.payload));
  if (len) memcpy(out.payload, buf + HEADER_LEN, len);
  if (consumed) *consumed = total;
  return PARSE_OK;
}

void FrameDecoder::drop(size_t k) {
  if (k >= n_) {
    n_ = 0;
    return;
  }
  memmove(buf_, buf_ + k, n_ - k);
  n_ -= k;
}

bool FrameDecoder::push(uint8_t b, uint32_t nowMs, Frame &out) {
  if (n_ > 0 && nowMs - lastMs_ > FRAME_GAP_MS) {
    dropped++;
    n_ = 0;
  }
  lastMs_ = nowMs;
  if (n_ >= sizeof(buf_)) drop(1);  // cannot happen with a sane LEN check
  buf_[n_++] = b;
  for (;;) {
    size_t used = 0;
    ParseResult r = parseFrame(key_, buf_, n_, out, &used);
    switch (r) {
      case PARSE_OK:
        drop(used);
        return true;
      case PARSE_NEED_MORE:
        return false;
      case PARSE_BAD_LEN:
        badLen++;
        drop(1);
        break;
      case PARSE_BAD_TAG:
        badTag++;
        drop(1);
        break;
      case PARSE_BAD_SOF: {
        size_t k = 1;
        while (k < n_ && buf_[k] != SOF) k++;
        drop(k);
        break;
      }
    }
    if (n_ == 0) return false;
  }
}

// ---- counters -----------------------------------------------------------------------
void TxCounter::begin() {
  uint32_t v = 0;
  store_.load(key_, v);
  cur_ = reserved_ = v;  // everything up to the reservation may have been used
}

void TxCounter::reserve(uint32_t upTo) {
  reserved_ = upTo;
  store_.save(key_, reserved_);
}

uint32_t TxCounter::next() {
  cur_++;
  if (cur_ > reserved_) reserve(cur_ + block_ - 1);
  return cur_;
}

void TxCounter::bumpPast(uint32_t v) {
  if (v < cur_) return;
  cur_ = v;
  if (cur_ >= reserved_) reserve(cur_ + block_);
}

void ReplayGuard::begin() {
  uint32_t v = 0;
  store_.load(key_, v);
  last_ = saved_ = v;
}

Verdict ReplayGuard::check(uint32_t ctr) const {
  if (ctr <= last_) return CTR_REPLAY;
  if (ctr - last_ > window_) return CTR_OUT_OF_WINDOW;
  return CTR_FRESH;
}

void ReplayGuard::accept(uint32_t ctr, bool important) {
  if (ctr <= last_) return;
  last_ = ctr;
  if (important || last_ - saved_ >= step_) {
    saved_ = last_;
    store_.save(key_, saved_);
  }
}

// ---- link -------------------------------------------------------------------------------
SecureLink::SecureLink(uint8_t self, const uint8_t key[KEY_LEN], CounterStore &store, const LinkConfig &cfg)
    : self_(self),
      peer_(self == SRC_READER ? SRC_CONTROLLER : SRC_READER),
      key_(key),
      tx_(store, self == SRC_READER ? "tx_r" : "tx_c", cfg.txReserveBlock),
      rx_(store, self == SRC_READER ? "rx_c" : "rx_r", cfg.rxWindow, cfg.rxPersistStep),
      dec_(key) {}

void SecureLink::begin() {
  tx_.begin();
  rx_.begin();
}

size_t SecureLink::build(uint8_t type, const uint8_t *payload, size_t len, uint8_t *out, size_t cap) {
  if (len > MAX_PAYLOAD || cap < HEADER_LEN + len + TAG_LEN) return 0;
  return encodeFrame(key_, self_, type, tx_.next(), payload, len, out, cap);
}

RxStatus SecureLink::push(uint8_t b, uint32_t nowMs, Frame &out) {
  if (!dec_.push(b, nowMs, out)) return RX_NONE;
  if (out.src != peer_) {  // our own frame reflected back, or a bus echo
    stats.wrongSrc++;
    return RX_WRONG_SRC;
  }
  Verdict v = rx_.check(out.ctr);
  if (v == CTR_REPLAY) {
    stats.replay++;
    return RX_REPLAY;
  }
  if (v == CTR_OUT_OF_WINDOW) {
    stats.window++;
    return RX_OUT_OF_WINDOW;
  }
  rx_.accept(out.ctr, out.type != MSG_HELLO);
  if (out.type == MSG_HELLO) {
    Hello h;
    if (unpackHello(out, h)) tx_.bumpPast(h.lastSeen);
  }
  stats.ok++;
  return RX_OK;
}

// ---- payloads ------------------------------------------------------------------------------
size_t packHello(const Hello &m, uint8_t *p) {
  p[0] = m.proto;
  p[1] = m.fwMajor;
  p[2] = m.fwMinor;
  p[3] = m.flags;
  put32(p + 4, m.uptimeS);
  put32(p + 8, m.lastSeen);
  p[12] = m.caps;
  return 13;
}
bool unpackHello(const Frame &f, Hello &m) {
  if (f.type != MSG_HELLO || f.len < 12) return false;
  m.proto = f.payload[0];
  m.fwMajor = f.payload[1];
  m.fwMinor = f.payload[2];
  m.flags = f.payload[3];
  m.uptimeS = get32(f.payload + 4);
  m.lastSeen = get32(f.payload + 8);
  m.caps = f.len >= 13 ? f.payload[12] : CAPS_V1;  // longer = newer: extra bytes ignored
  return true;
}

size_t packBandScan(const BandScan &m, uint8_t *p) {
  uint8_t n = m.uidLen > UID_MAX ? UID_MAX : m.uidLen;
  p[0] = n;
  memcpy(p + 1, m.uid, n);
  return 1 + n;
}
bool unpackBandScan(const Frame &f, BandScan &m) {
  if (f.type != MSG_BAND_SCAN || f.len < 1) return false;
  uint8_t n = f.payload[0];
  if (n < 4 || n > UID_MAX || f.len < 1 + n) return false;
  m.uidLen = n;
  memset(m.uid, 0, sizeof(m.uid));
  memcpy(m.uid, f.payload + 1, n);
  return true;
}

size_t packFingerMatch(const FingerMatch &m, uint8_t *p) {
  put16(p, m.page);
  put16(p + 2, m.score);
  return 4;
}
bool unpackFingerMatch(const Frame &f, FingerMatch &m) {
  if (f.type != MSG_FINGER_MATCH || f.len < 4) return false;
  m.page = get16(f.payload);
  m.score = get16(f.payload + 2);
  return true;
}

size_t packU8(uint8_t v, uint8_t *p) {
  p[0] = v;
  return 1;
}
bool unpackU8(const Frame &f, uint8_t &v) {
  if (f.len < 1) return false;
  v = f.payload[0];
  return true;
}
size_t packU16(uint16_t v, uint8_t *p) {
  put16(p, v);
  return 2;
}
bool unpackU16(const Frame &f, uint16_t &v) {
  if (f.len < 2) return false;
  v = get16(f.payload);
  return true;
}

size_t packFeedback(const FeedbackCmd &m, uint8_t *p) {
  p[0] = m.state;
  put16(p + 1, m.holdMs);
  return 3;
}
bool unpackFeedback(const Frame &f, FeedbackCmd &m) {
  if (f.type != MSG_FEEDBACK || f.len < 3 || f.payload[0] >= FB_COUNT) return false;
  m.state = f.payload[0];
  m.holdMs = get16(f.payload + 1);
  return true;
}

size_t packEnrollResult(const EnrollResult &m, uint8_t *p) {
  put16(p, m.page);
  p[2] = m.status;
  return 3;
}
bool unpackEnrollResult(const Frame &f, EnrollResult &m) {
  if (f.type != MSG_ENROLL_RESULT || f.len < 3) return false;
  m.page = get16(f.payload);
  m.status = f.payload[2];
  return true;
}

size_t packConfig(const ReaderConfig &m, uint8_t *p) {
  p[0] = m.brightness;
  p[1] = m.volume;
  return 2;
}
bool unpackConfig(const Frame &f, ReaderConfig &m) {
  if (f.type != MSG_SET_CONFIG || f.len < 2) return false;
  m.brightness = f.payload[0];
  m.volume = f.payload[1] > 100 ? 100 : f.payload[1];
  return true;
}

const char *msgName(uint8_t type) {
  switch (type) {
    case MSG_HELLO: return "HELLO";
    case MSG_BAND_SCAN: return "BAND_SCAN";
    case MSG_FINGER_MATCH: return "FINGER_MATCH";
    case MSG_FINGER_NOMATCH: return "FINGER_NOMATCH";
    case MSG_TAMPER: return "TAMPER";
    case MSG_ENROLL_RESULT: return "ENROLL_RESULT";
    case MSG_FEEDBACK: return "FEEDBACK";
    case MSG_ENROLL_FINGER: return "ENROLL_FINGER";
    case MSG_SET_CONFIG: return "SET_CONFIG";
    case MSG_DELETE_FINGER: return "DELETE_FINGER";
  }
  return "?";
}

const char *feedbackName(uint8_t s) {
  static const char *const N[FB_COUNT] = {"IDLE",         "READING",        "NEED_FINGER", "GRANTED",
                                          "DENIED",       "ERROR",          "OFFLINE",     "ENROLL_BAND",
                                          "ENROLL_FINGER", "ENROLL_OK",     "ENROLL_FAIL", "LOCKOUT"};
  return s < FB_COUNT ? N[s] : "?";
}

}  // namespace mb
