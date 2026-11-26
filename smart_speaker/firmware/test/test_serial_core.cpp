// Native tests for the hardware-free serial core. Run with tools/run_native_tests.py.
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include <improv.h>

#include "serial_core.h"

using namespace lumen;

static int checks = 0, failures = 0;

#define CHECK(cond)                                                \
  do {                                                             \
    checks++;                                                      \
    if (!(cond)) {                                                 \
      failures++;                                                  \
      printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);       \
    }                                                              \
  } while (0)

#define CHECK_EQ(actual, expected)                                               \
  do {                                                                           \
    checks++;                                                                    \
    const std::string a_ = (actual), e_ = (expected);                            \
    if (a_ != e_) {                                                              \
      failures++;                                                                \
      printf("FAIL %s:%d:\n  got      %s\n  expected %s\n", __FILE__, __LINE__,  \
             a_.c_str(), e_.c_str());                                            \
    }                                                                            \
  } while (0)

static const char SECRET[] = "hunter2-very-secret-token";

class MockStore : public SettingsStore {
 public:
  bool failSave = false, failErase = false;
  int saves = 0, erases = 0;
  bool save(const Settings &, const Settings &) override {
    if (failSave) return false;
    saves++;
    return true;
  }
  bool erase() override {
    if (failErase) return false;
    erases++;
    return true;
  }
};

class MockHost : public ImprovHost {
 public:
  uint8_t state = improv::STATE_AUTHORIZED;
  std::string name = "Kitchen";
  std::string ssid, password;
  bool refuse = false;
  int provisions = 0, scans = 0;
  uint8_t improvState() override { return state; }
  std::string deviceName() override { return name; }
  bool startProvisioning(const std::string &s, const std::string &p) override {
    if (refuse) return false;
    ssid = s;
    password = p;
    provisions++;
    return true;
  }
  void startScan() override { scans++; }
};

static const std::string DEVICE_DEFAULT = "roundspk-abcd";

struct Fixture {
  Settings settings = defaultSettings(DEVICE_DEFAULT);
  MockStore store;
  LineResult send(const std::string &line) {
    return handleLine(line.data(), line.size(), settings, DEVICE_DEFAULT, store);
  }
  std::string reply(const std::string &line) { return send(line).reply; }
};

static bool sameSettings(const Settings &a, const Settings &b) {
  return a.name == b.name && a.token == b.token && a.ledCount == b.ledCount &&
         a.ledMaxBrightness == b.ledMaxBrightness;
}

static std::string setLine(int id, const std::string &settingsJson) {
  return "{\"lumen\":1,\"id\":" + std::to_string(id) + ",\"cmd\":\"set\",\"settings\":" + settingsJson + "}";
}

// ---- contract ---------------------------------------------------------------
static void testInfo() {
  Fixture f;
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":1,\"cmd\":\"info\"}"),
           "{\"id\":1,\"ok\":true,\"project\":\"speaker\",\"fw\":\"" FW_VERSION "\",\"schema\":1}");
}

static void testGetDefaults() {
  Fixture f;
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":2,\"cmd\":\"get\"}"),
           "{\"id\":2,\"ok\":true,\"settings\":{\"name\":\"roundspk-abcd\",\"led_count\":39,"
           "\"led_max_brightness\":150,\"token_set\":false}}");
}

static void testSetAllFields() {
  Fixture f;
  LineResult r = f.send(setLine(3, "{\"name\":\"Kitchen\",\"led_count\":60,\"led_max_brightness\":90}"));
  CHECK_EQ(r.reply, "{\"id\":3,\"ok\":true,\"restart\":false}");
  CHECK(r.action == LineAction::SETTINGS_CHANGED);
  CHECK_EQ(f.settings.name, "Kitchen");
  CHECK(f.settings.ledCount == 60);
  CHECK(f.settings.ledMaxBrightness == 90);
  CHECK(f.store.saves == 1);
}

static void testSetSubsetKeepsOthers() {
  Fixture f;
  f.send(setLine(1, "{\"name\":\"Kitchen\"}"));
  f.send(setLine(2, "{\"led_count\":12}"));
  CHECK_EQ(f.settings.name, "Kitchen");
  CHECK(f.settings.ledCount == 12);
  CHECK(f.settings.ledMaxBrightness == LED_MAX_BRIGHTNESS_DEFAULT);
}

static void testTokenChangeNeedsRestart() {
  Fixture f;
  CHECK_EQ(f.reply(setLine(3, "{\"token\":\"abc\"}")), "{\"id\":3,\"ok\":true,\"restart\":true}");
  CHECK_EQ(f.settings.token, "abc");
  // Setting the same value again changes nothing and writes nothing.
  CHECK_EQ(f.reply(setLine(4, "{\"token\":\"abc\"}")), "{\"id\":4,\"ok\":true,\"restart\":false}");
  CHECK(f.store.saves == 1);
  // An empty token clears it.
  CHECK_EQ(f.reply(setLine(5, "{\"token\":\"\"}")), "{\"id\":5,\"ok\":true,\"restart\":true}");
  CHECK(f.settings.token.empty());
}

