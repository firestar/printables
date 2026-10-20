// Link protocol: framing, tags, resync, counters, replay window, payloads.
// Run: pio test -e native

#include <string.h>
#include <unity.h>

#include <map>
#include <string>
#include <vector>

#include "mb_protocol.h"
#include "vectors.h"

using namespace mb;

// In-memory CounterStore that counts flash writes.
struct MapStore : CounterStore {
  std::map<std::string, uint32_t> m;
  int writes = 0;
  bool load(const char *k, uint32_t &v) override {
    auto it = m.find(k);
    if (it == m.end()) return false;
    v = it->second;
    return true;
  }
  void save(const char *k, uint32_t v) override {
    m[k] = v;
    writes++;
  }
};

static const uint8_t *KEY = VEC_KEY;
static uint8_t OTHER_KEY[32];

void setUp() {}
void tearDown() {}

static std::vector<uint8_t> frame(uint8_t src, uint8_t type, uint32_t ctr, const uint8_t *p, size_t n,
                                  const uint8_t *key = KEY) {
  uint8_t buf[MAX_FRAME];
  size_t len = encodeFrame(key, src, type, ctr, p, n, buf, sizeof(buf));
  return std::vector<uint8_t>(buf, buf + len);
}

// Feeds bytes 1 ms apart; returns the frames the decoder produced.
static std::vector<Frame> feed(FrameDecoder &d, const std::vector<uint8_t> &bytes, uint32_t &t) {
  std::vector<Frame> out;
  Frame f;
  for (uint8_t b : bytes)
    if (d.push(b, t++, f)) out.push_back(f);
  return out;
}

// ---- cross-check against the Python implementation ---------------------------------
void test_vectors_encode_like_python() {
  for (size_t i = 0; i < VECTOR_COUNT; i++) {
    const Vector &v = VECTORS[i];
    uint8_t buf[MAX_FRAME];
    size_t n = encodeFrame(VEC_KEY, v.src, v.type, v.ctr, v.payload, v.payloadLen, buf, sizeof(buf));
    TEST_ASSERT_EQUAL_UINT_MESSAGE(v.frameLen, n, v.name);
    TEST_ASSERT_EQUAL_HEX8_ARRAY_MESSAGE(v.frame, buf, n, v.name);
  }
}

void test_vectors_decode() {
  for (size_t i = 0; i < VECTOR_COUNT; i++) {
    const Vector &v = VECTORS[i];
    Frame f;
    size_t used = 0;
    TEST_ASSERT_EQUAL_MESSAGE(PARSE_OK, parseFrame(VEC_KEY, v.frame, v.frameLen, f, &used), v.name);
    TEST_ASSERT_EQUAL_UINT(v.frameLen, used);
    TEST_ASSERT_EQUAL_HEX8(v.src, f.src);
    TEST_ASSERT_EQUAL_HEX8(v.type, f.type);
    TEST_ASSERT_EQUAL_UINT32(v.ctr, f.ctr);
    TEST_ASSERT_EQUAL_UINT(v.payloadLen, f.len);
    if (v.payloadLen) TEST_ASSERT_EQUAL_HEX8_ARRAY(v.payload, f.payload, v.payloadLen);
  }
}

static const Vector *vectorNamed(const char *name) {
  for (size_t i = 0; i < VECTOR_COUNT; i++)
    if (!strcmp(VECTORS[i].name, name)) return &VECTORS[i];
  return nullptr;
}

// Capability bits from Python-encoded HELLOs, including a legacy v1 one.
void test_vectors_hello_caps() {
  struct {
    const char *name;
    uint8_t proto, caps;
  } want[] = {{"hello_reader", 2, CAP_FINGERPRINT | CAP_NFC},
              {"hello_reader_nofp", 2, CAP_NFC},
              {"hello_reader_v1", 1, CAPS_V1},
              {"hello_controller", 2, 0}};
  for (auto &w : want) {
    const Vector *v = vectorNamed(w.name);
    TEST_ASSERT_NOT_NULL_MESSAGE(v, w.name);
    Frame f;
    TEST_ASSERT_EQUAL(PARSE_OK, parseFrame(VEC_KEY, v->frame, v->frameLen, f, nullptr));
    Hello h;
    TEST_ASSERT_TRUE_MESSAGE(unpackHello(f, h), w.name);
    TEST_ASSERT_EQUAL_UINT8_MESSAGE(w.proto, h.proto, w.name);
    TEST_ASSERT_EQUAL_HEX8_MESSAGE(w.caps, h.caps, w.name);
  }
  TEST_ASSERT_TRUE(CAPS_V1 & CAP_FINGERPRINT);  // old readers keep their finger users working
}

