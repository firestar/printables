// MagicBand reader, ESP32-S3-Zero.  Build variants (config.h):
//   split (ALL_IN_ONE=0): outdoor pod.  Reports band scans, fingerprint
//     matches and tamper to the indoor controller over the authenticated
//     RS-485 link and renders the feedback the controller commands.  It makes
//     no access decisions and has no Wi-Fi.  HELLO announces CAP_FINGERPRINT.
//   all-in-one (ALL_IN_ONE=1): reader on the secure side of the door.  The
//     same NFC / R503 / LED / audio code feeds the door app (src/door: access
//     engine, NVS users, strike, REX, door contact, Wi-Fi/MQTT) directly.
//   HAS_FINGERPRINT=0: no R503; band only.
// See README.md / PROTOCOL.md.

#include "config.h"  // first: HAS_FINGERPRINT / ALL_IN_ONE defaults pick the includes below

#if HAS_FINGERPRINT
#include <Adafruit_Fingerprint.h>
#endif
#include <Adafruit_PN532.h>
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>

#include "audio.h"
#include "leds.h"
#include "mb_protocol.h"
#if ALL_IN_ONE
#include <esp_task_wdt.h>

#include "door_app.h"
#else
#include "link_port.h"
#endif

using namespace mb;

static Adafruit_PN532 nfc(PIN_PN532_IRQ, PIN_PN532_RST, &Wire);
#if HAS_FINGERPRINT
static HardwareSerial fpSerial(1);
static Adafruit_Fingerprint finger(&fpSerial);
#endif
#if !ALL_IN_ONE
static HardwareSerial busSerial(2);
static LinkPort bus(SRC_READER);
#endif

static bool nfcOk = false;
[[maybe_unused]] static bool fpOk = false;  // stays false without an R503
static bool tamperOpen = false;

// ---- feedback state ---------------------------------------------------------------
static uint8_t ctrlState = FB_IDLE;  // last state commanded by the controller / door app
static uint32_t ctrlStateUntil = 0;  // 0 = hold until the next command
static uint8_t shownState = 0xFF;

static void setLocal(uint8_t s, uint32_t holdMs) {
  ctrlState = s;
  ctrlStateUntil = holdMs ? millis() + holdMs : 0;
  if (ctrlStateUntil == 0 && holdMs) ctrlStateUntil = 1;
}

static void fingerLed(uint8_t s) {
#if HAS_FINGERPRINT
  if (!fpOk) return;
  switch (s) {
    case FB_NEED_FINGER: finger.LEDcontrol(FINGERPRINT_LED_BREATHING, 100, FINGERPRINT_LED_BLUE, 0); break;
    case FB_ENROLL_FINGER: finger.LEDcontrol(FINGERPRINT_LED_BREATHING, 100, FINGERPRINT_LED_PURPLE, 0); break;
    case FB_GRANTED:
    case FB_ENROLL_OK: finger.LEDcontrol(FINGERPRINT_LED_ON, 0, FINGERPRINT_LED_PURPLE, 0); break;
    case FB_DENIED:
    case FB_LOCKOUT:
    case FB_ENROLL_FAIL: finger.LEDcontrol(FINGERPRINT_LED_FLASHING, 25, FINGERPRINT_LED_RED, 3); break;
    default: finger.LEDcontrol(FINGERPRINT_LED_OFF, 0, FINGERPRINT_LED_BLUE, 0); break;
  }
#else
  (void)s;
#endif
}

static bool peerOnline() {
#if ALL_IN_ONE
  return true;  // the door app is in this chip
#else
  return bus.peerOnline();
#endif
}

static void updateDisplay() {
  uint32_t now = millis();
  if (ctrlStateUntil && (int32_t)(now - ctrlStateUntil) >= 0) {
    ctrlState = FB_IDLE;
    ctrlStateUntil = 0;
  }
  uint8_t s = ctrlState;
  if (!peerOnline() && s != FB_READING) s = FB_OFFLINE;
  if (s == shownState) return;
  shownState = s;
  ledsSetState(s);
  fingerLed(s);
}

