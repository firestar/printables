// Round smart speaker - ESP32 firmware
//
// Network voice endpoint for a custom hub: streams mic audio to the hub,
// plays audio the hub sends, and drives the LED halo ring.  Protocol:
// see firmware/PROTOCOL.md.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <WebSocketsServer.h>
#include <WiFi.h>
#include <WiFiManager.h>

#include "audio.h"
#include "config.h"
#include "leds.h"

static Preferences prefs;
static WebSocketsServer ws(WS_PORT);
static WiFiManager wm;

// persisted settings
static String devName;   // friendly name, shown to the hub
static String token;     // shared secret; empty = no auth
static String hostName;  // roundspk-xxxx, used for mDNS / OTA

// session state (one hub connection at a time)
static int16_t client = -1;
static bool authed = false;
static uint32_t connectedAt = 0;
static bool playEndPending = false;
static bool duckMic = false;  // drop mic frames while the speaker plays
static uint32_t spkOverflowBytes = 0;
static uint32_t lastStatus = 0, lastBufReport = 0;

// mic frame assembly: [FRAME_MIC][PCM16LE ...]
static uint8_t micFrame[1 + MIC_FRAME_SAMPLES * 2 * 2];
static size_t micFill = 0;

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
static void sendJson(JsonDocument &doc) {
  if (client < 0) return;
  String s;
  serializeJson(doc, s);
  ws.sendTXT((uint8_t)client, s);
}

static void sendError(const char *msg) {
  JsonDocument d;
  d["type"] = "error";
  d["msg"] = msg;
  sendJson(d);
}

static void fillState(JsonDocument &d) {
  d["name"] = devName;
  d["id"] = hostName;
  d["fw"] = FW_VERSION;
  d["volume"] = audio::volume();
  JsonObject mic = d["mic"].to<JsonObject>();
  mic["enabled"] = audio::micEnabled();
  mic["rate"] = MIC_SAMPLE_RATE;
  mic["bits"] = 16;
  mic["channels"] = audio::micChannels();
  mic["gain_db"] = audio::micGainDb();
  mic["duck"] = duckMic;
  JsonObject spk = d["spk"].to<JsonObject>();
  spk["rate"] = audio::speakerRate();
  spk["bits"] = 16;
  spk["channels"] = 1;
  spk["buffer"] = SPK_RING_BYTES;
  spk["queued"] = audio::speakerQueued();
  JsonObject led = d["led"].to<JsonObject>();
  led["mode"] = leds::modeName(leds::mode());
  char hex[8];
  snprintf(hex, sizeof(hex), "#%06lX", (unsigned long)leds::color());
  led["color"] = hex;
  led["brightness"] = leds::brightness();
  led["max"] = leds::maxBrightness();
  led["count"] = NUM_LEDS;
}

static void sendHello() {
  JsonDocument d;
  d["type"] = "hello";
  d["auth_required"] = token.length() > 0;
  fillState(d);
  sendJson(d);
}

static void sendState(const char *type) {
  JsonDocument d;
  d["type"] = type;
  fillState(d);
  d["rssi"] = WiFi.RSSI();
  d["uptime_s"] = millis() / 1000;
  d["heap"] = ESP.getFreeHeap();
  d["spk_overflow"] = spkOverflowBytes;
  sendJson(d);
}

static bool parseColor(JsonVariantConst v, uint8_t &r, uint8_t &g, uint8_t &b) {
  if (v.is<JsonArrayConst>()) {
    JsonArrayConst a = v.as<JsonArrayConst>();
    if (a.size() != 3) return false;
    r = a[0];
    g = a[1];
    b = a[2];
    return true;
  }
  if (v.is<const char *>()) {
    const char *s = v.as<const char *>();
    if (*s == '#') s++;
    if (strlen(s) != 6) return false;
    uint32_t c = strtoul(s, nullptr, 16);
    r = c >> 16;
    g = c >> 8;
    b = c;
    return true;
  }
  return false;
}

static void endSession() {
  audio::setMicEnabled(false);
  audio::flushSpeaker();
  playEndPending = false;
  micFill = 0;
  leds::setMode(leds::IDLE);
}

