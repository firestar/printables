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
#include <esp_wifi.h>
#include <improv.h>

#include "audio.h"
#include "config.h"
#include "leds.h"
#include "serial_core.h"

static Preferences prefs;
static WebSocketsServer ws(WS_PORT);
static WiFiManager wm;

// persisted settings
static lumen::Settings settings;  // name, hub token (secret; empty = no auth), LEDs
static String hostName;           // roundspk-xxxx, used for mDNS / OTA

// Wi-Fi setup portal fields. The token field always starts blank: the portal's
// access point is open, so it must never show the stored token.
static WiFiManagerParameter pName("name", "Device name", "", lumen::NAME_MAX_BYTES);
static WiFiManagerParameter pToken("token", "Hub token (leave blank to keep the current one)", "",
                                   lumen::TOKEN_MAX_BYTES, "type='password' autocomplete='off'");

// network bring-up, run from loop() so USB serial is served throughout
enum class NetState : uint8_t { CONNECTING, PORTAL, PROVISIONING, ONLINE };
static NetState netState = NetState::CONNECTING;
static uint32_t netStateAt = 0;
static wifi_config_t prevWifi;  // network to go back to if Improv credentials fail
static bool servicesStarted = false;

// USB serial link
static lumen::SerialDemux demux;
static bool serialSeen = false;
static uint32_t lastSerialMs = 0;
static bool scanActive = false;
static uint32_t scanStartedAt = 0;
static bool restartPending = false;
static uint32_t restartAt = 0;

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
// settings storage (NVS namespace "roundspk")
// ---------------------------------------------------------------------------
// Keys: name, token, led_count, led_max, plus volume. NVS has no multi-key
// transaction, so a failed write puts the old values back. Power loss during a
// save can still leave only some keys written; each one is valid on its own.
class NvsStore : public lumen::SettingsStore {
 public:
  bool save(const lumen::Settings &before, const lumen::Settings &after) override {
    if (write(after, before)) return true;
    write(before, after);
    return false;
  }

  bool erase() override {
    if (!prefs.clear()) return false;
    wm.resetSettings();  // also forgets the saved Wi-Fi network
    return true;
  }

 private:
  // Writes only the keys where `to` differs from `from`, to save flash wear.
  static bool write(const lumen::Settings &to, const lumen::Settings &from) {
    bool ok = true;
    if (to.name != from.name) ok &= prefs.putString("name", to.name.c_str()) == to.name.size();
    if (to.token != from.token) {
      if (to.token.empty()) {
        prefs.remove("token");
        ok &= !prefs.isKey("token");
      } else {
        ok &= prefs.putString("token", to.token.c_str()) == to.token.size();
      }
    }
    if (to.ledCount != from.ledCount) ok &= prefs.putUShort("led_count", to.ledCount) == sizeof(uint16_t);
    if (to.ledMaxBrightness != from.ledMaxBrightness) ok &= prefs.putUChar("led_max", to.ledMaxBrightness) == 1;
    return ok;
  }
};
static NvsStore store;

// Puts the current settings into effect on the running device. A changed token
// is the exception: the OTA password only picks it up at the next restart.
static void applySettings() {
  leds::setCount(settings.ledCount);
  leds::setMaxBrightness(settings.ledMaxBrightness);
  pName.setValue(settings.name.c_str(), lumen::NAME_MAX_BYTES);
  if (servicesStarted) MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "name", settings.name.c_str());
}

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
  d["name"] = settings.name;
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
  led["max_effective"] = leds::effectiveMaxBrightness();
  led["count"] = leds::count();
}

