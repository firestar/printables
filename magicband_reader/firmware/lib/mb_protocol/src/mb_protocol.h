#pragma once
// Reader <-> controller RS-485 link: framing, HMAC tag, replay guard,
// persistent counters and message payloads.  Platform independent (no
// Arduino headers); see PROTOCOL.md for the byte layout.

#include <stddef.h>
#include <stdint.h>

namespace mb {

// ---- framing ------------------------------------------------------------------
static const uint8_t SOF = 0xA5;
static const uint8_t PROTO_VERSION = 2;  // 2: HELLO carries a capability byte
static const size_t KEY_LEN = 32;
static const size_t HEADER_LEN = 8;  // SOF, LEN, SRC, TYPE, CTR[4]
static const size_t TAG_LEN = 16;    // HMAC-SHA256 truncated
static const size_t MAX_PAYLOAD = 32;
static const size_t MAX_FRAME = HEADER_LEN + MAX_PAYLOAD + TAG_LEN;
static const uint32_t FRAME_GAP_MS = 20;  // inter-byte gap that drops a partial frame

enum Source : uint8_t { SRC_READER = 'R', SRC_CONTROLLER = 'C' };

enum MsgType : uint8_t {
  MSG_HELLO = 0x01,           // both ways, heartbeat
  MSG_BAND_SCAN = 0x10,       // R->C
  MSG_FINGER_MATCH = 0x11,    // R->C
  MSG_FINGER_NOMATCH = 0x12,  // R->C
  MSG_TAMPER = 0x13,          // R->C
  MSG_ENROLL_RESULT = 0x14,   // R->C
  MSG_FEEDBACK = 0x20,        // C->R
  MSG_ENROLL_FINGER = 0x21,   // C->R
  MSG_SET_CONFIG = 0x22,      // C->R
  MSG_DELETE_FINGER = 0x23,   // C->R
};

struct Frame {
  uint8_t src = 0;
  uint8_t type = 0;
  uint32_t ctr = 0;
  uint8_t len = 0;
  uint8_t payload[MAX_PAYLOAD] = {0};
};

// Builds a complete frame into `out`.  Returns its length, 0 on error
// (payload too long or `cap` too small).
size_t encodeFrame(const uint8_t key[KEY_LEN], uint8_t src, uint8_t type, uint32_t ctr,
                   const uint8_t *payload, size_t len, uint8_t *out, size_t cap);

enum ParseResult : uint8_t { PARSE_OK, PARSE_NEED_MORE, PARSE_BAD_SOF, PARSE_BAD_LEN, PARSE_BAD_TAG };

// Parses one frame that starts at buf[0].  On PARSE_OK `*consumed` is the
// frame length.  Never reads past `n`.
ParseResult parseFrame(const uint8_t key[KEY_LEN], const uint8_t *buf, size_t n, Frame &out,
                       size_t *consumed);

// Streaming decoder with resync: bad SOF/length/tag drops one byte and
// rescans for the next SOF.  A gap > FRAME_GAP_MS discards a partial frame.
class FrameDecoder {
 public:
  explicit FrameDecoder(const uint8_t key[KEY_LEN]) : key_(key) {}
  // Returns true when `out` holds a frame with a valid tag.
  bool push(uint8_t b, uint32_t nowMs, Frame &out);
  void reset() { n_ = 0; }
  uint32_t badTag = 0, badLen = 0, dropped = 0;

 private:
  void drop(size_t k);
  const uint8_t *key_;
  uint8_t buf_[MAX_FRAME];
  size_t n_ = 0;
  uint32_t lastMs_ = 0;
};

// ---- counters -----------------------------------------------------------------
// Persistent storage for counters (NVS on the ESP32, a map in tests).
class CounterStore {
 public:
  virtual ~CounterStore() {}
  virtual bool load(const char *key, uint32_t &v) = 0;
  virtual void save(const char *key, uint32_t v) = 0;
};

// Outgoing counter.  Persists a reservation `block` ahead so flash is
// written once per `block` frames; after a reboot counting resumes above the
// reservation, so a counter value is never reused.
class TxCounter {
 public:
  TxCounter(CounterStore &store, const char *key, uint32_t block) : store_(store), key_(key), block_(block) {}
  void begin();
  uint32_t next();
  uint32_t current() const { return cur_; }
  // Peer told us (authenticated HELLO) it has already seen `v`: jump past it.
  void bumpPast(uint32_t v);

 private:
  void reserve(uint32_t upTo);
  CounterStore &store_;
  const char *key_;
  uint32_t block_;
  uint32_t cur_ = 0, reserved_ = 0;
};

enum Verdict : uint8_t { CTR_FRESH, CTR_REPLAY, CTR_OUT_OF_WINDOW };

// Incoming counter: accepts last < ctr <= last + window.
class ReplayGuard {
 public:
  ReplayGuard(CounterStore &store, const char *key, uint32_t window, uint32_t persistStep)
      : store_(store), key_(key), window_(window), step_(persistStep) {}
  void begin();
  Verdict check(uint32_t ctr) const;
  // Records ctr as seen.  `important` frames (scans, commands) are persisted
  // at once; heartbeats only every `persistStep` so flash is not worn out.
  void accept(uint32_t ctr, bool important);
  uint32_t last() const { return last_; }