static void onFeedback(const FeedbackCmd &f);
static void applyConfig(const ReaderConfig &c) {
  ledsSetBrightness(c.brightness);
  audioSetVolume(c.volume);
}

// ---- uplink: reader events -> controller (split) or door app (all-in-one) -----------
#if !ALL_IN_ONE
// Event waiting for a FEEDBACK reply (retransmitted as a new frame if lost).
static struct {
  bool active = false;
  uint8_t type = 0;
  uint8_t payload[MAX_PAYLOAD];
  size_t len = 0;
  uint32_t sentAt = 0;
  uint8_t retries = 0;
} pendingEv;

static void sendEvent(uint8_t type, const uint8_t *p, size_t n) {
  pendingEv.active = true;
  pendingEv.type = type;
  memcpy(pendingEv.payload, p, n);
  pendingEv.len = n;
  pendingEv.sentAt = millis();
  pendingEv.retries = 0;
  bus.send(type, p, n);
}
#else
// Finished R503 enrollments are handed to the door app from loop(), not from
// inside the door app's own call that started them.
static struct {
  bool ready = false;
  EnrollResult r;
} enrollOut;
#endif

static void emitBand(const BandScan &b) {
#if ALL_IN_ONE
  doorBand(b.uid, b.uidLen);
#else
  uint8_t p[MAX_PAYLOAD];
  sendEvent(MSG_BAND_SCAN, p, packBandScan(b, p));
#endif
}

#if HAS_FINGERPRINT
static void emitFinger(const FingerMatch &m) {
#if ALL_IN_ONE
  doorFinger(m.page);
#else
  uint8_t p[MAX_PAYLOAD];
  sendEvent(MSG_FINGER_MATCH, p, packFingerMatch(m, p));
#endif
}

static void emitNoMatch(uint8_t reason) {
#if ALL_IN_ONE
  (void)reason;
  doorFingerNoMatch();
#else
  uint8_t p[MAX_PAYLOAD];
  sendEvent(MSG_FINGER_NOMATCH, p, packU8(reason, p));
#endif
}
#endif

static void emitEnrollResult(const EnrollResult &r) {
#if ALL_IN_ONE
  enrollOut.r = r;
  enrollOut.ready = true;
#else
  uint8_t p[4];
  sendEvent(MSG_ENROLL_RESULT, p, packEnrollResult(r, p));
#endif
}

static void emitTamper(bool open) {
#if ALL_IN_ONE
  doorReaderTamper(open, true);
#else
  uint8_t p[1];
  bus.send(MSG_TAMPER, p, packU8(open ? 1 : 0, p));
#endif
}

// ---- tamper -----------------------------------------------------------------------------
static bool readTamper() {
#if HAS_TAMPER_SWITCH
  return digitalRead(PIN_TAMPER) == HIGH;  // switch to GND opens with the hatch
#else
  return false;
#endif
}

static void pollTamper() {
  static bool raw = false;
  static uint32_t changed = 0;
  bool open = readTamper();
  if (open != raw) {
    raw = open;
    changed = millis();
  }
  if (raw != tamperOpen && millis() - changed >= TAMPER_DEBOUNCE_MS) {
    tamperOpen = raw;
    emitTamper(tamperOpen);
    log_w("tamper %s", tamperOpen ? "OPEN" : "closed");
  }
}

// ---- NFC (PN532, IRQ driven) --------------------------------------------------------------
static uint32_t nfcArmAt = 0, nfcCheckAt = 0;
static bool nfcArmed = false;
static uint8_t lastUid[UID_MAX];
static uint8_t lastUidLen = 0;
static uint32_t lastUidAt = 0;

static void nfcInit() {
  nfc.begin();
  uint32_t v = nfc.getFirmwareVersion();
  nfcOk = v != 0;
  if (!nfcOk) {
    log_e("PN532 not found");
    return;
  }
  log_i("PN532 firmware %u.%u", (unsigned)(v >> 16) & 0xFF, (unsigned)(v >> 8) & 0xFF);
  nfc.SAMConfig();
  nfcArmed = false;
}