// HELLO capability bits survive a pack/unpack round trip and a link hop.
void test_hello_caps_round_trip() {
  uint8_t b[MAX_PAYLOAD];
  for (uint8_t caps : {(uint8_t)0, CAP_NFC, (uint8_t)(CAP_FINGERPRINT | CAP_NFC), (uint8_t)0xFF}) {
    Hello h;
    h.caps = caps;
    h.flags = HELLO_NFC_OK;
    size_t n = packHello(h, b);
    TEST_ASSERT_EQUAL_UINT(13, n);
    TEST_ASSERT_EQUAL_UINT8(PROTO_VERSION, b[0]);
    Frame f;
    f.type = MSG_HELLO;
    f.len = (uint8_t)n;
    memcpy(f.payload, b, n);
    Hello h2;
    TEST_ASSERT_TRUE(unpackHello(f, h2));
    TEST_ASSERT_EQUAL_HEX8(caps, h2.caps);
    TEST_ASSERT_EQUAL_HEX8(HELLO_NFC_OK, h2.flags);
  }
  // through the secure link, as the controller receives it
  MapStore rs, cs;
  SecureLink reader(SRC_READER, KEY, rs), ctrl(SRC_CONTROLLER, KEY, cs);
  reader.begin();
  ctrl.begin();
  Hello h;
  h.caps = CAP_NFC;  // reader_nofp
  uint8_t frameBuf[MAX_FRAME];
  size_t len = reader.build(MSG_HELLO, b, packHello(h, b), frameBuf, sizeof(frameBuf));
  Frame f;
  RxStatus st = RX_NONE;
  for (size_t i = 0; i < len; i++) st = ctrl.push(frameBuf[i], (uint32_t)i, f);
  TEST_ASSERT_EQUAL(RX_OK, st);
  Hello got;
  TEST_ASSERT_TRUE(unpackHello(f, got));
  TEST_ASSERT_FALSE(got.caps & CAP_FINGERPRINT);
}

// ---- framing --------------------------------------------------------------------------
void test_round_trip_every_length() {
  uint8_t p[MAX_PAYLOAD];
  for (size_t n = 0; n <= MAX_PAYLOAD; n++) {
    for (size_t i = 0; i < n; i++) p[i] = (uint8_t)(n * 31 + i);
    auto fr = frame(SRC_READER, MSG_HELLO, 1000 + n, p, n);
    TEST_ASSERT_EQUAL_UINT(HEADER_LEN + n + TAG_LEN, fr.size());
    Frame f;
    size_t used;
    TEST_ASSERT_EQUAL(PARSE_OK, parseFrame(KEY, fr.data(), fr.size(), f, &used));
    TEST_ASSERT_EQUAL_UINT(n, f.len);
    TEST_ASSERT_EQUAL_UINT32(1000 + n, f.ctr);
    if (n) TEST_ASSERT_EQUAL_HEX8_ARRAY(p, f.payload, n);
  }
}

void test_encode_rejects_oversize() {
  uint8_t p[MAX_PAYLOAD + 1] = {0}, buf[128];
  TEST_ASSERT_EQUAL_UINT(0, encodeFrame(KEY, SRC_READER, MSG_HELLO, 1, p, MAX_PAYLOAD + 1, buf, sizeof(buf)));
  TEST_ASSERT_EQUAL_UINT(0, encodeFrame(KEY, SRC_READER, MSG_HELLO, 1, p, 4, buf, HEADER_LEN + 4 + TAG_LEN - 1));
}

void test_parse_need_more_when_truncated() {
  uint8_t p[3] = {1, 2, 3};
  auto fr = frame(SRC_READER, MSG_FEEDBACK, 5, p, 3);
  Frame f;
  for (size_t n = 0; n < fr.size(); n++) TEST_ASSERT_EQUAL(PARSE_NEED_MORE, parseFrame(KEY, fr.data(), n, f, nullptr));
}

void test_parse_bad_sof() {
  auto fr = frame(SRC_READER, MSG_HELLO, 1, nullptr, 0);
  fr[0] = 0x5A;
  Frame f;
  TEST_ASSERT_EQUAL(PARSE_BAD_SOF, parseFrame(KEY, fr.data(), fr.size(), f, nullptr));
}