static void testBoundaryValues() {
  Fixture f;
  CHECK(f.send(setLine(1, "{\"led_count\":1}")).action == LineAction::SETTINGS_CHANGED);
  CHECK(f.settings.ledCount == 1);
  CHECK(f.send(setLine(2, "{\"led_count\":300}")).action == LineAction::SETTINGS_CHANGED);
  CHECK(f.settings.ledCount == 300);
  CHECK(f.send(setLine(3, "{\"led_max_brightness\":0}")).action == LineAction::SETTINGS_CHANGED);
  CHECK(f.settings.ledMaxBrightness == 0);
  CHECK(f.send(setLine(4, "{\"led_max_brightness\":255}")).action == LineAction::SETTINGS_CHANGED);
  CHECK(f.settings.ledMaxBrightness == 255);
  CHECK(f.send(setLine(5, "{\"name\":\"" + std::string(32, 'n') + "\"}")).action == LineAction::SETTINGS_CHANGED);
  CHECK(f.send(setLine(6, "{\"token\":\"" + std::string(64, 't') + "\"}")).action == LineAction::SETTINGS_CHANGED);
  CHECK(f.settings.token.size() == 64);
}

static void testBadValuesRejected() {
  const char *bad[] = {
      "{\"led_count\":0}",
      "{\"led_count\":301}",
      "{\"led_count\":-1}",
      "{\"led_count\":39.5}",
      "{\"led_count\":39.0}",
      "{\"led_count\":\"39\"}",
      "{\"led_count\":true}",
      "{\"led_count\":null}",
      "{\"led_count\":99999999999999999999}",
      "{\"led_max_brightness\":256}",
      "{\"led_max_brightness\":-1}",
      "{\"led_max_brightness\":[1]}",
      "{\"name\":\"\"}",
      "{\"name\":7}",
      "{\"name\":null}",
      "{\"name\":\"bad\\nname\"}",
      "{\"name\":\"nul\\u0000name\"}",
      "{\"name\":\"\\u007f\"}",
      "{\"token\":7}",
      "{\"token\":\"tab\\there\"}",
      "{\"token_set\":true}",
      "{\"hub_token\":\"abc\"}",
      "{\"led_max\":90}",
      "{\"surprise\":1}",
  };
  for (const char *b : bad) {
    Fixture f;
    const Settings before = f.settings;
    LineResult r = f.send(setLine(7, b));
    CHECK(r.reply.find("\"ok\":false") != std::string::npos);
    CHECK(r.reply.find("\"id\":7") != std::string::npos);
    CHECK(r.action == LineAction::NONE);
    CHECK(sameSettings(before, f.settings));
    CHECK(f.store.saves == 0);
  }
  Fixture f;
  CHECK(f.reply(setLine(1, "{\"name\":\"" + std::string(33, 'n') + "\"}")).find("\"ok\":false") != std::string::npos);
  CHECK(f.reply(setLine(2, "{\"token\":\"" + std::string(65, 't') + "\"}")).find("\"ok\":false") != std::string::npos);
  CHECK_EQ(f.reply(setLine(3, "{\"led_count\":301}")), "{\"id\":3,\"ok\":false,\"error\":\"led_count out of range\"}");
  CHECK_EQ(f.reply(setLine(4, "{\"led_max\":9}")), "{\"id\":4,\"ok\":false,\"error\":\"unknown setting: led_max\"}");
}

static void testInvalidUtf8Rejected() {
  const std::vector<std::string> bad = {"\xC0\xAF", "\xE0\x80\x80", "\xED\xA0\x80", "\xF5\x80\x80\x80", "abc\xC3", "\xFF"};
  for (const std::string &s : bad) {
    CHECK(!isValidName(s.data(), s.size()));
    CHECK(!isValidToken(s.data(), s.size()));
    Fixture f;
    CHECK(f.reply(setLine(1, "{\"name\":\"" + s + "\"}")).find("\"ok\":false") != std::string::npos);
  }
  const std::string good = "K\xC3\xBC" "che \xE2\x82\xAC \xF0\x9F\x94\x8A";
  CHECK(isValidName(good.data(), good.size()));
  Fixture f;
  CHECK(f.reply(setLine(1, "{\"name\":\"" + good + "\"}")).find("\"ok\":true") != std::string::npos);
  CHECK_EQ(f.settings.name, good);
  // The limit is in bytes: 11 three-byte characters are 33 bytes.
  std::string euros;
  for (int i = 0; i < 11; i++) euros += "\xE2\x82\xAC";
  CHECK(!isValidName(euros.data(), euros.size()));
}

static void testAtomicReject() {
  // Good values before and after the bad one must not be applied.
  const char *mixed[] = {
      "{\"name\":\"Good\",\"token\":\"goodtoken\",\"led_count\":301}",
      "{\"led_count\":301,\"name\":\"Good\",\"token\":\"goodtoken\"}",
      "{\"name\":\"Good\",\"led_max_brightness\":999,\"led_count\":40}",
      "{\"token\":\"goodtoken\",\"surprise\":1}",
  };
  for (const char *m : mixed) {
    Fixture f;
    f.settings.token = "oldtoken";
    const Settings before = f.settings;
    LineResult r = f.send(setLine(9, m));
    CHECK(r.reply.find("\"ok\":false") != std::string::npos);
    CHECK(r.action == LineAction::NONE);
    CHECK(sameSettings(before, f.settings));
    CHECK(f.store.saves == 0);
  }
}

static void testStoreFailureLeavesSettingsAlone() {
  Fixture f;
  f.store.failSave = true;
  const Settings before = f.settings;
  LineResult r = f.send(setLine(1, "{\"name\":\"Good\",\"token\":\"abc\"}"));
  CHECK_EQ(r.reply, "{\"id\":1,\"ok\":false,\"error\":\"storage write failed\"}");
  CHECK(r.action == LineAction::NONE);
  CHECK(sameSettings(before, f.settings));
}