 private:
  CounterStore &store_;
  const char *key_;
  uint32_t window_, step_;
  uint32_t last_ = 0, saved_ = 0;
};

// ---- link -----------------------------------------------------------------------
struct LinkConfig {
  uint32_t txReserveBlock = 1024;
  uint32_t rxWindow = 1u << 20;
  uint32_t rxPersistStep = 256;
};

enum RxStatus : uint8_t { RX_NONE, RX_OK, RX_REPLAY, RX_OUT_OF_WINDOW, RX_WRONG_SRC };

struct LinkStats {
  uint32_t ok = 0, replay = 0, window = 0, wrongSrc = 0;
};

// One end of the link: frames/unframes, counts, rejects replays.
class SecureLink {
 public:
  SecureLink(uint8_t self, const uint8_t key[KEY_LEN], CounterStore &store, const LinkConfig &cfg = LinkConfig());
  void begin();
  // Builds the next outgoing frame (fresh counter).  Returns length or 0.
  size_t build(uint8_t type, const uint8_t *payload, size_t len, uint8_t *out, size_t cap);
  // Feeds one received byte.  RX_OK = `out` holds a fresh, authentic frame
  // from the peer.  A HELLO's lastSeen field moves our tx counter forward.
  RxStatus push(uint8_t b, uint32_t nowMs, Frame &out);
  uint32_t rxLast() const { return rx_.last(); }
  uint32_t txCurrent() const { return tx_.current(); }
  const FrameDecoder &decoder() const { return dec_; }
  LinkStats stats;

 private:
  uint8_t self_, peer_;
  const uint8_t *key_;
  TxCounter tx_;
  ReplayGuard rx_;
  FrameDecoder dec_;
};

// ---- payloads ---------------------------------------------------------------------
static const size_t UID_MAX = 10;

enum Feedback : uint8_t {
  FB_IDLE = 0,
  FB_READING = 1,
  FB_NEED_FINGER = 2,
  FB_GRANTED = 3,
  FB_DENIED = 4,
  FB_ERROR = 5,
  FB_OFFLINE = 6,  // reader-local: no controller heartbeat
  FB_ENROLL_BAND = 7,
  FB_ENROLL_FINGER = 8,
  FB_ENROLL_OK = 9,
  FB_ENROLL_FAIL = 10,
  FB_LOCKOUT = 11,
  FB_COUNT
};

enum NoMatchReason : uint8_t { NOMATCH_NO_MATCH = 0, NOMATCH_BAD_IMAGE = 1, NOMATCH_SENSOR_ERROR = 2 };
enum EnrollStatus : uint8_t { ENROLL_OK = 0, ENROLL_TIMEOUT = 1, ENROLL_MISMATCH = 2, ENROLL_SENSOR_ERROR = 3, ENROLL_STORE_FAIL = 4 };
static const uint8_t HELLO_TAMPER = 0x01;      // reader: hatch open
static const uint8_t HELLO_NFC_OK = 0x02;      // reader: PN532 answered
static const uint8_t HELLO_FINGER_OK = 0x04;   // reader: R503 answered
static const uint8_t HELLO_DOOR_OPEN = 0x01;   // controller: door contact open

// HELLO.caps: what the sender was built with (static, unlike the health flags).
static const uint8_t CAP_FINGERPRINT = 0x01;  // reader: R503 fitted (HAS_FINGERPRINT=1)
static const uint8_t CAP_NFC = 0x02;          // reader: PN532 fitted
// A v1 HELLO (12 bytes, no caps byte) comes from a reader that always had both.
static const uint8_t CAPS_V1 = CAP_FINGERPRINT | CAP_NFC;

struct Hello {
  uint8_t proto = PROTO_VERSION;
  uint8_t fwMajor = 0, fwMinor = 0;
  uint8_t flags = 0;
  uint32_t uptimeS = 0;
  uint32_t lastSeen = 0;  // highest counter received from the peer
  uint8_t caps = 0;       // CAP_* bits
};
struct BandScan {
  uint8_t uidLen = 0;
  uint8_t uid[UID_MAX] = {0};
};
struct FingerMatch {
  uint16_t page = 0;
  uint16_t score = 0;
};
struct FeedbackCmd {
  uint8_t state = FB_IDLE;
  uint16_t holdMs = 0;  // reader falls back to IDLE after this; 0 = stay
};
struct EnrollResult {
  uint16_t page = 0;
  uint8_t status = ENROLL_OK;
};
struct ReaderConfig {
  uint8_t brightness = 0;  // 0-255, reader clamps to its power cap
  uint8_t volume = 0;      // 0-100
};

size_t packHello(const Hello &m, uint8_t *p);
bool unpackHello(const Frame &f, Hello &m);
size_t packBandScan(const BandScan &m, uint8_t *p);
bool unpackBandScan(const Frame &f, BandScan &m);
size_t packFingerMatch(const FingerMatch &m, uint8_t *p);
bool unpackFingerMatch(const Frame &f, FingerMatch &m);
size_t packU8(uint8_t v, uint8_t *p);  // FINGER_NOMATCH reason, TAMPER state
bool unpackU8(const Frame &f, uint8_t &v);
size_t packU16(uint16_t v, uint8_t *p);  // ENROLL_FINGER / DELETE_FINGER page
bool unpackU16(const Frame &f, uint16_t &v);
size_t packFeedback(const FeedbackCmd &m, uint8_t *p);
bool unpackFeedback(const Frame &f, FeedbackCmd &m);
size_t packEnrollResult(const EnrollResult &m, uint8_t *p);
bool unpackEnrollResult(const Frame &f, EnrollResult &m);
size_t packConfig(const ReaderConfig &m, uint8_t *p);
bool unpackConfig(const Frame &f, ReaderConfig &m);

const char *msgName(uint8_t type);
const char *feedbackName(uint8_t state);

}  // namespace mb
