// Rotating aeroponic grow tower - ESP32 firmware
//
// Cycles a 12 V pump (or, in fog mode, an ultrasonic fogger + duct fan with
// short pump flushes) on a day/night schedule and turns the tower with a
// 28BYJ-48 stepper.  Stops pump/fogger/fan on low water and the stepper on a stall.
// Web UI + REST API on http://growtower.local/ (see web.cpp, README.md).
// The schedule itself lives in scheduler.cpp (pure, unit-tested).

#include <Arduino.h>
#include <ArduinoOTA.h>
#include <DallasTemperature.h>
#include <ESPmDNS.h>
#include <OneWire.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <esp_task_wdt.h>
#include <esp_timer.h>

#include "app.h"
#include "config.h"
#include "motor.h"
#include "scheduler.h"
#include "web.h"

namespace app {
sched::Scheduler scheduler;
Telemetry tele;
String tz = TZ_DEFAULT;
}  // namespace app

static Preferences prefs;
static WiFiManager wm;
static OneWire oneWire(PIN_ONEWIRE);
static DallasTemperature ds(&oneWire);

static volatile uint32_t revCount = 0;
static volatile uint32_t lastRevMs = 0;
static bool servicesUp = false;
static bool otaActive = false;  // forces all outputs off during an update
static uint32_t lastWifiTry = 0, lastControl = 0, lastTempReq = 0;
static bool tempPending = false;
static bool lastPump = false, lastFog = false, lastFan = false;

// ---------------------------------------------------------------------------
// app helpers
// ---------------------------------------------------------------------------
uint32_t app::nowS() { return (uint32_t)(esp_timer_get_time() / 1000000ULL); }

bool app::localTime(struct tm &t) {
  time_t now = time(nullptr);
  if (now < 1700000000) return false;  // SNTP has not synced yet
  localtime_r(&now, &t);
  return true;
}

static void applyTz() {
  setenv("TZ", app::tz.c_str(), 1);
  tzset();
}

void app::saveConfig() {
  const sched::Config &c = scheduler.config();
  prefs.putUShort("don", c.dayOnMin);
  prefs.putUShort("doff", c.dayOffMin);
  prefs.putUShort("non", c.nightOnMin);
  prefs.putUShort("noff", c.nightOffMin);
  prefs.putUShort("dstart", c.dayStartMin);
  prefs.putUShort("dend", c.dayEndMin);
  prefs.putUChar("rmode", c.rotMode);
  prefs.putUShort("rstep", c.rotStepDeg);
  prefs.putUShort("rdph", c.rotDegPerHour);
  prefs.putBool("rnight", c.rotAtNight);
  prefs.putBool("rsens", c.revSensor);
  prefs.putUShort("stallp", c.stallPct);
  prefs.putUShort("speed", c.motorSpeed);
  prefs.putUShort("mto", c.manualTimeoutMin);
  prefs.putUChar("feed", c.feedMode);
  prefs.putUShort("fdon", c.fogDayOnMin);
  prefs.putUShort("fdoff", c.fogDayOffMin);
  prefs.putUShort("fnon", c.fogNightOnMin);
  prefs.putUShort("fnoff", c.fogNightOffMin);
  prefs.putUShort("fanro", c.fanRunOnS);
  prefs.putUShort("fmaxt", c.fogMaxTempC);
  prefs.putUShort("flon", c.flushOnMin);
  prefs.putUShort("floff", c.flushOffMin);
  prefs.putString("tz", tz);
  applyTz();
}