static void testErase() {
  Fixture f;
  f.settings.token = SECRET;
  f.settings.name = "Kitchen";
  f.settings.ledCount = 100;
  LineResult r = f.send("{\"lumen\":1,\"id\":4,\"cmd\":\"erase\"}");
  CHECK_EQ(r.reply, "{\"id\":4,\"ok\":true}");
  CHECK(r.action == LineAction::ERASED);
  CHECK(f.store.erases == 1);
  CHECK(f.settings.token.empty());
  CHECK_EQ(f.settings.name, DEVICE_DEFAULT);
  CHECK(f.settings.ledCount == LED_COUNT_DEFAULT);

  Fixture g;
  g.settings.token = SECRET;
  g.store.failErase = true;
  LineResult e = g.send("{\"lumen\":1,\"id\":4,\"cmd\":\"erase\"}");
  CHECK(e.reply.find("\"ok\":false") != std::string::npos);
  CHECK(e.action == LineAction::NONE);
  CHECK_EQ(g.settings.token, SECRET);
}

static void testRestart() {
  Fixture f;
  LineResult r = f.send("{\"lumen\":1,\"id\":5,\"cmd\":\"restart\"}");
  CHECK_EQ(r.reply, "{\"id\":5,\"ok\":true}");
  CHECK(r.action == LineAction::RESTART);
}

static void testEnvelope() {
  Fixture f;
  // Log output and JSON that isn't addressed to us: ignored, no reply.
  CHECK_EQ(f.reply("ready: ws://10.0.0.2:8080/"), "");
  CHECK_EQ(f.reply("  {\"lumen\":1,\"id\":1,\"cmd\":\"info\"}"), "");
  CHECK_EQ(f.reply("{\"type\":\"status\"}"), "");
  CHECK_EQ(f.reply(""), "");
  // Addressed to us, but wrong.
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":6,\"cmd\":\"nope\"}"), "{\"id\":6,\"ok\":false,\"error\":\"unknown command\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":6}"), "{\"id\":6,\"ok\":false,\"error\":\"unknown command\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":6,\"cmd\":7}"), "{\"id\":6,\"ok\":false,\"error\":\"unknown command\"}");
  CHECK_EQ(f.reply("{\"lumen\":2,\"id\":6,\"cmd\":\"info\"}"), "{\"id\":6,\"ok\":false,\"error\":\"unsupported protocol version\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"cmd\":\"info\"}"), "{\"id\":null,\"ok\":false,\"error\":\"id must be an integer\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":\"x\",\"cmd\":\"info\"}"), "{\"id\":null,\"ok\":false,\"error\":\"id must be an integer\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":6,\"cmd\":\"set\"}"), "{\"id\":6,\"ok\":false,\"error\":\"settings must be an object\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":6,\"cmd\":\"set\",\"settings\":3}"), "{\"id\":6,\"ok\":false,\"error\":\"settings must be an object\"}");
  // Broken JSON: the id is recovered where possible.
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":8,\"cmd\":"), "{\"id\":8,\"ok\":false,\"error\":\"bad json\"}");
  CHECK_EQ(f.reply("{garbage"), "{\"id\":null,\"ok\":false,\"error\":\"bad json\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":8,\"cmd\":\"info\"} trailing"), "{\"id\":8,\"ok\":false,\"error\":\"bad json\"}");
  CHECK_EQ(f.reply("{\"lumen\":1,\"id\":8,\"cmd\":\"info\"}{\"lumen\":1}"), "{\"id\":8,\"ok\":false,\"error\":\"bad json\"}");
  std::string deep = "{\"lumen\":1,\"id\":8,\"x\":";
  for (int i = 0; i < 40; i++) deep += "[";
  CHECK(f.reply(deep).find("\"ok\":false") != std::string::npos);
  // Trailing whitespace is harmless.
  CHECK(f.reply("{\"lumen\":1,\"id\":8,\"cmd\":\"info\"}  ").find("\"ok\":true") != std::string::npos);
  // The id inside a string value isn't mistaken for the real one.
  CHECK_EQ(f.reply("{\"lumen\":1,\"name\":\"\\\"id\\\":9\",\"id\":3,\"cmd\":\"nope\""), "{\"id\":3,\"ok\":false,\"error\":\"bad json\"}");
}

// ---- secrets ----------------------------------------------------------------
static void testSecretNeverReturned() {
  Fixture f;
  std::vector<std::string> replies;
  replies.push_back(f.reply(setLine(1, std::string("{\"token\":\"") + SECRET + "\"}")));
  CHECK_EQ(f.settings.token, SECRET);
  replies.push_back(f.reply("{\"lumen\":1,\"id\":2,\"cmd\":\"get\"}"));
  CHECK(replies.back().find("\"token_set\":true") != std::string::npos);
  replies.push_back(f.reply("{\"lumen\":1,\"id\":3,\"cmd\":\"info\"}"));
  // Every way a request carrying a secret can be refused.
  replies.push_back(f.reply(setLine(4, std::string("{\"token\":\"") + SECRET + "\",\"led_count\":0}")));
  replies.push_back(f.reply(setLine(5, std::string("{\"hub_token\":\"") + SECRET + "\"}")));
  replies.push_back(f.reply(std::string("{\"lumen\":1,\"id\":6,\"cmd\":\"set\",\"settings\":{\"token\":\"") + SECRET));
  replies.push_back(f.reply(std::string("{\"lumen\":1,\"id\":7,\"cmd\":\"") + SECRET + "\"}"));
  replies.push_back(f.reply(std::string("{\"lumen\":2,\"id\":8,\"token\":\"") + SECRET + "\"}"));
  f.store.failSave = true;
  replies.push_back(f.reply(setLine(9, "{\"token\":\"changed-value\"}")));
  const std::string big = std::string("{\"lumen\":1,\"id\":10,\"cmd\":\"set\",\"settings\":{\"token\":\"") + SECRET + std::string(2000, 'x');
  replies.push_back(oversizedLineReply(big.data(), MAX_LINE_BYTES));
  CHECK(replies.size() == 10);
  for (const std::string &r : replies) {
    CHECK(!r.empty());
    CHECK(r.find(SECRET) == std::string::npos);
    CHECK(r.find("hunter2") == std::string::npos);
    CHECK(r.find("changed-value") == std::string::npos);
  }
}

