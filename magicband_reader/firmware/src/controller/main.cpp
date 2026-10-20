// Indoor controller (split mode): the only place access is decided.  Talks
// to the reader over the authenticated RS-485 link; the door logic, strike,
// inputs, NVS users and Home Assistant live in src/door (shared with the
// all-in-one reader).  Access works without Wi-Fi.  See README.md / PROTOCOL.md.

#include <Arduino.h>
#include <esp_task_wdt.h>

#include "config.h"
#include "door_app.h"
#include "link_port.h"
#include "mb_protocol.h"

using namespace mb;

static HardwareSerial busSerial(2);
static LinkPort bus(SRC_CONTROLLER);

// ---- front = the remote reader --------------------------------------------------------
void frontFeedback(uint8_t state, uint32_t holdMs) {
  FeedbackCmd f;
  f.state = state;
  f.holdMs = holdMs > 65535 ? 65535 : (uint16_t)holdMs;
  uint8_t p[4];
  bus.send(MSG_FEEDBACK, p, packFeedback(f, p));
}

void frontEnrollFinger(uint16_t page) {
  uint8_t p[2];
  bus.send(MSG_ENROLL_FINGER, p, packU16(page, p));
}

void frontDeleteFinger(uint16_t page) {
  uint8_t p[2];
  bus.send(MSG_DELETE_FINGER, p, packU16(page, p));
}

void frontConfig(uint8_t brightness, uint8_t volume) {
  ReaderConfig c;
  c.brightness = brightness;
  c.volume = volume;
  uint8_t p[4];
  bus.send(MSG_SET_CONFIG, p, packConfig(c, p));
}

// ---- reader events ---------------------------------------------------------------------------------
static struct {
  uint8_t type = 0, len = 0;
  uint8_t payload[MAX_PAYLOAD];
  uint32_t at = 0;
} lastEv;

// A reader event retransmitted because our FEEDBACK was lost: answer again,
// do not evaluate it twice.
static bool duplicate(const Frame &f) {
  uint32_t now = millis();
  bool dup = lastEv.at && now - lastEv.at < EVENT_DEDUP_MS && lastEv.type == f.type && lastEv.len == f.len &&
             memcmp(lastEv.payload, f.payload, f.len) == 0;
  lastEv.type = f.type;
  lastEv.len = f.len;
  memcpy(lastEv.payload, f.payload, f.len);
  lastEv.at = now;
  return dup;
}

static void handleFrame(const Frame &f) {
  if (f.type == MSG_HELLO) {
    Hello h;
    if (unpackHello(f, h)) {
      doorReaderCaps(h.caps);  // no CAP_FINGERPRINT: finger policies are denied, never downgraded
      doorReaderTamper(h.flags & HELLO_TAMPER, false);
    }
    return;
  }
  if (f.type == MSG_TAMPER) {
    uint8_t v;
    if (unpackU8(f, v)) doorReaderTamper(v, true);
    return;
  }
  if (duplicate(f)) {
    doorResendFeedback();
    return;
  }
  switch (f.type) {
    case MSG_BAND_SCAN: {
      BandScan b;
      if (unpackBandScan(f, b)) doorBand(b.uid, b.uidLen);
      break;
    }
    case MSG_FINGER_MATCH: {
      FingerMatch m;
      if (unpackFingerMatch(f, m))
        doorFinger(m.page);
      else
        doorFingerNoMatch();
      break;
    }
    case MSG_FINGER_NOMATCH:
      doorFingerNoMatch();
      break;
    case MSG_ENROLL_RESULT: {
      EnrollResult r;
      if (unpackEnrollResult(f, r)) doorEnrollResult(r.page, r.status);
      break;
    }
    default:
      break;
  }
}

// ---- link supervision ----------------------------------------------------------------------------------
static void superviseLink() {
  uint32_t now = millis();
  static uint32_t helloAt = 0, errWindowAt = 0, errBase = 0;
  static bool alarm = false;
  if (now - helloAt >= HELLO_INTERVAL_MS) {
    helloAt = now;
    Hello h;
    h.fwMajor = FW_VERSION_MAJOR;
    h.fwMinor = FW_VERSION_MINOR;
    h.flags = doorIsOpen() ? HELLO_DOOR_OPEN : 0;
    h.uptimeS = now / 1000;
    h.lastSeen = bus.rxLast();
    uint8_t p[MAX_PAYLOAD];
    bus.send(MSG_HELLO, p, packHello(h, p));
  }
  bool online = bus.peerOnline();
  digitalWrite(PIN_LED, online ? HIGH : LOW);
  doorReaderOnline(online);
  if (now - errWindowAt >= 60000) {  // forged / replayed frames per minute
    uint32_t r = bus.rejected();
    alarm = r - errBase >= LINK_ERROR_ALERT;
    errBase = r;
    errWindowAt = now;
  }
  doorLinkErrors(bus.rejected(), alarm);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED, OUTPUT);
  bus.begin(busSerial, PIN_RS485_RX, PIN_RS485_TX, PIN_RS485_DE, LINK_BAUD);
  doorBegin();
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  esp_task_wdt_add(nullptr);
  log_i("controller %s up", FW_VERSION);
}

void loop() {
  esp_task_wdt_reset();
  Frame f;
  while (bus.poll(f)) handleFrame(f);
  superviseLink();
  doorLoop();
  delay(1);
}