void test_parse_bad_length() {
  auto fr = frame(SRC_READER, MSG_HELLO, 1, nullptr, 0);
  fr[1] = MAX_PAYLOAD + 1;
  Frame f;
  TEST_ASSERT_EQUAL(PARSE_BAD_LEN, parseFrame(KEY, fr.data(), fr.size(), f, nullptr));
  // A length that is legal but wrong breaks the tag instead.
  auto fr2 = frame(SRC_READER, MSG_BAND_SCAN, 1, (const uint8_t *)"\x04\x01\x02\x03\x04", 5);
  fr2[1] = 4;
  TEST_ASSERT_EQUAL(PARSE_BAD_TAG, parseFrame(KEY, fr2.data(), fr2.size(), f, nullptr));
}

void test_parse_bad_tag_any_bit() {
  uint8_t p[5] = {4, 0xDE, 0xAD, 0xBE, 0xEF};
  auto good = frame(SRC_READER, MSG_BAND_SCAN, 9, p, 5);
  Frame f;
  for (size_t i = 2; i < good.size(); i++) {  // every byte after SOF/LEN, incl. the tag
    auto bad = good;
    bad[i] ^= 0x01;
    TEST_ASSERT_EQUAL(PARSE_BAD_TAG, parseFrame(KEY, bad.data(), bad.size(), f, nullptr));
  }
}

void test_parse_wrong_key() {
  memset(OTHER_KEY, 0x42, sizeof(OTHER_KEY));
  auto fr = frame(SRC_READER, MSG_HELLO, 1, nullptr, 0, OTHER_KEY);
  Frame f;
  TEST_ASSERT_EQUAL(PARSE_BAD_TAG, parseFrame(KEY, fr.data(), fr.size(), f, nullptr));
}

// ---- streaming decoder ------------------------------------------------------------------
void test_decoder_back_to_back() {
  FrameDecoder d(KEY);
  std::vector<uint8_t> bytes;
  for (uint32_t c = 1; c <= 5; c++) {
    auto fr = frame(SRC_READER, MSG_HELLO, c, nullptr, 0);
    bytes.insert(bytes.end(), fr.begin(), fr.end());
  }
  uint32_t t = 0;
  auto out = feed(d, bytes, t);
  TEST_ASSERT_EQUAL(5, (int)out.size());
  TEST_ASSERT_EQUAL_UINT32(5, out[4].ctr);
}

void test_decoder_skips_garbage_and_false_sof() {
  FrameDecoder d(KEY);
  // noise, a fake SOF with a plausible length, then a real frame
  std::vector<uint8_t> bytes = {0x00, 0xFF, 0x13, SOF, 0x05, 0x52, 0x10};
  uint8_t p[5] = {4, 1, 2, 3, 4};
  auto fr = frame(SRC_READER, MSG_BAND_SCAN, 77, p, 5);
  bytes.insert(bytes.end(), fr.begin(), fr.end());
  // trailing bytes so the fake frame (which swallowed the real one) completes
  for (int i = 0; i < 40; i++) bytes.push_back(0x00);
  uint32_t t = 0;
  auto out = feed(d, bytes, t);
  TEST_ASSERT_EQUAL(1, (int)out.size());
  TEST_ASSERT_EQUAL_UINT32(77, out[0].ctr);
  TEST_ASSERT_TRUE(d.badTag >= 1);
}

void test_decoder_recovers_after_corrupt_length() {
  FrameDecoder d(KEY);
  auto bad = frame(SRC_READER, MSG_HELLO, 1, nullptr, 0);
  bad[1] = 0xEE;
  auto good = frame(SRC_READER, MSG_HELLO, 2, nullptr, 0);
  std::vector<uint8_t> bytes(bad);
  bytes.insert(bytes.end(), good.begin(), good.end());
  uint32_t t = 0;
  auto out = feed(d, bytes, t);
  TEST_ASSERT_EQUAL(1, (int)out.size());
  TEST_ASSERT_EQUAL_UINT32(2, out[0].ctr);
  TEST_ASSERT_TRUE(d.badLen >= 1);
}

void test_decoder_recovers_after_corrupt_sof() {
  FrameDecoder d(KEY);
  auto bad = frame(SRC_READER, MSG_HELLO, 1, nullptr, 0);
  bad[0] = 0x00;
  auto good = frame(SRC_READER, MSG_HELLO, 2, nullptr, 0);
  std::vector<uint8_t> bytes(bad);
  bytes.insert(bytes.end(), good.begin(), good.end());
  uint32_t t = 0;
  auto out = feed(d, bytes, t);
  TEST_ASSERT_EQUAL(1, (int)out.size());
  TEST_ASSERT_EQUAL_UINT32(2, out[0].ctr);
}