static void pollNfc() {
  uint32_t now = millis();
  if (now >= nfcCheckAt) {  // health check (also clears a stuck detection)
    nfcCheckAt = now + 60000;
    nfcInit();
  }
  if (!nfcOk) return;
  if (!nfcArmed) {
    if ((int32_t)(now - nfcArmAt) < 0) return;
    nfc.startPassiveTargetIDDetection(PN532_MIFARE_ISO14443A);
    nfcArmed = true;
    return;
  }
  if (digitalRead(PIN_PN532_IRQ) != LOW) return;
  uint8_t uid[UID_MAX] = {0};
  uint8_t len = 0;
  bool ok = nfc.readDetectedPassiveTargetID(uid, &len);
  nfcArmed = false;
  nfcArmAt = now + 150;
  if (!ok || len < 4 || len > UID_MAX) return;
  bool same = len == lastUidLen && memcmp(uid, lastUid, len) == 0;
  bool repeat = same && now - lastUidAt < NFC_REPEAT_MS;
  lastUidAt = now;  // a band held at the pod keeps refreshing this
  if (repeat) return;
  memcpy(lastUid, uid, len);
  lastUidLen = len;
  BandScan b;
  b.uidLen = len;
  memcpy(b.uid, uid, len);
  setLocal(FB_READING, FEEDBACK_TIMEOUT_MS * (EVENT_RETRIES + 1));  // before: the all-in-one answers at once
  audioPlay(CUE_READ);
  emitBand(b);
}

// ---- fingerprint (R503) ---------------------------------------------------------------------
#if HAS_FINGERPRINT
enum EnrollStep : uint8_t { EN_NONE, EN_FIRST, EN_LIFT, EN_SECOND };
static EnrollStep enStep = EN_NONE;
static uint16_t enPage = 0;
static uint32_t enDeadline = 0;
static uint32_t fpNextPoll = 0;
static bool fpWaitLift = false;

static bool touching() {
  bool hi = digitalRead(PIN_FP_TOUCH) == HIGH;
  return FP_TOUCH_ACTIVE_HIGH ? hi : !hi;
}

static void fpInit() {
  fpSerial.begin(FP_BAUD, SERIAL_8N1, PIN_FP_RX, PIN_FP_TX);
  fpOk = finger.verifyPassword();
  if (fpOk) {
    finger.getParameters();
    log_i("R503 ok, capacity %u", finger.capacity);
  } else {
    log_e("R503 not found");
  }
}
#endif

static void enrollDone(uint16_t page, uint8_t status) {
  EnrollResult r;
  r.page = page;
  r.status = status;
#if HAS_FINGERPRINT
  enStep = EN_NONE;
#endif
  emitEnrollResult(r);
  log_i("enroll page %u -> status %u", page, status);
}

// R503 two-touch enrollment into `page` (ENROLL_FINGER from the controller,
// or the door app in the all-in-one).
static void startFingerEnroll(uint16_t page) {
#if HAS_FINGERPRINT
  if (!fpOk) return enrollDone(page, ENROLL_SENSOR_ERROR);
  enPage = page;
  enStep = EN_FIRST;
  enDeadline = millis() + FP_ENROLL_TIMEOUT_MS;
  setLocal(FB_ENROLL_FINGER, 0);
#else
  enrollDone(page, ENROLL_SENSOR_ERROR);  // no R503 on this build
#endif
}

static void deleteFinger(uint16_t page) {
#if HAS_FINGERPRINT
  if (!fpOk) return;
  if (page == 0xFFFF)
    finger.emptyDatabase();
  else
    finger.deleteModel(page);
#else
  (void)page;
#endif
}