// ---------------------------------------------------------------------------
// commands from the hub
// ---------------------------------------------------------------------------
static void handleCommand(JsonDocument &cmd) {
  const char *type = cmd["type"] | "";

  if (strcmp(type, "hello") == 0) {
    if (token.length() && token != (cmd["token"] | "")) {
      sendError("bad token");
      ws.disconnect((uint8_t)client);
      return;
    }
    authed = true;
    sendState("ready");
    return;
  }
  if (!authed) {
    sendError("not authenticated");
    return;
  }

  if (strcmp(type, "ping") == 0) {
    JsonDocument d;
    d["type"] = "pong";
    if (!cmd["id"].isNull()) d["id"] = cmd["id"];
    d["t"] = millis();
    sendJson(d);

  } else if (strcmp(type, "get_state") == 0) {
    sendState("state");

  } else if (strcmp(type, "mic") == 0) {
    if (!cmd["channels"].isNull()) audio::setMicChannels(cmd["channels"].as<uint8_t>());
    if (!cmd["gain_db"].isNull()) audio::setMicGainDb(cmd["gain_db"].as<float>());
    if (!cmd["duck"].isNull()) duckMic = cmd["duck"].as<bool>();
    if (!cmd["enable"].isNull()) {
      micFill = 0;
      audio::setMicEnabled(cmd["enable"].as<bool>());
    }
    sendState("state");

  } else if (strcmp(type, "play_start") == 0) {
    uint32_t rate = cmd["rate"] | (uint32_t)audio::speakerRate();
    if (rate != audio::speakerRate()) {
      audio::flushSpeaker();
      if (!audio::setSpeakerRate(rate)) {
        sendError("unsupported rate (8000-48000)");
        return;
      }
    }
    playEndPending = false;
    JsonDocument d;
    d["type"] = "play_ready";
    d["rate"] = audio::speakerRate();
    d["free"] = audio::speakerFree();
    sendJson(d);

  } else if (strcmp(type, "play_end") == 0) {
    playEndPending = true;

  } else if (strcmp(type, "stop") == 0) {
    audio::flushSpeaker();
    playEndPending = false;
    JsonDocument d;
    d["type"] = "play_done";
    d["stopped"] = true;
    sendJson(d);

  } else if (strcmp(type, "volume") == 0) {
    int v = cmd["value"] | (int)audio::volume();
    audio::setVolume((uint8_t)constrain(v, 0, 100));
    prefs.putUChar("volume", audio::volume());
    sendState("state");

  } else if (strcmp(type, "led") == 0) {
    if (!cmd["mode"].isNull()) {
      leds::Mode m;
      if (!leds::modeFromString(cmd["mode"] | "", m)) {
        sendError("unknown led mode");
        return;
      }
      leds::setMode(m);
    }
    if (!cmd["color"].isNull()) {
      uint8_t r, g, b;
      if (!parseColor(cmd["color"], r, g, b)) {
        sendError("color must be [r,g,b] or \"#rrggbb\"");
        return;
      }
      leds::setColor(r, g, b);
    }
    if (!cmd["brightness"].isNull())
      leds::setBrightness((uint8_t)constrain(cmd["brightness"].as<int>(), 0, 255));
    sendState("state");

  } else if (strcmp(type, "led_max") == 0) {
    int v = cmd["value"] | (int)leds::maxBrightness();
    leds::setMaxBrightness((uint8_t)constrain(v, 0, 255));
    prefs.putUChar("led_max", leds::maxBrightness());
    sendState("state");

  } else if (strcmp(type, "config") == 0) {
    bool reboot = false;
    if (!cmd["name"].isNull()) {
      devName = cmd["name"].as<String>();
      prefs.putString("name", devName);
    }
    if (!cmd["token"].isNull()) {
      token = cmd["token"].as<String>();
      prefs.putString("token", token);
      reboot = true;  // OTA password follows the token
    }
    sendState("state");
    if (reboot) {
      delay(200);
      ESP.restart();
    }

  } else if (strcmp(type, "wifi_reset") == 0) {
    JsonDocument d;
    d["type"] = "rebooting";
    sendJson(d);
    delay(200);
    wm.resetSettings();
    ESP.restart();

  } else if (strcmp(type, "reboot") == 0) {
    JsonDocument d;
    d["type"] = "rebooting";
    sendJson(d);
    delay(200);
    ESP.restart();

  } else {
    sendError("unknown command");
  }
}

// ---------------------------------------------------------------------------
// WebSocket events
// ---------------------------------------------------------------------------
static void onWs(uint8_t num, WStype_t type, uint8_t *payload, size_t len) {
  switch (type) {
    case WStype_CONNECTED:
      if (client >= 0 && client != num) ws.disconnect((uint8_t)client);  // newest hub wins
      client = num;
      authed = token.length() == 0;
      connectedAt = millis();
      endSession();
      sendHello();
      break;

    case WStype_DISCONNECTED:
      if (num == client) {
        client = -1;
        authed = false;
        endSession();
      }
      break;

    case WStype_TEXT: {
      if (num != client) return;
      JsonDocument cmd;
      if (deserializeJson(cmd, payload, len)) {
        sendError("bad json");
        return;
      }
      handleCommand(cmd);
      break;
    }

    case WStype_BIN:
      if (num != client || !authed || len < 1) return;
      if (payload[0] == FRAME_SPK) {
        size_t n = len - 1;
        size_t ok = audio::pushSpeaker(payload + 1, n);
        if (ok < n) spkOverflowBytes += n - ok;
      }
      break;

    default:
      break;
  }
}

