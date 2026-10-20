#include "ha.h"

#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiManager.h>

#include "config.h"

static WiFiManager wm;
static WiFiClient net;
static PubSubClient mqtt(net);
static Preferences prefs;
static char host[64], user[32], pass[64], portStr[6];
static char devId[24];
static WiFiManagerParameter *pHost, *pPort, *pUser, *pPass;
static uint32_t retryAt = 0;
static bool otaStarted = false;

static String topic(const char *sub) { return String(MQTT_BASE) + "/" + sub; }

static void copyParam(char *dst, size_t n, WiFiManagerParameter *p, const char *key) {
  strlcpy(dst, p->getValue(), n);
  prefs.putString(key, dst);
}

static void saveParams() {
  copyParam(host, sizeof(host), pHost, "host");
  copyParam(portStr, sizeof(portStr), pPort, "port");
  copyParam(user, sizeof(user), pUser, "user");
  copyParam(pass, sizeof(pass), pPass, "pass");
  mqtt.disconnect();
  retryAt = 0;
}

static void onMessage(char *t, byte *payload, unsigned int len) {
  size_t bl = strlen(MQTT_BASE);
  if (strncmp(t, MQTT_BASE, bl) != 0 || t[bl] != '/') return;
  char buf[512];
  size_t n = len < sizeof(buf) - 1 ? len : sizeof(buf) - 1;
  memcpy(buf, payload, n);
  buf[n] = 0;
  appOnMqtt(t + bl + 1, buf);
}

const char *haDeviceId() { return devId; }

void haBegin(bool forcePortal) {
  uint64_t mac = ESP.getEfuseMac();
  snprintf(devId, sizeof(devId), "magicband_%06x", (unsigned)((mac >> 24) & 0xFFFFFF));
  prefs.begin("mbnet", false);
  strlcpy(host, prefs.getString("host", "").c_str(), sizeof(host));
  strlcpy(portStr, prefs.getString("port", "1883").c_str(), sizeof(portStr));
  strlcpy(user, prefs.getString("user", "").c_str(), sizeof(user));
  strlcpy(pass, prefs.getString("pass", "").c_str(), sizeof(pass));

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  pHost = new WiFiManagerParameter("mqtt_host", "MQTT broker host", host, sizeof(host) - 1);
  pPort = new WiFiManagerParameter("mqtt_port", "MQTT port", portStr, sizeof(portStr) - 1);
  pUser = new WiFiManagerParameter("mqtt_user", "MQTT user", user, sizeof(user) - 1);
  pPass = new WiFiManagerParameter("mqtt_pass", "MQTT password", pass, sizeof(pass) - 1);
  wm.addParameter(pHost);
  wm.addParameter(pPort);
  wm.addParameter(pUser);
  wm.addParameter(pPass);
  wm.setSaveParamsCallback(saveParams);
  wm.setConfigPortalBlocking(false);  // the door must keep working while the portal is open
  wm.setConfigPortalTimeout(PORTAL_TIMEOUT_S);
  String ap = String(devId) + "-setup";
  if (forcePortal)
    wm.startConfigPortal(ap.c_str());
  else
    wm.autoConnect(ap.c_str());

  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  mqtt.setBufferSize(2048);
  mqtt.setCallback(onMessage);
}

bool haConnected() { return mqtt.connected(); }

void haPublish(const char *sub, const char *payload, bool retain) {
  if (mqtt.connected()) mqtt.publish(topic(sub).c_str(), payload, retain);
}

void haPublishJson(const char *sub, const JsonDocument &doc, bool retain) {
  if (!mqtt.connected()) return;
  String s;
  serializeJson(doc, s);
  mqtt.publish(topic(sub).c_str(), s.c_str(), retain);
}

// ---- discovery ---------------------------------------------------------------------------
static void disc(const char *component, const char *obj, const char *name, JsonDocument &d) {
  String uid = String(devId) + "_" + obj;
  d["name"] = name;
  d["unique_id"] = uid;
  d["availability_topic"] = topic("status");
  JsonObject dev = d["device"].to<JsonObject>();
  dev["identifiers"].add(String(devId));
  dev["name"] = "MagicBand door";
  dev["model"] = HA_MODEL;
  dev["manufacturer"] = "DIY";
  dev["sw_version"] = FW_VERSION;
  String t = String(HA_DISCOVERY_PREFIX) + "/" + component + "/" + devId + "/" + obj + "/config";
  String s;
  serializeJson(d, s);
  mqtt.publish(t.c_str(), s.c_str(), true);
}

static void button(const char *obj, const char *name, const char *cmd, const char *icon) {
  JsonDocument d;
  d["command_topic"] = topic("cmd");
  d["payload_press"] = String("{\"cmd\":\"") + cmd + "\"}";
  d["icon"] = icon;
  d["entity_category"] = "config";
  disc("button", obj, name, d);
}

static void sensor(const char *obj, const char *name, const char *stat, const char *tpl, const char *icon) {
  JsonDocument d;
  d["state_topic"] = topic(stat);
  if (tpl) d["value_template"] = tpl;
  if (icon) d["icon"] = icon;
  disc("sensor", obj, name, d);
}

static void binarySensor(const char *obj, const char *name, const char *cls, bool diagnostic) {
  JsonDocument d;
  d["state_topic"] = topic(obj);
  d["device_class"] = cls;
  if (diagnostic) d["entity_category"] = "diagnostic";
  disc("binary_sensor", obj, name, d);
}

