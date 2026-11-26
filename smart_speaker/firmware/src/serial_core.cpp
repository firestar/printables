#include "serial_core.h"

#include <ArduinoJson.h>
#include <improv.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace lumen {

// ---------------------------------------------------------------------------
// settings model
// ---------------------------------------------------------------------------
Settings defaultSettings(const std::string &defaultName) {
  Settings s;
  s.name = defaultName;
  s.ledCount = LED_COUNT_DEFAULT;
  s.ledMaxBrightness = LED_MAX_BRIGHTNESS_DEFAULT;
  return s;
}

// Valid UTF-8 (no overlong forms or surrogates) without C0 controls or DEL.
static bool isCleanUtf8(const char *str, size_t len) {
  const uint8_t *s = reinterpret_cast<const uint8_t *>(str);
  size_t i = 0;
  while (i < len) {
    const uint8_t c = s[i];
    if (c < 0x20 || c == 0x7F) return false;
    if (c < 0x80) {
      i++;
      continue;
    }
    size_t extra;
    uint8_t lo = 0x80, hi = 0xBF;  // allowed range of the first continuation byte
    if (c >= 0xC2 && c <= 0xDF) {
      extra = 1;
    } else if (c >= 0xE0 && c <= 0xEF) {
      extra = 2;
      if (c == 0xE0) lo = 0xA0;
      if (c == 0xED) hi = 0x9F;
    } else if (c >= 0xF0 && c <= 0xF4) {
      extra = 3;
      if (c == 0xF0) lo = 0x90;
      if (c == 0xF4) hi = 0x8F;
    } else {
      return false;
    }
    if (len - i <= extra) return false;
    if (s[i + 1] < lo || s[i + 1] > hi) return false;
    for (size_t k = 2; k <= extra; k++) {
      if (s[i + k] < 0x80 || s[i + k] > 0xBF) return false;
    }
    i += extra + 1;
  }
  return true;
}

bool isValidName(const char *s, size_t len) {
  return len >= 1 && len <= NAME_MAX_BYTES && isCleanUtf8(s, len);
}

bool isValidToken(const char *s, size_t len) {
  return len <= TOKEN_MAX_BYTES && isCleanUtf8(s, len);
}

uint16_t sanitizeLedCount(uint32_t count) {
  if (count < LED_COUNT_MIN || count > LED_COUNT_MAX) return LED_COUNT_DEFAULT;
  return static_cast<uint16_t>(count);
}

uint8_t powerCappedBrightness(uint16_t count, uint8_t requestedMax) {
  if (count == 0) return requestedMax;
  const uint32_t cap =
      (uint32_t)LED_POWER_BUDGET_MA * 255u / ((uint32_t)count * LED_FULL_WHITE_MA);
  return cap < requestedMax ? static_cast<uint8_t>(cap) : requestedMax;
}

// ---------------------------------------------------------------------------
// settings protocol
// ---------------------------------------------------------------------------

// Lets ArduinoJson read from a buffer and shows what it left behind, because
// deserializeJson() on its own accepts trailing garbage after the object.
struct SpanReader {
  const char *p;
  const char *end;
  int read() { return p < end ? static_cast<uint8_t>(*p++) : -1; }
  size_t readBytes(char *out, size_t n) {
    size_t i = 0;
    while (i < n && p < end) out[i++] = *p++;
    return i;
  }
  bool onlySpaceLeft() const {
    for (const char *q = p; q < end; q++) {
      if (*q != ' ' && *q != '\t' && *q != '\r') return false;
    }
    return true;
  }
};

struct ReplyId {
  bool valid;
  long long value;
};

static void putId(JsonDocument &d, const ReplyId &id) {
  if (id.valid) {
    d["id"] = id.value;
  } else {
    d["id"] = nullptr;
  }
}

static std::string serialize(const JsonDocument &d) {
  std::string out;
  serializeJson(d, out);
  return out;
}