#if HAS_FINGERPRINT
static void pollEnroll(uint32_t now) {
  if ((int32_t)(now - enDeadline) >= 0) return enrollDone(enPage, ENROLL_TIMEOUT);
  uint8_t r = finger.getImage();
  switch (enStep) {
    case EN_FIRST:
      if (r != FINGERPRINT_OK) return;
      if (finger.image2Tz(1) != FINGERPRINT_OK) return;  // smudged: just try again
      finger.LEDcontrol(FINGERPRINT_LED_FLASHING, 25, FINGERPRINT_LED_PURPLE, 2);
      audioPlay(CUE_READ);
      enStep = EN_LIFT;
      return;
    case EN_LIFT:
      if (r == FINGERPRINT_NOFINGER) {
        finger.LEDcontrol(FINGERPRINT_LED_BREATHING, 100, FINGERPRINT_LED_PURPLE, 0);
        enStep = EN_SECOND;
      }
      return;
    case EN_SECOND: {
      if (r != FINGERPRINT_OK) return;
      if (finger.image2Tz(2) != FINGERPRINT_OK) return;
      uint8_t m = finger.createModel();
      if (m == FINGERPRINT_ENROLLMISMATCH) return enrollDone(enPage, ENROLL_MISMATCH);
      if (m != FINGERPRINT_OK) return enrollDone(enPage, ENROLL_SENSOR_ERROR);
      return enrollDone(enPage, finger.storeModel(enPage) == FINGERPRINT_OK ? ENROLL_OK : ENROLL_STORE_FAIL);
    }
    default:
      return;
  }
}

static void pollFinger() {
  if (!fpOk) return;
  uint32_t now = millis();
  if ((int32_t)(now - fpNextPoll) < 0) return;
  fpNextPoll = now + 100;
  if (enStep != EN_NONE) return pollEnroll(now);
  bool want = touching() || ctrlState == FB_NEED_FINGER;  // also poll if WAKEUP is not wired
  if (fpWaitLift) {
    if (!touching() && finger.getImage() == FINGERPRINT_NOFINGER) fpWaitLift = false;
    return;
  }
  if (!want) return;
  uint8_t r = finger.getImage();
  if (r == FINGERPRINT_NOFINGER) return;
  fpWaitLift = true;
  fpNextPoll = now + 400;
  if (r != FINGERPRINT_OK || finger.image2Tz(1) != FINGERPRINT_OK) {
    emitNoMatch(r == FINGERPRINT_OK ? NOMATCH_BAD_IMAGE : NOMATCH_SENSOR_ERROR);
    return;
  }
  r = finger.fingerSearch(1);
  setLocal(FB_READING, FEEDBACK_TIMEOUT_MS * (EVENT_RETRIES + 1));
  if (r == FINGERPRINT_OK && finger.confidence >= FP_MIN_SCORE) {
    FingerMatch m;
    m.page = finger.fingerID;
    m.score = finger.confidence;
    emitFinger(m);
  } else {
    emitNoMatch(NOMATCH_NO_MATCH);
  }
}
#endif

// ---- feedback in ------------------------------------------------------------------------------
static void onFeedback(const FeedbackCmd &f) {
#if !ALL_IN_ONE
  pendingEv.active = false;
#endif
  setLocal(f.state, f.holdMs);
  switch (f.state) {
    case FB_GRANTED: audioPlay(CUE_GRANTED); break;
    case FB_DENIED:
    case FB_LOCKOUT: audioPlay(CUE_DENIED); break;
    case FB_NEED_FINGER: audioPlay(CUE_NEED_FINGER); break;
    case FB_ENROLL_OK: audioPlay(CUE_ENROLL_OK); break;
    case FB_ERROR:
    case FB_ENROLL_FAIL: audioPlay(CUE_ERROR); break;
    default: break;
  }
  shownState = 0xFF;  // re-apply even if the state did not change (R503 ring)
}

static uint8_t capabilities() { return CAP_NFC | (HAS_FINGERPRINT ? CAP_FINGERPRINT : 0); }

#if ALL_IN_ONE
// ---- front for the local door app ---------------------------------------------------------------
void frontFeedback(uint8_t state, uint32_t holdMs) {
  FeedbackCmd f;
  f.state = state;
  f.holdMs = holdMs > 65535 ? 65535 : (uint16_t)holdMs;
  onFeedback(f);
}
void frontEnrollFinger(uint16_t page) { startFingerEnroll(page); }
void frontDeleteFinger(uint16_t page) { deleteFinger(page); }
void frontConfig(uint8_t brightness, uint8_t volume) {
  ReaderConfig c;
  c.brightness = brightness;
  c.volume = volume > 100 ? 100 : volume;
  applyConfig(c);
}