// ---- demux ------------------------------------------------------------------
struct DemuxLog {
  std::vector<std::string> lines;
  std::vector<std::vector<uint8_t>> packets;
  std::vector<std::string> oversized;
  int badChecksums = 0;
};

static void feedAll(SerialDemux &d, const std::string &bytes, DemuxLog &log, uint32_t &now) {
  for (size_t i = 0; i < bytes.size(); i++) {
    SerialDemux::Event ev = d.feed(static_cast<uint8_t>(bytes[i]), now);
    if (ev.type == SerialDemux::EV_LINE) log.lines.push_back(std::string(reinterpret_cast<const char *>(ev.data), ev.len));
    if (ev.type == SerialDemux::EV_LINE_TOO_LONG) log.oversized.push_back(std::string(reinterpret_cast<const char *>(ev.data), ev.len));
    if (ev.type == SerialDemux::EV_IMPROV_PACKET) log.packets.push_back(std::vector<uint8_t>(ev.data, ev.data + ev.len));
    if (ev.type == SerialDemux::EV_IMPROV_BAD_CHECKSUM) log.badChecksums++;
  }
}

// An RPC packet exactly as the browser sends it, without the trailing newline.
static std::string rpcPacket(uint8_t command, const std::string &data) {
  std::string p = "IMPROV";
  p += static_cast<char>(1);
  p += static_cast<char>(improv::TYPE_RPC);
  p += static_cast<char>(data.size() + 2);
  p += static_cast<char>(command);
  p += static_cast<char>(data.size());
  p += data;
  uint8_t sum = 0;
  for (char c : p) sum += static_cast<uint8_t>(c);
  p += static_cast<char>(sum);
  return p;
}

static std::string wifiData(const std::string &ssid, const std::string &password) {
  std::string d;
  d += static_cast<char>(ssid.size());
  d += ssid;
  d += static_cast<char>(password.size());
  d += password;
  return d;
}

static void testDemuxLines() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  feedAll(d, "one\ntwo\r\n\n\r\nthree", log, now);
  CHECK(log.lines.size() == 2);
  CHECK_EQ(log.lines[0], "one");
  CHECK_EQ(log.lines[1], "two");
  feedAll(d, "-more\n", log, now);
  CHECK(log.lines.size() == 3);
  CHECK_EQ(log.lines[2], "three-more");
}

static void testDemuxMixed() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  const std::string json1 = "{\"lumen\":1,\"id\":1,\"cmd\":\"info\"}";
  const std::string json2 = "{\"lumen\":1,\"id\":2,\"cmd\":\"get\"}";
  const std::string state = rpcPacket(improv::GET_CURRENT_STATE, "");
  // A password holding the awkward bytes: newline, brace, and a length byte of 10.
  const std::string wifi = rpcPacket(improv::WIFI_SETTINGS, wifiData("Net", "a\nb{c\"\r\n}"));
  feedAll(d, "boot log line\n" + json1 + "\n" + state + "\n" + wifi + "\n" + json2 + "\nmore log\n" + state, log, now);
  CHECK(log.lines.size() == 4);
  CHECK_EQ(log.lines[0], "boot log line");
  CHECK_EQ(log.lines[1], json1);
  CHECK_EQ(log.lines[2], json2);
  CHECK_EQ(log.lines[3], "more log");
  CHECK(log.packets.size() == 3);
  CHECK(log.badChecksums == 0);
  improv::ImprovCommand cmd = improv::parse_improv_data(log.packets[1].data(), log.packets[1].size(), false);
  CHECK(cmd.command == improv::WIFI_SETTINGS);
  CHECK_EQ(cmd.ssid, "Net");
  CHECK_EQ(cmd.password, "a\nb{c\"\r\n}");
}

static void testDemuxPacketInsideLine() {
  // A packet landing in the middle of a line leaves both intact.
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  const std::string packet = rpcPacket(improv::GET_DEVICE_INFO, "");
  feedAll(d, "{\"lumen\":1," + packet + "\"id\":1}\n", log, now);
  CHECK(log.packets.size() == 1);
  CHECK(log.lines.size() == 1);
  CHECK_EQ(log.lines[0], "{\"lumen\":1,\"id\":1}");
}

static void testDemuxSignatureLookalikes() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  const std::string a = "{\"lumen\":1,\"id\":1,\"cmd\":\"set\",\"settings\":{\"name\":\"IMPROV\"}}";
  const std::string b = "IMPRO IIMPROVE IMP";
  const std::string c = "IMPROV";
  const std::string e = std::string("IMPROV") + static_cast<char>(2) + "x";  // other version: not ours
  feedAll(d, a + "\n" + b + "\n" + c + "\n" + e + "\n", log, now);
  CHECK(log.packets.empty());
  CHECK(log.lines.size() == 4);
  CHECK_EQ(log.lines[0], a);
  CHECK_EQ(log.lines[1], b);
  CHECK_EQ(log.lines[2], c);
  CHECK_EQ(log.lines[3], e);
  // A lookalike running straight into a real packet.
  const std::string packet = rpcPacket(improv::GET_DEVICE_INFO, "");
  DemuxLog log2;
  feedAll(d, "IMPRO" + packet + "\n", log2, now);
  CHECK(log2.packets.size() == 1);
  CHECK(log2.lines.size() == 1);
  CHECK_EQ(log2.lines[0], "IMPRO");
}