static void loadConfig() {
  prefs.begin("growtower", false);
  sched::Config c;
  c.dayOnMin = prefs.getUShort("don", c.dayOnMin);
  c.dayOffMin = prefs.getUShort("doff", c.dayOffMin);
  c.nightOnMin = prefs.getUShort("non", c.nightOnMin);
  c.nightOffMin = prefs.getUShort("noff", c.nightOffMin);
  c.dayStartMin = prefs.getUShort("dstart", c.dayStartMin);
  c.dayEndMin = prefs.getUShort("dend", c.dayEndMin);
  c.rotMode = prefs.getUChar("rmode", c.rotMode);
  c.rotStepDeg = prefs.getUShort("rstep", c.rotStepDeg);
  c.rotDegPerHour = prefs.getUShort("rdph", c.rotDegPerHour);
  c.rotAtNight = prefs.getBool("rnight", c.rotAtNight);
  c.revSensor = prefs.getBool("rsens", c.revSensor);
  c.stallPct = prefs.getUShort("stallp", c.stallPct);
  c.motorSpeed = prefs.getUShort("speed", MOTOR_SPEED_DEFAULT);
  c.manualTimeoutMin = prefs.getUShort("mto", c.manualTimeoutMin);
  c.feedMode = prefs.getUChar("feed", c.feedMode);
  c.fogDayOnMin = prefs.getUShort("fdon", c.fogDayOnMin);
  c.fogDayOffMin = prefs.getUShort("fdoff", c.fogDayOffMin);
  c.fogNightOnMin = prefs.getUShort("fnon", c.fogNightOnMin);
  c.fogNightOffMin = prefs.getUShort("fnoff", c.fogNightOffMin);
  c.fanRunOnS = prefs.getUShort("fanro", c.fanRunOnS);
  c.fogMaxTempC = prefs.getUShort("fmaxt", c.fogMaxTempC);
  c.flushOnMin = prefs.getUShort("flon", c.flushOnMin);
  c.flushOffMin = prefs.getUShort("floff", c.flushOffMin);
  c.motorStepsPerRev = STEPPER_HALF_STEPS_PER_REV;
  c.pinionTeeth = PINION_TEETH;
  c.ringTeeth = RING_TEETH;
  app::scheduler.setConfig(c);
  app::tz = prefs.getString("tz", TZ_DEFAULT);
}

// ---------------------------------------------------------------------------
// outputs
// ---------------------------------------------------------------------------
static void IRAM_ATTR onRevPulse() {
  uint32_t now = millis();
  if (now - lastRevMs >= REV_DEBOUNCE_MS) {  // reed contacts bounce
    lastRevMs = now;
    revCount = revCount + 1;
  }
}

static void allOutputsOff() {
  digitalWrite(PIN_PUMP, LOW);
  digitalWrite(PIN_FOG, LOW);
  digitalWrite(PIN_FAN, LOW);
  motor::command(motor::position(), true, app::scheduler.config().motorSpeed);
}

static void controlStep() {
  sched::Inputs in;
  in.nowS = app::nowS();
  struct tm t;
  if (app::localTime(t)) {
    in.minuteOfDay = t.tm_hour * 60 + t.tm_min;
    in.dayOfYear = t.tm_yday;
  }
  bool closed = digitalRead(PIN_FLOAT) == LOW;
  in.waterLowRaw = WATER_OK_WHEN_CLOSED ? !closed : closed;
  in.revCount = revCount;
  in.motorPos = motor::position();
  in.tempValid = app::tele.tempValid;
  in.tempC = app::tele.tempC;
  app::tele.revPulses = in.revCount;

  sched::Outputs o = app::scheduler.update(in);
  if (otaActive) {
    o.pump = o.fog = o.fan = false;
    o.motorHalt = true;
  }
  if (o.pump != lastPump) Serial.printf("pump %s\n", o.pump ? "on" : "off");
  if (o.fog != lastFog) Serial.printf("fogger %s\n", o.fog ? "on" : "off");
  if (o.fan != lastFan) Serial.printf("fan %s\n", o.fan ? "on" : "off");
  lastPump = o.pump;
  lastFog = o.fog;
  lastFan = o.fan;

  digitalWrite(PIN_PUMP, o.pump ? HIGH : LOW);
  digitalWrite(PIN_FOG, o.fog ? HIGH : LOW);
  digitalWrite(PIN_FAN, o.fan ? HIGH : LOW);
  motor::command(o.motorTarget, o.motorHalt, app::scheduler.config().motorSpeed);
  app::tele.motorEnergised = motor::energised();
}

static void updateLed() {
  const sched::Status &s = app::scheduler.status();
  uint32_t ms = millis();
  bool on;
  if (s.faultStall || s.waterLow)
    on = (ms / 125) % 2;  // fast blink: needs attention
  else if (WiFi.status() != WL_CONNECTED)
    on = (ms / 500) % 2;  // slow blink: no Wi-Fi (schedule still runs)
  else if (s.pumpOn || s.fogOn)
    on = true;
  else
    on = ms % 3000 < 60;  // heartbeat
  digitalWrite(PIN_LED, on ? HIGH : LOW);
}