static void number(const char *obj, const char *name, int mn, int mx, const char *unit, const char *icon) {
  JsonDocument d;
  d["command_topic"] = topic((String(obj) + "/set").c_str());
  d["state_topic"] = topic(obj);
  d["min"] = mn;
  d["max"] = mx;
  d["mode"] = "slider";
  if (unit) d["unit_of_measurement"] = unit;
  d["icon"] = icon;
  d["entity_category"] = "config";
  disc("number", obj, name, d);
}

void haPublishDiscovery() {
  if (!mqtt.connected()) return;
  {
    JsonDocument d;
    d["command_topic"] = topic("lock/set");
    d["state_topic"] = topic("lock/state");
    disc("lock", "door", "Door", d);
  }
  sensor("last_user", "Last scan user", "scan", "{{ value_json.user }}", "mdi:account");
  sensor("last_uid", "Last scan band", "scan", "{{ value_json.uid }}", "mdi:watch");
  {
    JsonDocument d;
    d["state_topic"] = topic("scan");
    d["value_template"] = "{{ value_json.result }}";
    d["json_attributes_topic"] = topic("scan");
    d["icon"] = "mdi:door-closed-lock";
    disc("sensor", "last_result", "Last scan result", d);
  }
  sensor("enroll", "Enrollment", "enroll", nullptr, "mdi:account-plus");
  {
    JsonDocument d;
    d["state_topic"] = topic("link_errors");
    d["state_class"] = "total_increasing";
    d["entity_category"] = "diagnostic";
    d["icon"] = "mdi:shield-alert";
    disc("sensor", "link_errors", "Link rejected frames", d);
  }
  binarySensor("door", "Door", "door", false);
  binarySensor("tamper", "Reader tamper", "tamper", false);
  binarySensor("reader", "Reader link", "connectivity", true);
  // ON = users need a finger but the reader has no R503 (reader_nofp): they are denied
  binarySensor("fp_problem", "Fingerprint configuration problem", "problem", false);
  {
    JsonDocument d;
    d["state_topic"] = topic("access");
    JsonArray ev = d["event_types"].to<JsonArray>();
    for (const char *e : {"granted", "denied", "need_finger", "locked_out"}) ev.add(e);
    d["icon"] = "mdi:card-account-details";
    disc("event", "access", "Access", d);
  }
  {
    JsonDocument d;
    d["command_topic"] = topic("new_name/set");
    d["state_topic"] = topic("new_name");
    d["max"] = 23;
    d["entity_category"] = "config";
    d["icon"] = "mdi:form-textbox";
    disc("text", "new_name", "New user name", d);
  }
  {
    JsonDocument d;
    d["command_topic"] = topic("user/set");
    d["state_topic"] = topic("user");
    JsonArray opts = d["options"].to<JsonArray>();
    appUserOptions(opts);
    if (opts.size() == 0) opts.add("-");
    d["entity_category"] = "config";
    d["icon"] = "mdi:account-search";
    disc("select", "user", "Selected user", d);
  }
  {
    JsonDocument d;
    d["command_topic"] = topic("policy/set");
    d["state_topic"] = topic("policy");
    JsonArray opts = d["options"].to<JsonArray>();
    for (const char *p : {"band_only", "band_and_finger", "finger_only"}) opts.add(p);
    d["entity_category"] = "config";
    d["icon"] = "mdi:shield-account";
    disc("select", "policy", "Selected user policy", d);
  }
  {
    JsonDocument d;
    d["command_topic"] = topic("enabled/set");
    d["state_topic"] = topic("enabled");
    d["entity_category"] = "config";
    d["icon"] = "mdi:account-check";
    disc("switch", "enabled", "Selected user enabled", d);
  }
  button("enroll_band", "Enroll next band (new user)", "enroll_band", "mdi:watch-import");
  button("add_band", "Add band to selected user", "add_band", "mdi:watch-variant");
  button("enroll_finger", "Enroll finger for selected user", "enroll_finger", "mdi:fingerprint");
  button("delete_user", "Delete selected user", "delete_user", "mdi:account-remove");
  button("cancel_enroll", "Cancel enrollment", "cancel", "mdi:cancel");
  number("brightness", "Reader brightness", 0, 255, nullptr, "mdi:brightness-6");
  number("volume", "Reader volume", 0, 100, "%", "mdi:volume-high");
  number("unlock_time", "Unlock time", 1, 30, "s", "mdi:timer-lock-open");
}

// ---- loop ----------------------------------------------------------------------------------
void haLoop() {
  wm.process();
  if (WiFi.status() != WL_CONNECTED) return;
  if (!otaStarted) {
    otaStarted = true;
    MDNS.begin(HOSTNAME);
    ArduinoOTA.setHostname(HOSTNAME);
    if (strlen(OTA_PASSWORD)) ArduinoOTA.setPassword(OTA_PASSWORD);
    ArduinoOTA.begin();
  }
  ArduinoOTA.handle();
  if (!mqtt.connected() && host[0] && (int32_t)(millis() - retryAt) >= 0) {
    retryAt = millis() + MQTT_RETRY_MS;
    mqtt.setServer(host, (uint16_t)atoi(portStr));
    String will = topic("status");
    if (mqtt.connect(devId, user[0] ? user : nullptr, user[0] ? pass : nullptr, will.c_str(), 1, true, "offline")) {
      mqtt.publish(will.c_str(), "online", true);
      mqtt.subscribe(topic("+/set").c_str());
      mqtt.subscribe(topic("cmd").c_str());
      haPublishDiscovery();
      appOnMqttConnected();
      log_i("MQTT connected to %s", host);
    } else {
      log_w("MQTT connect failed (%d)", mqtt.state());
    }
  }
  mqtt.loop();
}