static void testDemuxBadChecksum() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  std::string p = rpcPacket(improv::GET_DEVICE_INFO, "");
  p[p.size() - 1] = static_cast<char>(p[p.size() - 1] + 1);
  feedAll(d, p + "\n{\"lumen\":1}\n", log, now);
  CHECK(log.packets.empty());
  CHECK(log.badChecksums == 1);
  CHECK(log.lines.size() == 1);
  CHECK_EQ(log.lines[0], "{\"lumen\":1}");
}

static void testDemuxTruncatedPacketRecovers() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  const std::string p = rpcPacket(improv::WIFI_SETTINGS, wifiData("Net", "password"));
  feedAll(d, p.substr(0, p.size() - 5), log, now);
  now += SERIAL_IDLE_RESET_MS + 1;
  feedAll(d, "{\"lumen\":1,\"id\":1}\n", log, now);
  CHECK(log.packets.empty());
  CHECK(log.badChecksums == 0);
  CHECK(log.lines.size() == 1);
  CHECK_EQ(log.lines[0], "{\"lumen\":1,\"id\":1}");
  // Within the idle window the packet is still being read.
  SerialDemux d2;
  DemuxLog log2;
  now = 0;
  feedAll(d2, p.substr(0, 12), log2, now);
  now += SERIAL_IDLE_RESET_MS;
  feedAll(d2, p.substr(12), log2, now);
  CHECK(log2.packets.size() == 1);
}

static void testDemuxPartialLineRecovers() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 1000;
  feedAll(d, "garbage with no newline", log, now);
  now += SERIAL_IDLE_RESET_MS + 1;
  feedAll(d, "{\"lumen\":1}\n", log, now);
  CHECK(log.lines.size() == 1);
  CHECK_EQ(log.lines[0], "{\"lumen\":1}");
  // millis() wrapping around isn't mistaken for a long gap.
  SerialDemux d2;
  DemuxLog log2;
  now = 0xFFFFFFFFu;
  feedAll(d2, "ab", log2, now);
  now = 5;
  feedAll(d2, "cd\n", log2, now);
  CHECK(log2.lines.size() == 1);
  CHECK_EQ(log2.lines[0], "abcd");
}

static void testOversizedLines() {
  SerialDemux d;
  DemuxLog log;
  uint32_t now = 0;
  // Exactly at the limit is fine; one byte more isn't.
  const std::string fits(MAX_LINE_BYTES, 'a');
  feedAll(d, fits + "\n", log, now);
  CHECK(log.lines.size() == 1);
  CHECK(log.oversized.empty());

  const std::string tooLong = "{\"lumen\":1,\"id\":12,\"pad\":\"" + std::string(MAX_LINE_BYTES, 'x') + "\"}";
  feedAll(d, tooLong + "\n", log, now);
  CHECK(log.oversized.size() == 1);
  CHECK(log.oversized[0].size() == MAX_LINE_BYTES);
  CHECK_EQ(oversizedLineReply(log.oversized[0].data(), log.oversized[0].size()),
           "{\"id\":12,\"ok\":false,\"error\":\"line too long\"}");

  // Far beyond the limit, then normal service resumes on the next line.
  const std::string huge(200000, 'y');
  feedAll(d, huge + "\n{\"lumen\":1,\"id\":13}\n", log, now);
  CHECK(log.oversized.size() == 2);
  CHECK_EQ(oversizedLineReply(log.oversized[1].data(), log.oversized[1].size()), "");  // log output: no reply
  CHECK(log.lines.size() == 2);
  CHECK_EQ(log.lines[1], "{\"lumen\":1,\"id\":13}");

  // A packet still gets through while a line is overflowing.
  DemuxLog log2;
  feedAll(d, std::string(MAX_LINE_BYTES + 10, 'z') + rpcPacket(improv::GET_DEVICE_INFO, "") + "more\n", log2, now);
  CHECK(log2.packets.size() == 1);
  CHECK(log2.oversized.size() == 1);

  // The longest valid set request, with every string \u-escaped, must fit.
  std::string name, token;
  for (size_t i = 0; i < NAME_MAX_BYTES; i++) name += "\\u0041";
  for (size_t i = 0; i < TOKEN_MAX_BYTES; i++) token += "\\u0041";
  const std::string longest = setLine(2147483647, "{\"name\":\"" + name + "\",\"token\":\"" + token +
                                                      "\",\"led_count\":300,\"led_max_brightness\":255}");
  CHECK(longest.size() <= MAX_LINE_BYTES);
  Fixture f;
  CHECK(f.reply(longest).find("\"ok\":true") != std::string::npos);
  CHECK(f.settings.token == std::string(TOKEN_MAX_BYTES, 'A'));
}

// ---- Improv -----------------------------------------------------------------
// Decodes what the device sends the same way the browser's Improv client does
// (improv-wifi/sdk-serial-js, ImprovSerial._processInput): a packet is only seen
// if it starts a line, and any other line is discarded up to its newline.
struct ClientParser {
  struct Packet {
    uint8_t type;
    std::vector<uint8_t> data;
    bool checksumOk;
  };
  std::vector<Packet> packets;
  std::vector<std::string> textLines;
  std::vector<uint8_t> line;
  int isImprov = -1;
  size_t improvLength = 0;
  std::string text;