void test_decoder_gap_drops_partial() {
  FrameDecoder d(KEY);
  auto fr = frame(SRC_READER, MSG_HELLO, 3, nullptr, 0);
  Frame f;
  uint32_t t = 0;
  for (size_t i = 0; i < 10; i++) TEST_ASSERT_FALSE(d.push(fr[i], t++, f));
  t += FRAME_GAP_MS + 5;  // line went quiet mid-frame
  for (size_t i = 10; i < fr.size(); i++) TEST_ASSERT_FALSE(d.push(fr[i], t++, f));
  TEST_ASSERT_EQUAL_UINT32(1, d.dropped);
  auto out = feed(d, fr, t);  // the next complete frame still decodes
  TEST_ASSERT_EQUAL(1, (int)out.size());
}

// ---- counters ---------------------------------------------------------------------------
void test_replay_guard_window() {
  MapStore s;
  ReplayGuard g(s, "rx", 100, 10);
  g.begin();
  TEST_ASSERT_EQUAL(CTR_REPLAY, g.check(0));
  TEST_ASSERT_EQUAL(CTR_FRESH, g.check(1));
  TEST_ASSERT_EQUAL(CTR_FRESH, g.check(100));
  TEST_ASSERT_EQUAL(CTR_OUT_OF_WINDOW, g.check(101));
  g.accept(50, false);
  TEST_ASSERT_EQUAL(CTR_REPLAY, g.check(50));
  TEST_ASSERT_EQUAL(CTR_REPLAY, g.check(49));
  TEST_ASSERT_EQUAL(CTR_FRESH, g.check(51));
  TEST_ASSERT_EQUAL(CTR_FRESH, g.check(150));
  TEST_ASSERT_EQUAL(CTR_OUT_OF_WINDOW, g.check(151));
}

void test_replay_guard_persistence() {
  MapStore s;
  {
    ReplayGuard g(s, "rx", 1000, 10);
    g.begin();
    for (uint32_t c = 1; c <= 25; c++) g.accept(c, false);  // heartbeats
    TEST_ASSERT_EQUAL(2, s.writes);                           // at 10 and 20
    g.accept(26, true);                                       // a scan: saved at once
    TEST_ASSERT_EQUAL_UINT32(26, s.m["rx"]);
  }
  ReplayGuard g2(s, "rx", 1000, 10);  // reboot
  g2.begin();
  TEST_ASSERT_EQUAL(CTR_REPLAY, g2.check(26));  // the scan cannot be replayed
  TEST_ASSERT_EQUAL(CTR_FRESH, g2.check(27));
}

void test_tx_counter_reserves_blocks_and_never_reuses() {
  MapStore s;
  uint32_t last;
  {
    TxCounter c(s, "tx", 100);
    c.begin();
    TEST_ASSERT_EQUAL_UINT32(1, c.next());
    TEST_ASSERT_EQUAL(1, s.writes);  // reserved 1..100
    for (int i = 0; i < 99; i++) c.next();
    TEST_ASSERT_EQUAL(1, s.writes);
    last = c.next();  // 101 -> new block
    TEST_ASSERT_EQUAL_UINT32(101, last);
    TEST_ASSERT_EQUAL(2, s.writes);
  }
  TxCounter c2(s, "tx", 100);  // reboot (power cut mid-block)
  c2.begin();
  TEST_ASSERT_TRUE(c2.next() > last);
}

void test_tx_counter_bump_past() {
  MapStore s;
  TxCounter c(s, "tx", 100);
  c.begin();
  c.next();
  c.bumpPast(5000);
  TEST_ASSERT_EQUAL_UINT32(5001, c.next());
  c.bumpPast(10);  // never goes backwards
  TEST_ASSERT_EQUAL_UINT32(5002, c.next());
  TxCounter c2(s, "tx", 100);
  c2.begin();
  TEST_ASSERT_TRUE(c2.next() > 5002);
}