static std::string errorReply(const ReplyId &id, const std::string &msg) {
  JsonDocument d;
  putId(d, id);
  d["ok"] = false;
  d["error"] = msg;
  return serialize(d);
}

// Recovers the id from a line that can't be parsed, so the browser gets a useful
// error instead of a timeout. The text "id": can't occur inside a JSON string
// because the quotes would have to be escaped.
static ReplyId scanForId(const char *line, size_t len) {
  static const char KEY[] = "\"id\":";
  const size_t keyLen = sizeof(KEY) - 1;
  for (size_t i = 0; i + keyLen < len; i++) {
    if (memcmp(line + i, KEY, keyLen) != 0) continue;
    size_t k = i + keyLen;
    const size_t start = k;
    long long value = 0;
    while (k < len && line[k] >= '0' && line[k] <= '9' && k - start < 15) {
      value = value * 10 + (line[k] - '0');
      k++;
    }
    if (k > start && (k == len || line[k] == ',' || line[k] == '}' || line[k] == ' ')) {
      ReplyId id = {true, value};
      return id;
    }
    break;
  }
  ReplyId none = {false, 0};
  return none;
}

// Builds `next` from the request. Returns an error message, or empty on success.
// Messages name the key and never contain a submitted value.
static std::string mergeSettings(JsonObjectConst request, Settings &next) {
  for (JsonPairConst kv : request) {
    const std::string key = kv.key().c_str();
    JsonVariantConst v = kv.value();
    if (key == "name") {
      if (!v.is<JsonString>()) return "name must be a string";
      JsonString s = v.as<JsonString>();
      if (!isValidName(s.c_str(), s.size())) return "name must be 1 to 32 bytes of printable UTF-8";
      next.name.assign(s.c_str(), s.size());
    } else if (key == "token") {
      if (!v.is<JsonString>()) return "token must be a string";
      JsonString s = v.as<JsonString>();
      if (!isValidToken(s.c_str(), s.size())) return "token must be up to 64 bytes of printable UTF-8";
      next.token.assign(s.c_str(), s.size());
    } else if (key == "led_count") {
      if (!v.is<long long>()) return "led_count must be an integer";
      const long long n = v.as<long long>();
      if (n < LED_COUNT_MIN || n > LED_COUNT_MAX) return "led_count out of range";
      next.ledCount = static_cast<uint16_t>(n);
    } else if (key == "led_max_brightness") {
      if (!v.is<long long>()) return "led_max_brightness must be an integer";
      const long long n = v.as<long long>();
      if (n < 0 || n > 255) return "led_max_brightness out of range";
      next.ledMaxBrightness = static_cast<uint8_t>(n);
    } else {
      return "unknown setting: " + key;
    }
  }
  return std::string();
}