// ---------------------------------------------------------------------------
// sensors
// ---------------------------------------------------------------------------
static void pollTemp() {
  uint32_t ms = millis();
  if (tempPending && ms - lastTempReq >= TEMP_CONVERT_MS) {
    tempPending = false;
    float c = ds.getTempCByIndex(0);
    app::tele.tempValid = c != DEVICE_DISCONNECTED_C && c > -55.0f && c < 125.0f;
    if (app::tele.tempValid) app::tele.tempC = c;
  }
  if (!tempPending && ms - lastTempReq >= TEMP_INTERVAL_MS) {
    lastTempReq = ms;
    if (ds.getDeviceCount() == 0) {  // optional sensor: keep looking for it
      ds.begin();
      ds.setWaitForConversion(false);
      if (ds.getDeviceCount() == 0) {
        app::tele.tempValid = false;
        return;
      }
    }
    ds.requestTemperatures();
    tempPending = true;
  }
}

// ---------------------------------------------------------------------------
// network
// ---------------------------------------------------------------------------
static void startWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.setAutoReconnect(true);

  // Non-blocking portal: watering keeps running while nobody configures Wi-Fi.
  wm.setConfigPortalBlocking(false);
  wm.setConnectTimeout(15);
  // No saved network: keep the portal up.  Saved but unreachable: close it
  // after a while and keep retrying the saved network.
  wm.setConfigPortalTimeout(wm.getWiFiIsSaved() ? PORTAL_TIMEOUT_S : 0);
  if (wm.autoConnect(HOSTNAME "-setup"))
    Serial.println("wifi connected");
  else
    Serial.println("wifi setup portal: " HOSTNAME "-setup");
}

static void startServices() {
  if (MDNS.begin(HOSTNAME)) MDNS.addService("http", "tcp", HTTP_PORT);

  ArduinoOTA.setHostname(HOSTNAME);
  if (strlen(OTA_PASSWORD)) ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() {
    otaActive = true;
    allOutputsOff();
  });
  ArduinoOTA.onProgress([](unsigned int, unsigned int) { esp_task_wdt_reset(); });
  ArduinoOTA.onError([](ota_error_t) { otaActive = false; });
  ArduinoOTA.begin();

  web::begin();
  servicesUp = true;
  Serial.printf("ready: http://%s/  (%s.local)\n", WiFi.localIP().toString().c_str(), HOSTNAME);
}

static void wifiLoop() {
  wm.process();
  bool up = WiFi.status() == WL_CONNECTED;
  bool portal = wm.getConfigPortalActive();
  if (up && !portal && !servicesUp) startServices();
  if (!up && !portal && wm.getWiFiIsSaved() && millis() - lastWifiTry >= WIFI_RETRY_S * 1000UL) {
    lastWifiTry = millis();
    WiFi.begin();
  }
}

// ---------------------------------------------------------------------------
// setup / loop
// ---------------------------------------------------------------------------
void setup() {
  // fail-safe: everything off before anything else
  const uint8_t switched[] = {PIN_PUMP, PIN_FOG, PIN_FAN};
  for (uint8_t p : switched) {
    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
  }
  const uint8_t coils[] = {PIN_STEP_IN1, PIN_STEP_IN2, PIN_STEP_IN3, PIN_STEP_IN4};
  for (uint8_t p : coils) {
    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
  }
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, HIGH);

  pinMode(PIN_FLOAT, INPUT_PULLUP);
  pinMode(PIN_REV, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_REV), onRevPulse, FALLING);

  Serial.begin(115200);
  Serial.printf("\ngrow tower fw %s\n", FW_VERSION);
  loadConfig();
  motor::begin();

  ds.begin();
  ds.setWaitForConversion(false);

  startWifi();
  configTzTime(app::tz.c_str(), NTP_SERVER_1, NTP_SERVER_2);

  esp_task_wdt_init(WDT_TIMEOUT_S, true);  // panic + reboot if loop() hangs
  esp_task_wdt_add(NULL);
}

void loop() {
  esp_task_wdt_reset();
  wifiLoop();
  if (servicesUp) {
    ArduinoOTA.handle();
    web::loop();
  }
  pollTemp();
  if (millis() - lastControl >= 100) {
    lastControl = millis();
    controlStep();
  }
  updateLed();
  delay(2);
}