// ---- secure link --------------------------------------------------------------------------
struct Pair {
  MapStore rs, cs;
  SecureLink reader{SRC_READER, KEY, rs};
  SecureLink ctrl{SRC_CONTROLLER, KEY, cs};
  uint32_t t = 0;
  Pair() {
    reader.begin();
    ctrl.begin();
  }
  std::vector<uint8_t> build(SecureLink &l, uint8_t type, const uint8_t *p = nullptr, size_t n = 0) {
    uint8_t buf[MAX_FRAME];
    size_t len = l.build(type, p, n, buf, sizeof(buf));
    return std::vector<uint8_t>(buf, buf + len);
  }
  RxStatus deliver(SecureLink &to, const std::vector<uint8_t> &bytes, Frame &f) {
    t += 100;
    RxStatus last = RX_NONE;
    for (uint8_t b : bytes) {
      RxStatus r = to.push(b, t++, f);
      if (r != RX_NONE) last = r;
    }
    return last;
  }
};

void test_link_accepts_fresh_rejects_replay() {
  Pair p;
  uint8_t pl[5] = {4, 9, 8, 7, 6};
  auto scan = p.build(p.reader, MSG_BAND_SCAN, pl, 5);
  Frame f;
  TEST_ASSERT_EQUAL(RX_OK, p.deliver(p.ctrl, scan, f));
  BandScan b;
  TEST_ASSERT_TRUE(unpackBandScan(f, b));
  TEST_ASSERT_EQUAL_UINT8(4, b.uidLen);
  TEST_ASSERT_EQUAL(RX_REPLAY, p.deliver(p.ctrl, scan, f));
  TEST_ASSERT_EQUAL_UINT32(1, p.ctrl.stats.replay);
}

void test_link_rejects_reflected_frame() {
  Pair p;
  auto mine = p.build(p.ctrl, MSG_FEEDBACK, (const uint8_t *)"\x03\x00\x00", 3);
  Frame f;
  TEST_ASSERT_EQUAL(RX_WRONG_SRC, p.deliver(p.ctrl, mine, f));  // echoed back at the controller
  TEST_ASSERT_EQUAL(RX_OK, p.deliver(p.reader, mine, f));
}

void test_link_rejects_out_of_window() {
  Pair p;
  auto far = frame(SRC_READER, MSG_HELLO, (1u << 20) + 5, nullptr, 0);
  Frame f;
  TEST_ASSERT_EQUAL(RX_OUT_OF_WINDOW, p.deliver(p.ctrl, far, f));
}

void test_link_hello_resyncs_wiped_sender() {
  Pair p;
  Frame f;
  for (int i = 0; i < 50; i++) TEST_ASSERT_EQUAL(RX_OK, p.deliver(p.ctrl, p.build(p.reader, MSG_TAMPER, (const uint8_t *)"\x00", 1), f));
  // Reader flash erased: its counter restarts at 1 and every frame is a replay.
  MapStore wiped;
  SecureLink fresh(SRC_READER, KEY, wiped);
  fresh.begin();
  TEST_ASSERT_EQUAL(RX_REPLAY, p.deliver(p.ctrl, p.build(fresh, MSG_HELLO), f));
  // The controller's authenticated HELLO tells it how far it got.
  Hello h;
  h.lastSeen = p.ctrl.rxLast();
  uint8_t pl[16];
  size_t n = packHello(h, pl);
  TEST_ASSERT_EQUAL(RX_OK, p.deliver(fresh, p.build(p.ctrl, MSG_HELLO, pl, n), f));
  TEST_ASSERT_EQUAL(RX_OK, p.deliver(p.ctrl, p.build(fresh, MSG_HELLO), f));
}

// ---- payloads ------------------------------------------------------------------------------
static Frame asFrame(uint8_t type, const uint8_t *p, size_t n) {
  Frame f;
  f.type = type;
  f.len = (uint8_t)n;
  memcpy(f.payload, p, n);
  return f;
}