LineResult handleLine(const char *line, size_t len, Settings &settings,
                      const std::string &defaultName, SettingsStore &store) {
  LineResult r;
  if (len == 0 || line[0] != '{') return r;

  JsonDocument doc;
  SpanReader reader = {line, line + len};
  DeserializationError parseError =
      deserializeJson(doc, reader, DeserializationOption::NestingLimit(4));
  if (parseError || !reader.onlySpaceLeft() || !doc.is<JsonObjectConst>()) {
    r.reply = errorReply(scanForId(line, len), "bad json");
    return r;
  }
  JsonObjectConst req = doc.as<JsonObjectConst>();

  JsonVariantConst version = req["lumen"];
  if (version.isNull()) return r;  // some other JSON line, not addressed to us

  ReplyId id = {false, 0};
  if (req["id"].is<long long>()) {
    id.valid = true;
    id.value = req["id"].as<long long>();
  }
  if (!version.is<long long>() || version.as<long long>() != 1) {
    r.reply = errorReply(id, "unsupported protocol version");
    return r;
  }
  if (!id.valid) {
    r.reply = errorReply(id, "id must be an integer");
    return r;
  }
  if (!req["cmd"].is<const char *>()) {
    r.reply = errorReply(id, "unknown command");
    return r;
  }
  const std::string cmd = req["cmd"].as<const char *>();

  JsonDocument out;
  putId(out, id);
  out["ok"] = true;

  if (cmd == "info") {
    out["project"] = PROJECT_ID;
    out["fw"] = FW_VERSION;
    out["schema"] = SCHEMA_VERSION;

  } else if (cmd == "get") {
    JsonObject s = out["settings"].to<JsonObject>();
    s["name"] = settings.name;
    s["led_count"] = settings.ledCount;
    s["led_max_brightness"] = settings.ledMaxBrightness;
    s["token_set"] = !settings.token.empty();

  } else if (cmd == "set") {
    if (!req["settings"].is<JsonObjectConst>()) {
      r.reply = errorReply(id, "settings must be an object");
      return r;
    }
    Settings next = settings;
    const std::string error = mergeSettings(req["settings"].as<JsonObjectConst>(), next);
    if (!error.empty()) {
      r.reply = errorReply(id, error);
      return r;
    }
    const bool changed = next.name != settings.name || next.token != settings.token ||
                         next.ledCount != settings.ledCount ||
                         next.ledMaxBrightness != settings.ledMaxBrightness;
    // The OTA password is set from the token at startup. Everything else is live.
    const bool restart = next.token != settings.token;
    if (changed) {
      if (!store.save(settings, next)) {
        r.reply = errorReply(id, "storage write failed");
        return r;
      }
      settings = next;
      r.action = LineAction::SETTINGS_CHANGED;
    }
    out["restart"] = restart;

  } else if (cmd == "erase") {
    if (!store.erase()) {
      r.reply = errorReply(id, "storage erase failed");
      return r;
    }
    settings = defaultSettings(defaultName);
    r.action = LineAction::ERASED;

  } else if (cmd == "restart") {
    r.action = LineAction::RESTART;

  } else {
    r.reply = errorReply(id, "unknown command");
    return r;
  }

  r.reply = serialize(out);
  return r;
}

std::string oversizedLineReply(const char *prefix, size_t len) {
  if (len == 0 || prefix[0] != '{') return std::string();
  return errorReply(scanForId(prefix, len), "line too long");
}

std::string frameReply(const std::string &reply) { return "\n" + reply + "\n"; }

// ---------------------------------------------------------------------------
// byte demultiplexer
// ---------------------------------------------------------------------------
static const uint8_t IMPROV_SIGNATURE[7] = {'I', 'M', 'P', 'R', 'O', 'V', improv::IMPROV_SERIAL_VERSION};

static uint8_t signatureSum() {
  uint8_t sum = 0;
  for (size_t i = 0; i < sizeof(IMPROV_SIGNATURE); i++) sum += IMPROV_SIGNATURE[i];
  return sum;
}

SerialDemux::Event SerialDemux::feed(uint8_t byte, uint32_t nowMs) {
  if (seenByte_ && nowMs - lastByteMs_ > SERIAL_IDLE_RESET_MS) {
    lineLen_ = 0;
    lineOverflow_ = false;
    inPacket_ = false;
    sigPos_ = 0;
  }
  seenByte_ = true;
  lastByteMs_ = nowMs;

  if (inPacket_) return feedPacket(byte);

  const Event none = {EV_NONE, 0, nullptr, 0};
  if (byte == IMPROV_SIGNATURE[sigPos_]) {
    if (++sigPos_ == sizeof(IMPROV_SIGNATURE)) {
      sigPos_ = 0;
      packetPos_ = 0;
      inPacket_ = true;
    }
    return none;
  }
  if (sigPos_ > 0) {
    // It wasn't a packet after all: the held-back bytes belong to the line.
    for (uint8_t i = 0; i < sigPos_; i++) pushLine(IMPROV_SIGNATURE[i]);
    sigPos_ = 0;
    if (byte == IMPROV_SIGNATURE[0]) {
      sigPos_ = 1;
      return none;
    }
  }
  return feedLine(byte);
}