#else
// ---- link -----------------------------------------------------------------------------------
static void handleFrame(const Frame &f) {
  switch (f.type) {
    case MSG_FEEDBACK: {
      FeedbackCmd fb;
      if (unpackFeedback(f, fb)) onFeedback(fb);
      break;
    }
    case MSG_ENROLL_FINGER: {
      uint16_t page;
      if (unpackU16(f, page)) startFingerEnroll(page);
      break;
    }
    case MSG_DELETE_FINGER: {
      uint16_t page;
      if (unpackU16(f, page)) deleteFinger(page);
      break;
    }
    case MSG_SET_CONFIG: {
      ReaderConfig c;
      if (unpackConfig(f, c)) applyConfig(c);
      break;
    }
    default:
      break;  // HELLO: liveness is tracked by LinkPort
  }
}

static void sendHello() {
  Hello h;
  h.fwMajor = FW_VERSION_MAJOR;
  h.fwMinor = FW_VERSION_MINOR;
  h.flags = (tamperOpen ? HELLO_TAMPER : 0) | (nfcOk ? HELLO_NFC_OK : 0) | (fpOk ? HELLO_FINGER_OK : 0);
  h.uptimeS = millis() / 1000;
  h.lastSeen = bus.rxLast();
  h.caps = capabilities();
  uint8_t p[MAX_PAYLOAD];
  bus.send(MSG_HELLO, p, packHello(h, p));
}

static void pollLink() {
  Frame f;
  while (bus.poll(f)) handleFrame(f);
  uint32_t now = millis();
  static uint32_t helloAt = 0;
  if (now - helloAt >= HELLO_INTERVAL_MS) {
    helloAt = now;
    sendHello();
  }
  if (pendingEv.active && now - pendingEv.sentAt >= FEEDBACK_TIMEOUT_MS) {
    if (pendingEv.retries < EVENT_RETRIES) {
      pendingEv.retries++;
      pendingEv.sentAt = now;
      bus.send(pendingEv.type, pendingEv.payload, pendingEv.len);
    } else {
      pendingEv.active = false;
      setLocal(FB_ERROR, 2000);
      audioPlay(CUE_ERROR);
    }
  }
}
#endif

void setup() {
  Serial.begin(115200);
#if !ALL_IN_ONE
  WiFi.mode(WIFI_OFF);  // the split reader never uses radio
#endif
  btStop();
  pinMode(PIN_TAMPER, INPUT_PULLUP);
  pinMode(PIN_PN532_IRQ, INPUT_PULLUP);
  ledsBegin();
  audioBegin();
  Wire.setPins(PIN_I2C_SDA, PIN_I2C_SCL);
  Wire.begin();
#if HAS_FINGERPRINT
  pinMode(PIN_FP_TOUCH, INPUT);
  fpInit();
#endif
  nfcCheckAt = 0;  // pollNfc() initialises the PN532 on its first run
  tamperOpen = readTamper();
#if ALL_IN_ONE
  doorBegin();
  doorReaderCaps(capabilities());
  doorReaderTamper(tamperOpen, false);
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  esp_task_wdt_add(nullptr);
  log_i("all-in-one %s up: nfc=%d finger=%d tamper=%d", FW_VERSION, nfcOk, fpOk, tamperOpen);
#else
  bus.begin(busSerial, PIN_RS485_RX, PIN_RS485_TX, PIN_RS485_DE, LINK_BAUD);
  log_i("reader %s up: caps=0x%02x finger=%d tamper=%d", FW_VERSION, capabilities(), fpOk, tamperOpen);
#endif
}

void loop() {
#if ALL_IN_ONE
  esp_task_wdt_reset();
  if (enrollOut.ready) {
    enrollOut.ready = false;
    doorEnrollResult(enrollOut.r.page, enrollOut.r.status);
  }
  doorLoop();
#else
  pollLink();
#endif
  pollTamper();
  pollNfc();
#if HAS_FINGERPRINT
  pollFinger();
#endif
  updateDisplay();
  ledsLoop();
  delay(1);
}