// ---------------------------------------------------------------------------
// periodic work
// ---------------------------------------------------------------------------
static void pumpMic() {
  const size_t frameBytes = MIC_FRAME_SAMPLES * 2 * audio::micChannels();
  if (!audio::micEnabled() || client < 0 || !authed) return;
  micFrame[0] = FRAME_MIC;
  for (;;) {
    size_t n = audio::readMic(micFrame + 1 + micFill, frameBytes - micFill);
    micFill += n;
    if (micFill < frameBytes) return;
    micFill = 0;
    if (duckMic && audio::speakerActive()) continue;  // drop while playing
    ws.sendBIN((uint8_t)client, micFrame, 1 + frameBytes);
  }
}

static void pumpReports() {
  if (client < 0 || !authed) return;
  uint32_t now = millis();
  if (now - lastStatus >= STATUS_INTERVAL_MS) {
    lastStatus = now;
    sendState("status");
  }
  bool playing = audio::speakerQueued() > 0 || playEndPending;
  if (playing && now - lastBufReport >= PLAY_BUFFER_INTERVAL_MS) {
    lastBufReport = now;
    JsonDocument d;
    d["type"] = "play_buffer";
    d["free"] = audio::speakerFree();
    d["queued"] = audio::speakerQueued();
    sendJson(d);
  }
  if (playEndPending && !audio::speakerActive()) {
    playEndPending = false;
    JsonDocument d;
    d["type"] = "play_done";
    d["stopped"] = false;
    sendJson(d);
  }
}

// ---------------------------------------------------------------------------
// setup
// ---------------------------------------------------------------------------
static void loadPrefs() {
  prefs.begin("roundspk", false);
  uint64_t mac = ESP.getEfuseMac();
  char hn[24];
  snprintf(hn, sizeof(hn), "roundspk-%02x%02x", (uint8_t)(mac >> 32), (uint8_t)(mac >> 40));
  hostName = hn;
  devName = prefs.getString("name", hostName);
  token = prefs.getString("token", "");
  audio::setVolume(prefs.getUChar("volume", VOLUME_DEFAULT));
  leds::setMaxBrightness(prefs.getUChar("led_max", LED_MAX_BRIGHTNESS_DEFAULT));
}

static void startWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(hostName.c_str());

  // static: WiFiManager keeps pointers to its parameters
  static WiFiManagerParameter pName("name", "Device name", devName.c_str(), 32);
  static WiFiManagerParameter pToken("token", "Hub token (optional)", token.c_str(), 64);
  wm.addParameter(&pName);
  wm.addParameter(&pToken);
  wm.setSaveParamsCallback([]() {
    devName = pName.getValue();
    token = pToken.getValue();
    prefs.putString("name", devName);
    prefs.putString("token", token);
  });
  wm.setAPCallback([](WiFiManager *) { leds::setMode(leds::SETUP); });
  wm.setConfigPortalTimeout(PORTAL_TIMEOUT_S);
  wm.setConnectTimeout(20);

  String ap = hostName + "-setup";
  if (!wm.autoConnect(ap.c_str())) {
    leds::setMode(leds::ERROR_BLINK);
    delay(2000);
    ESP.restart();
  }
  WiFi.setSleep(false);  // modem sleep adds latency/jitter to audio
}

static void startServices() {
  if (MDNS.begin(hostName.c_str())) {
    MDNS.addService(MDNS_SERVICE, "tcp", WS_PORT);
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "id", hostName.c_str());
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "name", devName.c_str());
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "fw", FW_VERSION);
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "auth", token.length() ? "1" : "0");
  }

  ArduinoOTA.setHostname(hostName.c_str());
  if (token.length()) ArduinoOTA.setPassword(token.c_str());
  ArduinoOTA.onStart([]() {
    audio::setMicEnabled(false);
    audio::flushSpeaker();
    leds::setColor(0, 255, 120);
    leds::setMode(leds::THINKING);
  });
  ArduinoOTA.onError([](ota_error_t) { leds::setMode(leds::ERROR_BLINK); });
  ArduinoOTA.begin();

  ws.begin();
  ws.onEvent(onWs);
  ws.enableHeartbeat(15000, 3000, 2);  // drop dead hubs
}

void setup() {
  Serial.begin(115200);
  leds::begin();  // boot animation while everything else starts
  loadPrefs();
  if (!audio::begin()) {
    Serial.println("audio init failed");
    leds::setMode(leds::ERROR_BLINK);
  }
  startWifi();
  startServices();
  leds::setMode(leds::IDLE);
  Serial.printf("ready: ws://%s:%d/  (%s.local)\n", WiFi.localIP().toString().c_str(), WS_PORT,
                hostName.c_str());
}

void loop() {
  ws.loop();
  ArduinoOTA.handle();

  if (client >= 0 && !authed && millis() - connectedAt > AUTH_TIMEOUT_MS) {
    sendError("auth timeout");
    ws.disconnect((uint8_t)client);
  }
  pumpMic();
  pumpReports();
  delay(1);
}