SerialDemux::Event SerialDemux::feedPacket(uint8_t byte) {
  packet_[packetPos_++] = byte;
  // packet_[1] is the data length, so the total is known from the second byte.
  if (packetPos_ < 2 || packetPos_ < 2u + packet_[1] + 1u) {
    const Event none = {EV_NONE, 0, nullptr, 0};
    return none;
  }
  inPacket_ = false;
  uint8_t sum = signatureSum();
  for (size_t i = 0; i + 1 < packetPos_; i++) sum += packet_[i];
  Event ev = {sum == byte ? EV_IMPROV_PACKET : EV_IMPROV_BAD_CHECKSUM, packet_[0], packet_ + 2, packet_[1]};
  return ev;
}

void SerialDemux::pushLine(uint8_t byte) {
  if (lineLen_ < MAX_LINE_BYTES) {
    line_[lineLen_++] = byte;
  } else {
    lineOverflow_ = true;
  }
}

SerialDemux::Event SerialDemux::feedLine(uint8_t byte) {
  Event ev = {EV_NONE, 0, nullptr, 0};
  if (byte != '\n') {
    pushLine(byte);
    return ev;
  }
  size_t len = lineLen_;
  lineLen_ = 0;
  if (lineOverflow_) {
    lineOverflow_ = false;
    ev.type = EV_LINE_TOO_LONG;
    ev.data = line_;
    ev.len = len;
    return ev;
  }
  if (len > 0 && line_[len - 1] == '\r') len--;
  if (len > 0) {
    ev.type = EV_LINE;
    ev.data = line_;
    ev.len = len;
  }
  return ev;
}

// ---------------------------------------------------------------------------
// Improv Serial
// ---------------------------------------------------------------------------
static Bytes buildPacket(uint8_t type, const uint8_t *data, size_t len) {
  Bytes out;
  out.reserve(1 + sizeof(IMPROV_SIGNATURE) + 2 + len + 2);
  out.push_back('\n');
  out.insert(out.end(), IMPROV_SIGNATURE, IMPROV_SIGNATURE + sizeof(IMPROV_SIGNATURE));
  out.push_back(type);
  out.push_back(static_cast<uint8_t>(len));
  out.insert(out.end(), data, data + len);
  uint8_t sum = 0;
  for (size_t i = 1; i < out.size(); i++) sum += out[i];
  out.push_back(sum);
  out.push_back('\n');
  return out;
}

Bytes improvStatePacket(uint8_t state) { return buildPacket(improv::TYPE_CURRENT_STATE, &state, 1); }

Bytes improvErrorPacket(uint8_t error) { return buildPacket(improv::TYPE_ERROR_STATE, &error, 1); }

Bytes improvRpcResultPacket(uint8_t command, const std::vector<std::string> &strings) {
  // add_checksum=false: the SDK leaves a trailing 0 for its RPC checksum, which
  // serial doesn't use because the packet carries its own.
  std::vector<uint8_t> rpc = improv::build_rpc_response(static_cast<improv::Command>(command), strings, false);
  return buildPacket(improv::TYPE_RPC_RESPONSE, rpc.data(), rpc.size() - 1);
}

void improvProvisionedPackets(std::vector<Bytes> &out) {
  // No URL: the speaker has no web page to send the browser to.
  out.push_back(improvStatePacket(improv::STATE_PROVISIONED));
  out.push_back(improvRpcResultPacket(improv::WIFI_SETTINGS, std::vector<std::string>()));
}

void improvProvisionFailedPackets(std::vector<Bytes> &out) {
  out.push_back(improvErrorPacket(improv::ERROR_UNABLE_TO_CONNECT));
  out.push_back(improvStatePacket(improv::STATE_AUTHORIZED));
}