static void sendHello() {
  JsonDocument d;
  d["type"] = "hello";
  d["auth_required"] = !settings.token.empty();
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
    if (!settings.token.empty() && settings.token != (cmd["token"] | "")) {
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
    settings.ledMaxBrightness = leds::maxBrightness();
    prefs.putUChar("led_max", settings.ledMaxBrightness);
    sendState("state");

  } else if (strcmp(type, "config") == 0) {
    // Same limits as the serial settings protocol, and all or nothing.
    lumen::Settings next = settings;
    bool reboot = false;
    JsonVariantConst nameArg = cmd["name"];
    if (!nameArg.isNull()) {
      JsonString s = nameArg.as<JsonString>();
      if (!nameArg.is<JsonString>() || !lumen::isValidName(s.c_str(), s.size())) {
        sendError("name must be 1 to 32 bytes of printable UTF-8");
        return;
      }
      next.name.assign(s.c_str(), s.size());
    }
    JsonVariantConst tokenArg = cmd["token"];
    if (!tokenArg.isNull()) {
      JsonString s = tokenArg.as<JsonString>();
      if (!tokenArg.is<JsonString>() || !lumen::isValidToken(s.c_str(), s.size())) {
        sendError("token must be up to 64 bytes of printable UTF-8");
        return;
      }
      next.token.assign(s.c_str(), s.size());
      reboot = true;  // OTA password follows the token
    }
    if (!store.save(settings, next)) {
      sendError("storage write failed");
      return;
    }
    settings = next;
    applySettings();
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
      authed = settings.token.empty();
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
  settings = lumen::defaultSettings(hn);
  // Older firmware put no limit on these, so they're loaded as stored. Cutting a
  // long token short would silently lock the hub out.
  String storedName = prefs.getString("name", hostName);
  if (storedName.length()) settings.name = storedName.c_str();
  settings.token = prefs.getString("token", "").c_str();
  settings.ledCount = lumen::sanitizeLedCount(prefs.getUShort("led_count", LED_COUNT_DEFAULT));
  settings.ledMaxBrightness = prefs.getUChar("led_max", LED_MAX_BRIGHTNESS_DEFAULT);
  audio::setVolume(prefs.getUChar("volume", VOLUME_DEFAULT));
  leds::setMaxBrightness(settings.ledMaxBrightness);
}

static void startServices() {
  if (MDNS.begin(hostName.c_str())) {
    MDNS.addService(MDNS_SERVICE, "tcp", WS_PORT);
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "id", hostName.c_str());
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "name", settings.name.c_str());
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "fw", FW_VERSION);
    MDNS.addServiceTxt(MDNS_SERVICE, "tcp", "auth", settings.token.empty() ? "0" : "1");
  }

  ArduinoOTA.setHostname(hostName.c_str());
  if (!settings.token.empty()) ArduinoOTA.setPassword(settings.token.c_str());
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
  servicesStarted = true;
}

// ---------------------------------------------------------------------------
// network bring-up
// ---------------------------------------------------------------------------
// Nothing here may block for long, or the browser's Improv requests go unanswered:
// it gives up after about a second. So autoConnect(), which blocks on the saved
// network and then on the portal, isn't used. loop() drives this state machine
// instead, and WiFiManager runs in non-blocking mode.
static void setNetState(NetState s) {
  netState = s;
  netStateAt = millis();
}

static void enterPortal() {
  String ap = hostName + "-setup";
  wm.startConfigPortal(ap.c_str());
  setNetState(NetState::PORTAL);
}

static void startWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(hostName.c_str());

  // Its debug output would share this UART with the protocols, and its verbose
  // levels print portal fields and the Wi-Fi password, so it stays off entirely.
  wm.setDebugOutput(false);
  pName.setValue(settings.name.c_str(), lumen::NAME_MAX_BYTES);
  wm.addParameter(&pName);
  wm.addParameter(&pToken);
  wm.setSaveParamsCallback([]() {
    lumen::Settings next = settings;
    const char *name = pName.getValue();
    if (lumen::isValidName(name, strlen(name))) next.name = name;
    const char *newToken = pToken.getValue();
    if (*newToken && lumen::isValidToken(newToken, strlen(newToken))) next.token = newToken;
    pToken.setValue("", lumen::TOKEN_MAX_BYTES);  // don't serve it back in the form
    if (store.save(settings, next)) {
      settings = next;
      applySettings();
    }
  });
  wm.setAPCallback([](WiFiManager *) { leds::setMode(leds::SETUP); });
  wm.setConfigPortalBlocking(false);
  wm.setConfigPortalTimeout(PORTAL_TIMEOUT_S);
  wm.setConnectTimeout(20);

  if (wm.getWiFiIsSaved()) {
    WiFi.begin();
    setNetState(NetState::CONNECTING);
  } else {
    enterPortal();
  }
}