  void feed(uint8_t b) {
    // Text side, as the settings form reads it.
    if (isImprov != 1) {
      if (b == '\n') {
        if (!text.empty()) textLines.push_back(text);
        text.clear();
      } else {
        text += static_cast<char>(b);
      }
    }
    if (isImprov == 0) {
      if (b == 10) isImprov = -1;
      return;
    }
    if (isImprov == 1) {
      line.push_back(b);
      if (line.size() == improvLength) {
        Packet p;
        p.type = line[7];
        p.data.assign(line.begin() + 9, line.begin() + 9 + line[8]);
        uint8_t sum = 0;
        for (size_t i = 0; i + 1 < line.size(); i++) sum += line[i];
        p.checksumOk = sum == line.back();
        packets.push_back(p);
        isImprov = -1;
        line.clear();
        text.clear();
      }
      return;
    }
    if (b == 10) {
      line.clear();
      return;
    }
    line.push_back(b);
    if (line.size() != 9) return;
    isImprov = memcmp(line.data(), "IMPROV", 6) == 0 ? 1 : 0;
    if (isImprov == 0) {
      line.clear();
      return;
    }
    improvLength = 9u + line[8] + 1u;
  }
  void feed(const std::vector<uint8_t> &bytes) {
    for (uint8_t b : bytes) feed(b);
  }
  void feed(const std::string &bytes) {
    for (char c : bytes) feed(static_cast<uint8_t>(c));
  }
};

static std::vector<std::string> rpcStrings(const ClientParser::Packet &p) {
  std::vector<std::string> out;
  size_t i = 2;
  while (i < p.data.size()) {
    const size_t n = p.data[i++];
    out.push_back(std::string(p.data.begin() + i, p.data.begin() + i + n));
    i += n;
  }
  return out;
}

// Sends one RPC through the demux and decodes the replies with the client parser.
static ClientParser exchange(const std::string &packet, MockHost &host) {
  SerialDemux d;
  ClientParser client;
  std::vector<Bytes> out;
  for (char c : packet) {
    SerialDemux::Event ev = d.feed(static_cast<uint8_t>(c), 0);
    handleImprovEvent(ev, host, out);
  }
  for (const Bytes &b : out) client.feed(b);
  return client;
}

static void testImprovDeviceInfo() {
  MockHost host;
  ClientParser c = exchange(rpcPacket(improv::GET_DEVICE_INFO, ""), host);
  CHECK(c.packets.size() == 2);
  CHECK(c.packets[0].type == improv::TYPE_ERROR_STATE);
  CHECK(c.packets[0].data[0] == improv::ERROR_NONE);
  CHECK(c.packets[1].type == improv::TYPE_RPC_RESPONSE);
  CHECK(c.packets[1].checksumOk);
  CHECK(c.packets[1].data[0] == improv::GET_DEVICE_INFO);
  // The RPC's own length byte must match what follows it.
  CHECK(c.packets[1].data[1] == c.packets[1].data.size() - 2);
  const std::vector<std::string> info = rpcStrings(c.packets[1]);
  CHECK(info.size() == 4);
  CHECK_EQ(info[0], FW_NAME);
  CHECK_EQ(info[1], FW_VERSION);
  CHECK_EQ(info[2], HW_NAME);
  CHECK_EQ(info[3], "Kitchen");

  // A very long name from old firmware can't corrupt the packet.
  host.name = std::string(400, 'n');
  ClientParser l = exchange(rpcPacket(improv::GET_DEVICE_INFO, ""), host);
  CHECK(l.packets.size() == 2);
  CHECK(l.packets[1].checksumOk);
  CHECK(rpcStrings(l.packets[1])[3].size() == 64);
}

static void testImprovCurrentState() {
  MockHost host;
  ClientParser c = exchange(rpcPacket(improv::GET_CURRENT_STATE, ""), host);
  CHECK(c.packets.size() == 2);
  CHECK(c.packets[1].type == improv::TYPE_CURRENT_STATE);
  CHECK(c.packets[1].data[0] == improv::STATE_AUTHORIZED);

  // A provisioned device also sends the RPC result the client waits for.
  host.state = improv::STATE_PROVISIONED;
  ClientParser p = exchange(rpcPacket(improv::GET_CURRENT_STATE, ""), host);
  CHECK(p.packets.size() == 3);
  CHECK(p.packets[1].data[0] == improv::STATE_PROVISIONED);
  CHECK(p.packets[2].type == improv::TYPE_RPC_RESPONSE);
  CHECK(p.packets[2].data[0] == improv::GET_CURRENT_STATE);
  CHECK(rpcStrings(p.packets[2]).empty());
}

static void testImprovProvisioning() {
  MockHost host;
  ClientParser c = exchange(rpcPacket(improv::WIFI_SETTINGS, wifiData("MyNet", "hunter2-wifi")), host);
  CHECK(host.provisions == 1);
  CHECK_EQ(host.ssid, "MyNet");
  CHECK_EQ(host.password, "hunter2-wifi");
  CHECK(c.packets.size() == 2);
  CHECK(c.packets[1].type == improv::TYPE_CURRENT_STATE);
  CHECK(c.packets[1].data[0] == improv::STATE_PROVISIONING);
  // Nothing sent back carries the password.
  for (const ClientParser::Packet &p : c.packets) {
    const std::string body(p.data.begin(), p.data.end());
    CHECK(body.find("hunter2") == std::string::npos);
  }

  std::vector<Bytes> ok;
  improvProvisionedPackets(ok);
  ClientParser done;
  for (const Bytes &b : ok) done.feed(b);
  CHECK(done.packets.size() == 2);
  CHECK(done.packets[0].data[0] == improv::STATE_PROVISIONED);
  CHECK(done.packets[1].data[0] == improv::WIFI_SETTINGS);

  std::vector<Bytes> bad;
  improvProvisionFailedPackets(bad);
  ClientParser failed;
  for (const Bytes &b : bad) failed.feed(b);
  CHECK(failed.packets.size() == 2);
  CHECK(failed.packets[0].type == improv::TYPE_ERROR_STATE);
  CHECK(failed.packets[0].data[0] == improv::ERROR_UNABLE_TO_CONNECT);
  CHECK(failed.packets[1].data[0] == improv::STATE_AUTHORIZED);
}