void improvScanPackets(const std::vector<ScanEntry> &entries, std::vector<Bytes> &out) {
  std::vector<ScanEntry> unique;
  for (size_t i = 0; i < entries.size(); i++) {
    if (entries[i].ssid.empty()) continue;
    bool seen = false;
    for (size_t k = 0; k < unique.size(); k++) {
      if (unique[k].ssid == entries[i].ssid) {
        if (entries[i].rssi > unique[k].rssi) unique[k] = entries[i];
        seen = true;
        break;
      }
    }
    if (!seen) unique.push_back(entries[i]);
  }
  for (size_t i = 0; i < unique.size(); i++) {
    char rssi[12];
    snprintf(rssi, sizeof(rssi), "%d", unique[i].rssi);
    std::vector<std::string> fields;
    fields.push_back(unique[i].ssid);
    fields.push_back(rssi);
    fields.push_back(unique[i].secured ? "YES" : "NO");
    out.push_back(improvRpcResultPacket(improv::GET_WIFI_NETWORKS, fields));
  }
  out.push_back(improvRpcResultPacket(improv::GET_WIFI_NETWORKS, std::vector<std::string>()));
}

static void handleRpc(const uint8_t *payload, size_t len, ImprovHost &host, std::vector<Bytes> &out) {
  // parse_improv_data() reads the first two bytes without checking the length.
  if (len < 2 || payload[1] != len - 2) {
    out.push_back(improvErrorPacket(improv::ERROR_INVALID_RPC));
    return;
  }
  const uint8_t rawCommand = payload[0];
  improv::ImprovCommand cmd = improv::parse_improv_data(payload, len, false);

  // The spec asks for the error state to be cleared when an RPC arrives.
  out.push_back(improvErrorPacket(improv::ERROR_NONE));

  switch (rawCommand) {
    case improv::WIFI_SETTINGS:
      // A malformed payload makes the SDK report the command as UNKNOWN.
      if (cmd.command != improv::WIFI_SETTINGS || cmd.ssid.empty() || cmd.ssid.size() > 32 ||
          cmd.password.size() > 64) {
        out.push_back(improvErrorPacket(improv::ERROR_INVALID_RPC));
        return;
      }
      if (!host.startProvisioning(cmd.ssid, cmd.password)) {
        out.push_back(improvErrorPacket(improv::ERROR_UNKNOWN));
        return;
      }
      out.push_back(improvStatePacket(improv::STATE_PROVISIONING));
      return;

    case improv::GET_CURRENT_STATE: {
      const uint8_t state = host.improvState();
      out.push_back(improvStatePacket(state));
      if (state == improv::STATE_PROVISIONED) {
        out.push_back(improvRpcResultPacket(improv::GET_CURRENT_STATE, std::vector<std::string>()));
      }
      return;
    }

    case improv::GET_DEVICE_INFO: {
      // A name from older firmware could be long. Keep the packet in range.
      std::string name = host.deviceName();
      if (name.size() > 64) name.resize(64);
      std::vector<std::string> info;
      info.push_back(FW_NAME);
      info.push_back(FW_VERSION);
      info.push_back(HW_NAME);
      info.push_back(name);
      out.push_back(improvRpcResultPacket(improv::GET_DEVICE_INFO, info));
      return;
    }

    case improv::GET_WIFI_NETWORKS:
      host.startScan();
      return;

    default:
      out.push_back(improvErrorPacket(improv::ERROR_UNKNOWN_RPC));
      return;
  }
}

void handleImprovEvent(const SerialDemux::Event &ev, ImprovHost &host, std::vector<Bytes> &out) {
  if (ev.type == SerialDemux::EV_IMPROV_BAD_CHECKSUM) {
    out.push_back(improvErrorPacket(improv::ERROR_INVALID_RPC));
  } else if (ev.type == SerialDemux::EV_IMPROV_PACKET && ev.improvType == improv::TYPE_RPC) {
    handleRpc(ev.data, ev.len, host, out);
  }
}

}  // namespace lumen