static void goOnline() {
  WiFi.setSleep(false);  // modem sleep adds latency/jitter to audio
  if (!servicesStarted) startServices();
  leds::setMode(leds::IDLE);
  setNetState(NetState::ONLINE);
  Serial.printf("ready: ws://%s:%d/  (%s.local)\n", WiFi.localIP().toString().c_str(), WS_PORT,
                hostName.c_str());
}

static void writePackets(const std::vector<lumen::Bytes> &packets) {
  for (const lumen::Bytes &p : packets) Serial.write(p.data(), p.size());
}

static void pumpNet() {
  const uint32_t elapsed = millis() - netStateAt;
  std::vector<lumen::Bytes> out;
  switch (netState) {
    case NetState::CONNECTING:
      if (WiFi.status() == WL_CONNECTED) {
        goOnline();
      } else if (elapsed > WIFI_CONNECT_TIMEOUT_MS) {
        enterPortal();
      }
      break;

    case NetState::PORTAL:
      if (wm.process() || WiFi.status() == WL_CONNECTED) {
        if (wm.getConfigPortalActive()) wm.stopConfigPortal();
        goOnline();
      } else if (!wm.getConfigPortalActive()) {
        // Timed out or exited. Reboot and try again as before, unless someone is
        // using the USB link: a reboot would cut off their session.
        if (serialSeen && millis() - lastSerialMs < SERIAL_SESSION_MS) {
          enterPortal();
        } else {
          leds::setMode(leds::ERROR_BLINK);
          delay(2000);
          ESP.restart();
        }
      }
      break;

    case NetState::PROVISIONING:
      // The short wait lets a previous connection report that it has gone.
      if (elapsed > 1000 && WiFi.status() == WL_CONNECTED) {
        memset(&prevWifi, 0, sizeof(prevWifi));
        lumen::improvProvisionedPackets(out);
        writePackets(out);
        goOnline();
      } else if (elapsed > WIFI_CONNECT_TIMEOUT_MS) {
        lumen::improvProvisionFailedPackets(out);
        writePackets(out);
        // Don't keep credentials that failed: restore what was saved before, or
        // nothing if this was the first attempt.
        WiFi.disconnect();
        esp_wifi_set_config(WIFI_IF_STA, &prevWifi);
        const bool hadNetwork = prevWifi.sta.ssid[0] != 0;
        memset(&prevWifi, 0, sizeof(prevWifi));
        if (hadNetwork) {
          WiFi.begin();
          setNetState(NetState::CONNECTING);
        } else {
          enterPortal();
        }
      }
      break;

    case NetState::ONLINE:
      break;
  }
}

// ---------------------------------------------------------------------------
// USB serial link: Improv Serial and the JSON settings protocol
// ---------------------------------------------------------------------------
class DeviceImprovHost : public lumen::ImprovHost {
 public:
  uint8_t improvState() override {
    if (netState == NetState::PROVISIONING) return improv::STATE_PROVISIONING;
    return WiFi.status() == WL_CONNECTED ? improv::STATE_PROVISIONED : improv::STATE_AUTHORIZED;
  }

  std::string deviceName() override { return settings.name; }

  bool startProvisioning(const std::string &ssid, const std::string &password) override {
    if (netState == NetState::PROVISIONING || restartPending) return false;
    Serial.println("improv: connecting");
    if (wm.getConfigPortalActive()) wm.stopConfigPortal();
    WiFi.mode(WIFI_STA);
    if (esp_wifi_get_config(WIFI_IF_STA, &prevWifi) != ESP_OK) memset(&prevWifi, 0, sizeof(prevWifi));
    WiFi.disconnect();
    WiFi.begin(ssid.c_str(), password.c_str());
    leds::setMode(leds::BOOT);
    setNetState(NetState::PROVISIONING);
    return true;
  }