static void testImprovBadRequests() {
  const std::vector<std::string> badWifi = {
      wifiData("", "password"),                     // no SSID
      wifiData(std::string(33, 's'), "password"),   // SSID too long
      wifiData("Net", std::string(65, 'p')),        // password too long
      std::string("\x03" "Ne", 3),                  // SSID runs off the end
      std::string("\x03" "Net" "\x20" "pw", 7),     // password runs off the end
      std::string(),                                // nothing at all
  };
  for (const std::string &data : badWifi) {
    MockHost host;
    ClientParser c = exchange(rpcPacket(improv::WIFI_SETTINGS, data), host);
    CHECK(host.provisions == 0);
    CHECK(!c.packets.empty());
    CHECK(c.packets.back().type == improv::TYPE_ERROR_STATE);
    CHECK(c.packets.back().data[0] == improv::ERROR_INVALID_RPC);
  }

  MockHost host;
  ClientParser unknown = exchange(rpcPacket(0x7E, ""), host);
  CHECK(unknown.packets.back().data[0] == improv::ERROR_UNKNOWN_RPC);

  // The inner length disagrees with the packet.
  std::string lying = "IMPROV";
  lying += static_cast<char>(1);
  lying += static_cast<char>(improv::TYPE_RPC);
  lying += static_cast<char>(2);
  lying += static_cast<char>(improv::GET_DEVICE_INFO);
  lying += static_cast<char>(9);
  uint8_t sum = 0;
  for (char ch : lying) sum += static_cast<uint8_t>(ch);
  lying += static_cast<char>(sum);
  ClientParser l = exchange(lying, host);
  CHECK(l.packets.size() == 1);
  CHECK(l.packets[0].data[0] == improv::ERROR_INVALID_RPC);

  // A payload too short to hold a command.
  std::string shorty = "IMPROV";
  shorty += static_cast<char>(1);
  shorty += static_cast<char>(improv::TYPE_RPC);
  shorty += static_cast<char>(0);
  sum = 0;
  for (char ch : shorty) sum += static_cast<uint8_t>(ch);
  shorty += static_cast<char>(sum);
  ClientParser s = exchange(shorty, host);
  CHECK(s.packets.size() == 1);
  CHECK(s.packets[0].data[0] == improv::ERROR_INVALID_RPC);

  // A bad checksum is reported and nothing runs.
  std::string corrupt = rpcPacket(improv::WIFI_SETTINGS, wifiData("Net", "password"));
  corrupt[corrupt.size() - 1] = static_cast<char>(corrupt[corrupt.size() - 1] ^ 0x55);
  MockHost h2;
  ClientParser b = exchange(corrupt, h2);
  CHECK(h2.provisions == 0);
  CHECK(b.packets.size() == 1);
  CHECK(b.packets[0].data[0] == improv::ERROR_INVALID_RPC);

  // The device refuses because it's busy.
  MockHost busy;
  busy.refuse = true;
  ClientParser r = exchange(rpcPacket(improv::WIFI_SETTINGS, wifiData("Net", "password")), busy);
  CHECK(r.packets.back().type == improv::TYPE_ERROR_STATE);
  CHECK(r.packets.back().data[0] == improv::ERROR_UNKNOWN);
}

static void testImprovScan() {
  MockHost host;
  exchange(rpcPacket(improv::GET_WIFI_NETWORKS, ""), host);
  CHECK(host.scans == 1);

  std::vector<ScanEntry> entries = {{"Home", -70, true}, {"", -40, true}, {"Cafe", -60, false}, {"Home", -50, true}};
  std::vector<Bytes> out;
  improvScanPackets(entries, out);
  ClientParser c;
  for (const Bytes &b : out) c.feed(b);
  CHECK(c.packets.size() == 3);
  const std::vector<std::string> home = rpcStrings(c.packets[0]);
  CHECK(home.size() == 3);
  CHECK_EQ(home[0], "Home");
  CHECK_EQ(home[1], "-50");
  CHECK_EQ(home[2], "YES");
  const std::vector<std::string> cafe = rpcStrings(c.packets[1]);
  CHECK_EQ(cafe[0], "Cafe");
  CHECK_EQ(cafe[2], "NO");
  CHECK(rpcStrings(c.packets[2]).empty());  // ends the list

  // A failed scan still ends the list, or the browser would wait for it.
  std::vector<Bytes> none;
  improvScanPackets(std::vector<ScanEntry>(), none);
  CHECK(none.size() == 1);
}