void test_payload_round_trips() {
  uint8_t b[MAX_PAYLOAD];
  Hello h;
  h.flags = 6;
  h.uptimeS = 123456;
  h.lastSeen = 0xDEADBEEF;
  Hello h2;
  TEST_ASSERT_TRUE(unpackHello(asFrame(MSG_HELLO, b, packHello(h, b)), h2));
  TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, h2.lastSeen);
  TEST_ASSERT_EQUAL_UINT32(123456, h2.uptimeS);

  BandScan s;
  s.uidLen = 7;
  for (int i = 0; i < 7; i++) s.uid[i] = (uint8_t)(0x10 + i);
  BandScan s2;
  TEST_ASSERT_TRUE(unpackBandScan(asFrame(MSG_BAND_SCAN, b, packBandScan(s, b)), s2));
  TEST_ASSERT_EQUAL_HEX8_ARRAY(s.uid, s2.uid, 7);

  FingerMatch m{199, 250}, m2;
  TEST_ASSERT_TRUE(unpackFingerMatch(asFrame(MSG_FINGER_MATCH, b, packFingerMatch(m, b)), m2));
  TEST_ASSERT_EQUAL_UINT16(199, m2.page);
  TEST_ASSERT_EQUAL_UINT16(250, m2.score);

  FeedbackCmd fb{FB_NEED_FINGER, 8000}, fb2;
  TEST_ASSERT_TRUE(unpackFeedback(asFrame(MSG_FEEDBACK, b, packFeedback(fb, b)), fb2));
  TEST_ASSERT_EQUAL_UINT8(FB_NEED_FINGER, fb2.state);
  TEST_ASSERT_EQUAL_UINT16(8000, fb2.holdMs);

  EnrollResult er{12, ENROLL_MISMATCH}, er2;
  TEST_ASSERT_TRUE(unpackEnrollResult(asFrame(MSG_ENROLL_RESULT, b, packEnrollResult(er, b)), er2));
  TEST_ASSERT_EQUAL_UINT16(12, er2.page);
  TEST_ASSERT_EQUAL_UINT8(ENROLL_MISMATCH, er2.status);

  ReaderConfig rc{80, 140}, rc2;  // volume clamps to 100
  TEST_ASSERT_TRUE(unpackConfig(asFrame(MSG_SET_CONFIG, b, packConfig(rc, b)), rc2));
  TEST_ASSERT_EQUAL_UINT8(80, rc2.brightness);
  TEST_ASSERT_EQUAL_UINT8(100, rc2.volume);

  uint16_t pg = 0;
  TEST_ASSERT_TRUE(unpackU16(asFrame(MSG_ENROLL_FINGER, b, packU16(321, b)), pg));
  TEST_ASSERT_EQUAL_UINT16(321, pg);
}

void test_payload_rejects_malformed() {
  uint8_t shortUid[3] = {2, 1, 2};  // UIDs are 4..10 bytes
  BandScan s;
  TEST_ASSERT_FALSE(unpackBandScan(asFrame(MSG_BAND_SCAN, shortUid, 3), s));
  uint8_t lying[3] = {7, 1, 2};  // claims 7 bytes, carries 2
  TEST_ASSERT_FALSE(unpackBandScan(asFrame(MSG_BAND_SCAN, lying, 3), s));
  uint8_t badState[3] = {FB_COUNT, 0, 0};
  FeedbackCmd fb;
  TEST_ASSERT_FALSE(unpackFeedback(asFrame(MSG_FEEDBACK, badState, 3), fb));
  Hello h;
  TEST_ASSERT_FALSE(unpackHello(asFrame(MSG_HELLO, badState, 3), h));
  FingerMatch m;
  TEST_ASSERT_FALSE(unpackFingerMatch(asFrame(MSG_TAMPER, badState, 3), m));  // wrong type
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_vectors_encode_like_python);
  RUN_TEST(test_vectors_decode);
  RUN_TEST(test_round_trip_every_length);
  RUN_TEST(test_vectors_hello_caps);
  RUN_TEST(test_hello_caps_round_trip);
  RUN_TEST(test_encode_rejects_oversize);
  RUN_TEST(test_parse_need_more_when_truncated);
  RUN_TEST(test_parse_bad_sof);
  RUN_TEST(test_parse_bad_length);
  RUN_TEST(test_parse_bad_tag_any_bit);
  RUN_TEST(test_parse_wrong_key);
  RUN_TEST(test_decoder_back_to_back);
  RUN_TEST(test_decoder_skips_garbage_and_false_sof);
  RUN_TEST(test_decoder_recovers_after_corrupt_length);
  RUN_TEST(test_decoder_recovers_after_corrupt_sof);
  RUN_TEST(test_decoder_gap_drops_partial);
  RUN_TEST(test_replay_guard_window);
  RUN_TEST(test_replay_guard_persistence);
  RUN_TEST(test_tx_counter_reserves_blocks_and_never_reuses);
  RUN_TEST(test_tx_counter_bump_past);
  RUN_TEST(test_link_accepts_fresh_rejects_replay);
  RUN_TEST(test_link_rejects_reflected_frame);
  RUN_TEST(test_link_rejects_out_of_window);
  RUN_TEST(test_link_hello_resyncs_wiped_sender);
  RUN_TEST(test_payload_round_trips);
  RUN_TEST(test_payload_rejects_malformed);
  return UNITY_END();
}