  void startScan() override {
    if (scanActive) return;
    WiFi.scanNetworks(true);
    scanActive = true;
    scanStartedAt = millis();
  }
};
static DeviceImprovHost improvHost;

static void pumpScan() {
  if (!scanActive) return;
  const int16_t n = WiFi.scanComplete();
  if (n == WIFI_SCAN_RUNNING && millis() - scanStartedAt < WIFI_SCAN_TIMEOUT_MS) return;
  scanActive = false;
  std::vector<lumen::ScanEntry> entries;
  for (int16_t i = 0; i < n; i++) {
    lumen::ScanEntry e;
    e.ssid = WiFi.SSID(i).c_str();
    e.rssi = WiFi.RSSI(i);
    e.secured = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    entries.push_back(e);
  }
  WiFi.scanDelete();
  std::vector<lumen::Bytes> out;
  lumen::improvScanPackets(entries, out);  // an empty list if the scan failed
  writePackets(out);
}

static void scheduleRestart(uint32_t delayMs) {
  const uint32_t at = millis() + delayMs;
  if (!restartPending || (int32_t)(at - restartAt) < 0) restartAt = at;
  restartPending = true;
}

static void sendReply(const std::string &reply) {
  if (reply.empty()) return;
  const std::string framed = lumen::frameReply(reply);
  Serial.write(reinterpret_cast<const uint8_t *>(framed.data()), framed.size());
}

static void handleSerialLine(const char *line, size_t len) {
  lumen::LineResult r = lumen::handleLine(line, len, settings, hostName.c_str(), store);
  sendReply(r.reply);
  switch (r.action) {
    case lumen::LineAction::NONE:
      break;
    case lumen::LineAction::SETTINGS_CHANGED:
      applySettings();
      break;
    case lumen::LineAction::RESTART:
      scheduleRestart(100);
      break;
    case lumen::LineAction::ERASED:
      // Wi-Fi is gone, so restarting is the only way forward. Wait briefly in
      // case the browser follows up with its own restart command.
      applySettings();
      scheduleRestart(1000);
      break;
  }
}

static void pumpSerial() {
  while (Serial.available() > 0) {
    const uint32_t now = millis();
    serialSeen = true;
    lastSerialMs = now;
    const lumen::SerialDemux::Event ev = demux.feed((uint8_t)Serial.read(), now);
    switch (ev.type) {
      case lumen::SerialDemux::EV_NONE:
        break;
      case lumen::SerialDemux::EV_LINE:
        handleSerialLine(reinterpret_cast<const char *>(ev.data), ev.len);
        break;
      case lumen::SerialDemux::EV_LINE_TOO_LONG:
        sendReply(lumen::oversizedLineReply(reinterpret_cast<const char *>(ev.data), ev.len));
        break;
      case lumen::SerialDemux::EV_IMPROV_PACKET:
      case lumen::SerialDemux::EV_IMPROV_BAD_CHECKSUM: {
        std::vector<lumen::Bytes> out;
        lumen::handleImprovEvent(ev, improvHost, out);
        writePackets(out);
        break;
      }
    }
  }
}

void setup() {
  // Room for a full request while loop() is briefly busy (starting the portal
  // takes about a second). Has to be set before begin().
  Serial.setRxBufferSize(2048);
  Serial.begin(115200);
  loadPrefs();
  leds::begin(settings.ledCount);  // boot animation while everything else starts
  if (!audio::begin()) {
    Serial.println("audio init failed");
    leds::setMode(leds::ERROR_BLINK);
  }
  startWifi();
}

void loop() {
  pumpSerial();
  pumpNet();
  pumpScan();

  if (restartPending && (int32_t)(millis() - restartAt) >= 0) {
    Serial.flush();
    ESP.restart();
  }

  if (servicesStarted) {
    ws.loop();
    ArduinoOTA.handle();

    if (client >= 0 && !authed && millis() - connectedAt > AUTH_TIMEOUT_MS) {
      sendError("auth timeout");
      ws.disconnect((uint8_t)client);
    }
    pumpMic();
    pumpReports();
  }
  delay(1);
}