// Everything the device can send, mixed together, read by both browser parsers.
static void testOutputStreamMixed() {
  ClientParser c;
  const std::string reply = "{\"id\":1,\"ok\":true,\"restart\":false}";
  c.feed(std::string("rst:0x1 (POWERON_RESET),boot:0x13\nets Jul 29 2019"));  // cut off, no newline
  c.feed(improvStatePacket(improv::STATE_AUTHORIZED));
  c.feed(std::string("[E] a log line that was also cut o"));
  c.feed(frameReply(reply));
  c.feed(improvErrorPacket(improv::ERROR_NONE));
  c.feed(std::string("short\n"));
  c.feed(frameReply(reply));
  c.feed(std::string("x"));
  c.feed(improvStatePacket(improv::STATE_PROVISIONED));

  CHECK(c.packets.size() == 3);
  for (const ClientParser::Packet &p : c.packets) CHECK(p.checksumOk);
  int replies = 0;
  for (const std::string &line : c.textLines) {
    if (line[0] == '{') {
      CHECK_EQ(line, reply);
      replies++;
    }
  }
  CHECK(replies == 2);
}

// A whole session through the real pieces, the way main.cpp wires them.
static void testEndToEndSession() {
  SerialDemux d;
  MockHost host;
  Fixture f;
  ClientParser client;
  const std::string input =
      std::string("{\"lumen\":1,\"id\":1,\"cmd\":\"info\"}\n") + rpcPacket(improv::GET_CURRENT_STATE, "") + "\n" +
      setLine(2, std::string("{\"token\":\"") + SECRET + "\"}") + "\n" + rpcPacket(improv::GET_DEVICE_INFO, "") + "\n" +
      "{\"lumen\":1,\"id\":3,\"cmd\":\"get\"}\n" + rpcPacket(improv::WIFI_SETTINGS, wifiData("Net", "wifi-password\n")) + "\n" +
      std::string(MAX_LINE_BYTES + 1, '{') + "\n" + "{\"lumen\":1,\"id\":4,\"cmd\":\"info\"}\n";
  std::string wire;
  for (char ch : input) {
    SerialDemux::Event ev = d.feed(static_cast<uint8_t>(ch), 0);
    if (ev.type == SerialDemux::EV_LINE) {
      wire += frameReply(handleLine(reinterpret_cast<const char *>(ev.data), ev.len, f.settings, DEVICE_DEFAULT, f.store).reply);
    } else if (ev.type == SerialDemux::EV_LINE_TOO_LONG) {
      wire += frameReply(oversizedLineReply(reinterpret_cast<const char *>(ev.data), ev.len));
    } else {
      std::vector<Bytes> out;
      handleImprovEvent(ev, host, out);
      for (const Bytes &b : out) wire.append(b.begin(), b.end());
    }
  }
  client.feed(wire);
  CHECK(wire.find(SECRET) == std::string::npos);
  CHECK(wire.find("wifi-password") == std::string::npos);
  CHECK_EQ(f.settings.token, SECRET);
  CHECK(host.provisions == 1);
  CHECK_EQ(host.password, "wifi-password\n");
  std::vector<std::string> json;
  for (const std::string &line : client.textLines) {
    if (line[0] == '{') json.push_back(line);
  }
  CHECK(json.size() == 5);
  CHECK(json[0].find("\"project\":\"speaker\"") != std::string::npos);
  CHECK_EQ(json[1], "{\"id\":2,\"ok\":true,\"restart\":true}");
  CHECK(json[2].find("\"token_set\":true") != std::string::npos);
  CHECK_EQ(json[3], "{\"id\":null,\"ok\":false,\"error\":\"line too long\"}");
  CHECK(json[4].find("\"id\":4") != std::string::npos);
  for (const ClientParser::Packet &p : client.packets) CHECK(p.checksumOk);
  CHECK(client.packets.size() == 6);  // two for each of the three RPCs
}

// ---- power cap --------------------------------------------------------------
static void testPowerCap() {
  CHECK(LED_POWER_BUDGET_MA < 3000);
  // The default at the reference LED count is untouched.
  CHECK(powerCappedBrightness(39, 150) == 150);
  CHECK(powerCappedBrightness(39, 255) == 196);
  CHECK(powerCappedBrightness(300, 255) == 25);
  CHECK(powerCappedBrightness(300, 10) == 10);
  CHECK(powerCappedBrightness(1, 255) == 255);
  CHECK(powerCappedBrightness(39, 0) == 0);
  // Never over budget, at any count and requested brightness.
  for (uint32_t n = LED_COUNT_MIN; n <= LED_COUNT_MAX; n++) {
    const uint32_t b = powerCappedBrightness(static_cast<uint16_t>(n), 255);
    CHECK(n * LED_FULL_WHITE_MA * b / 255 <= LED_POWER_BUDGET_MA);
  }
  CHECK(sanitizeLedCount(0) == LED_COUNT_DEFAULT);
  CHECK(sanitizeLedCount(301) == LED_COUNT_DEFAULT);
  CHECK(sanitizeLedCount(300) == 300);
  CHECK(sanitizeLedCount(1) == 1);
}

int main() {
  testInfo();
  testGetDefaults();
  testSetAllFields();
  testSetSubsetKeepsOthers();
  testTokenChangeNeedsRestart();
  testBoundaryValues();
  testBadValuesRejected();
  testInvalidUtf8Rejected();
  testAtomicReject();
  testStoreFailureLeavesSettingsAlone();
  testErase();
  testRestart();
  testEnvelope();
  testSecretNeverReturned();
  testDemuxLines();
  testDemuxMixed();
  testDemuxPacketInsideLine();
  testDemuxSignatureLookalikes();
  testDemuxBadChecksum();
  testDemuxTruncatedPacketRecovers();
  testDemuxPartialLineRecovers();
  testOversizedLines();
  testImprovDeviceInfo();
  testImprovCurrentState();
  testImprovProvisioning();
  testImprovBadRequests();
  testImprovScan();
  testOutputStreamMixed();
  testEndToEndSession();
  testPowerCap();
  printf("%d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
