// Command handling + sequencing state machine, run against the SimHal physics
// model in simulated time.  Run: pio test -e native

#include <stdio.h>
#include <string.h>
#include <unity.h>

#include <map>
#include <string>
#include <vector>

#include "cs_json.h"
#include "cs_scanner.h"
#include "cs_sim.h"

using namespace cs;

void setUp() {}
void tearDown() {}

struct Capture : LineSink {
  std::vector<std::string> lines;
  void sendLine(const char *l) override { lines.push_back(l); }
};

struct MemStore : SettingsStore {
  std::map<std::string, float> m;
  bool load(const char *key, float &v) override {
    auto it = m.find(key);
    if (it == m.end()) return false;
    v = it->second;
    return true;
  }
  void save(const char *key, float v) override { m[key] = v; }
};

struct Rig {
  SimHal hal;
  Capture out;
  MemStore store;
  Scanner sc;
  int nextId = 1;
  explicit Rig(const SimConfig &c = SimConfig(), bool start = true) : hal(c), sc(hal, out, &store, "0.1.0") {
    if (start) sc.begin();
  }
  void run(uint32_t ms) {
    for (uint32_t i = 0; i < ms; i++) {
      hal.advance(1);
      sc.tick();
    }
  }
  // Send {"id":N,<body>} and run until the reply with that id arrives.
  std::string call(const char *body, uint32_t maxMs = 120000) {
    int id = nextId++;
    char line[256];
    snprintf(line, sizeof(line), "{\"id\":%d%s%s}", id, *body ? "," : "", body);
    size_t from = out.lines.size();
    sc.handleLine(line);
    char tag[24];
    snprintf(tag, sizeof(tag), "{\"id\":%d,", id);
    for (uint32_t t = 0;; t++) {
      for (size_t i = from; i < out.lines.size(); i++)
        if (out.lines[i].rfind(tag, 0) == 0) return out.lines[i];
      if (t >= maxMs) return "";
      hal.advance(1);
      sc.tick();
    }
  }
  bool sawEvent(const char *name) const {
    std::string needle = std::string("{\"evt\":\"") + name + "\"";
    for (const std::string &l : out.lines)
      if (l.rfind(needle, 0) == 0) return true;
    return false;
  }
};

static bool ok(const std::string &reply) { return reply.find("\"ok\":true") != std::string::npos; }

// The err code of an error reply (msg can be longer than JsonObject keeps, so no parse).
static std::string err(const std::string &reply) {
  const std::string tag = "\"ok\":false,\"err\":\"";
  size_t p = reply.find(tag);
  if (p == std::string::npos) return "<" + reply + ">";
  p += tag.size();
  return reply.substr(p, reply.find('"', p) - p);
}

static void expectOk(const std::string &reply) {
  if (!ok(reply)) TEST_FAIL_MESSAGE(reply.c_str());
}

static void home(Rig &r) {
  expectOk(r.call("\"cmd\":\"home\""));
  TEST_ASSERT_TRUE(r.sc.homed());
}

// ---- protocol basics ----------------------------------------------------------------

static void test_ping() {
  Rig r;
  std::string rep = r.call("\"cmd\":\"ping\"");
  TEST_ASSERT_EQUAL_STRING("{\"id\":1,\"ok\":true,\"fw\":\"0.1.0\"}", rep.c_str());
}

static void test_bad_input() {
  Rig r;
  r.sc.handleLine("not json");
  TEST_ASSERT_EQUAL_STRING("{\"id\":-1,\"ok\":false,\"err\":\"bad_cmd\",\"msg\":\"malformed json\"}",
                           r.out.lines.back().c_str());
  r.sc.handleLine("{\"cmd\":\"ping\"}");
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.out.lines.back()).c_str());
  TEST_ASSERT_TRUE(r.out.lines.back().rfind("{\"id\":-1,", 0) == 0);
  size_t n = r.out.lines.size();
  r.sc.handleLine("   ");  // blank lines are ignored
  TEST_ASSERT_EQUAL_INT((int)n, (int)r.out.lines.size());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"dance\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"sort\",\"bin\":3")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"sort\",\"bin\":1.5")).c_str());
}

static void test_not_homed() {
  Rig r;
  TEST_ASSERT_EQUAL_STRING("not_homed", err(r.call("\"cmd\":\"feed\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("not_homed", err(r.call("\"cmd\":\"sleeve\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("not_homed", err(r.call("\"cmd\":\"sort\",\"bin\":0")).c_str());
  TEST_ASSERT_EQUAL_STRING("not_homed", err(r.call("\"cmd\":\"eject_reject\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("unhomed", stateName(r.sc.state()));
}

static void test_home() {
  Rig r;
  home(r);
  TEST_ASSERT_EQUAL_STRING("idle", stateName(r.sc.state()));
  TEST_ASSERT_TRUE(r.hal.sensor(SN_ELEV_HOME));
  TEST_ASSERT_TRUE(r.hal.sensor(SN_PICK_HOME));
  TEST_ASSERT_TRUE(r.hal.sensor(SN_TONGUE_HOME));
  for (int a = 0; a < AX_COUNT; a++)
    if (a != AX_FEED) TEST_ASSERT_TRUE(r.hal.position((Axis)a) == 0.0f);
  TEST_ASSERT_EQUAL_INT(800, r.hal.current_[AX_ELEV]);
  TEST_ASSERT_TRUE(r.hal.enabled);
}

static void test_home_switch_stuck() {
  Rig r;
  r.hal.forceSensor[SN_ELEV_HOME] = true;
  std::string rep = r.call("\"cmd\":\"home\"");
  TEST_ASSERT_EQUAL_STRING("jam", err(rep).c_str());
  TEST_ASSERT_TRUE(rep.find("elevator home switch stuck") != std::string::npos);
  TEST_ASSERT_FALSE(r.sc.homed());
}

static void test_status() {
  Rig r;
  home(r);
  std::string rep = r.call("\"cmd\":\"status\"");
  TEST_ASSERT_TRUE(rep.rfind("{\"id\":2,\"ok\":true,\"state\":\"idle\",\"homed\":true,", 0) == 0);
  const char *keys[] = {"\"hopper_empty\":false", "\"magazine_empty\":false", "\"sensors\":{\"stack_top\":",
                        "\"elev_home\":true",     "\"lid_open\":false}",    "\"vacuum_kpa\":0.0",
                        "\"lights\":{\"top\":0,\"bottom\":0}"};
  for (const char *k : keys)
    if (rep.find(k) == std::string::npos) TEST_FAIL_MESSAGE(k);
}

// ---- the full cycle ---------------------------------------------------------------

static void test_full_cycle() {
  Rig r;
  home(r);
  expectOk(r.call("\"cmd\":\"lights\",\"top\":200,\"bottom\":40"));
  TEST_ASSERT_EQUAL_INT(200, r.hal.lightTop);
  TEST_ASSERT_EQUAL_INT(40, r.hal.lightBottom);

  for (int card = 0; card < 3; card++) {
    expectOk(r.call("\"cmd\":\"feed\""));
    TEST_ASSERT_TRUE(r.hal.sensor(SN_SCAN_STOP));
    TEST_ASSERT_FALSE(r.hal.out_[OUT_VAC_PUMP]);
    expectOk(r.call("\"cmd\":\"sleeve\""));
    TEST_ASSERT_TRUE(r.sc.sleevedCardOnPlaten());
    TEST_ASSERT_TRUE(r.hal.platenCardSleeved());                // seated by the pawl, still sleeved
    TEST_ASSERT_EQUAL_INT(65, r.hal.servo_[SV_PUSHER]);         // pawl holds at the seat angle
    TEST_ASSERT_TRUE(r.hal.sensor(SN_TONGUE_HOME));
    for (int o = 0; o < OUT_COUNT; o++) TEST_ASSERT_FALSE(r.hal.out_[o]);
    char body[40];
    snprintf(body, sizeof(body), "\"cmd\":\"sort\",\"bin\":%d", card);
    std::string rep = r.call(body);
    expectOk(rep);
    char binTag[16];
    snprintf(binTag, sizeof(binTag), "\"bin\":%d}", card);
    TEST_ASSERT_TRUE(rep.find(binTag) != std::string::npos);
    TEST_ASSERT_EQUAL_INT(1, r.hal.binCount[card]);
  }
  TEST_ASSERT_EQUAL_INT(3, r.hal.sleevedCards);
  TEST_ASSERT_EQUAL_INT(97, r.hal.sleeves);
  TEST_ASSERT_EQUAL_INT(47, r.hal.hopper);
  TEST_ASSERT_EQUAL_STRING("idle", stateName(r.sc.state()));
}

static void test_busy_and_status_during_job() {
  Rig r;
  home(r);
  r.sc.handleLine("{\"id\":50,\"cmd\":\"feed\"}");
  r.run(50);
  TEST_ASSERT_EQUAL_STRING("busy", err(r.call("\"cmd\":\"feed\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("busy", err(r.call("\"cmd\":\"home\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("busy", err(r.call("\"cmd\":\"reset\"")).c_str());
  std::string st = r.call("\"cmd\":\"status\"");
  TEST_ASSERT_TRUE(st.find("\"state\":\"feeding\"") != std::string::npos);
  expectOk(r.call("\"cmd\":\"ping\""));
  r.run(60000);
  bool done = false;
  for (const std::string &l : r.out.lines)
    if (l == "{\"id\":50,\"ok\":true}") done = true;
  TEST_ASSERT_TRUE(done);
}

static void test_sleeve_and_sort_preconditions() {
  Rig r;
  home(r);
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"sleeve\"")).c_str());        // no card
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"eject_reject\"")).c_str());  // no card
  expectOk(r.call("\"cmd\":\"feed\""));
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"feed\"")).c_str());  // card already at scan
  expectOk(r.call("\"cmd\":\"sleeve\""));
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"feed\"")).c_str());  // sleeved card on the platen
  expectOk(r.call("\"cmd\":\"sort\",\"bin\":0"));
  expectOk(r.call("\"cmd\":\"feed\""));
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"sort\",\"bin\":0")).c_str());  // card at scan
  expectOk(r.call("\"cmd\":\"sleeve\""));
}

// ---- error paths ------------------------------------------------------------------

static void test_double_feed_then_reject() {
  SimConfig c;
  c.pDouble = 1;
  Rig r(c);
  home(r);
  std::string rep = r.call("\"cmd\":\"feed\"");
  TEST_ASSERT_EQUAL_STRING("double_feed", err(rep).c_str());
  TEST_ASSERT_TRUE(r.sc.homed());
  TEST_ASSERT_TRUE(r.hal.sensor(SN_SCAN_STOP));
  rep = r.call("\"cmd\":\"eject_reject\"");
  expectOk(rep);
  TEST_ASSERT_TRUE(rep.find("\"bin\":2") != std::string::npos);
  TEST_ASSERT_EQUAL_INT(1, r.hal.binCount[2]);
  TEST_ASSERT_EQUAL_INT(0, r.hal.sleevedCards);
  TEST_ASSERT_EQUAL_INT(100, r.hal.sleeves);
}

static void test_hopper_empty() {
  SimConfig c;
  c.hopperCards = 0;
  Rig r(c);
  home(r);
  TEST_ASSERT_EQUAL_STRING("hopper_empty", err(r.call("\"cmd\":\"feed\"")).c_str());
  TEST_ASSERT_TRUE(r.sawEvent("hopper_empty"));
  TEST_ASSERT_TRUE(r.call("\"cmd\":\"status\"").find("\"hopper_empty\":true") != std::string::npos);
  // already at the top: fails at once, no second event
  size_t events = 0;
  TEST_ASSERT_EQUAL_STRING("hopper_empty", err(r.call("\"cmd\":\"feed\"")).c_str());
  for (const std::string &l : r.out.lines) events += l == "{\"evt\":\"hopper_empty\"}";
  TEST_ASSERT_EQUAL_INT(1, (int)events);
}

static void test_pick_fail() {
  SimConfig c;
  c.pPickFail = 1;
  Rig r(c);
  home(r);
  TEST_ASSERT_EQUAL_STRING("pick_fail", err(r.call("\"cmd\":\"feed\"")).c_str());
  TEST_ASSERT_FALSE(r.hal.out_[OUT_VAC_PUMP]);
  TEST_ASSERT_TRUE(r.sc.homed());
}

static void test_feed_jam() {
  SimConfig c;
  c.scanAt = 1000;  // card never reaches scan_stop
  Rig r(c);
  home(r);
  TEST_ASSERT_EQUAL_STRING("jam", err(r.call("\"cmd\":\"feed\"")).c_str());
}

static void test_sleeve_open_fail() {
  SimConfig c;
  c.pLiftFail = 1;
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  std::string rep = r.call("\"cmd\":\"sleeve\"");
  TEST_ASSERT_EQUAL_STRING("sleeve_open_fail", err(rep).c_str());
  TEST_ASSERT_TRUE(rep.find("lift cup") != std::string::npos);
  for (int o = 0; o < OUT_COUNT; o++) TEST_ASSERT_FALSE(r.hal.out_[o]);
  // the card is still at the scan station and can be rejected
  expectOk(r.call("\"cmd\":\"eject_reject\""));
}

static void test_magazine_empty() {
  SimConfig c;
  c.sleeves = 0;
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  TEST_ASSERT_EQUAL_STRING("magazine_empty", err(r.call("\"cmd\":\"sleeve\"")).c_str());
}

static void test_magazine_low_event() {
  SimConfig c;
  c.sleeves = 11;
  Rig r(c);
  home(r);
  TEST_ASSERT_FALSE(r.sawEvent("magazine_low"));
  expectOk(r.call("\"cmd\":\"feed\""));
  expectOk(r.call("\"cmd\":\"sleeve\""));
  expectOk(r.call("\"cmd\":\"sort\",\"bin\":0"));
  r.run(100);
  TEST_ASSERT_TRUE(r.sawEvent("magazine_low"));
}

static void test_sleeve_insert_fail() {
  SimConfig c;
  c.mouthAt = 1000;  // sleeve_mouth never trips
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  TEST_ASSERT_EQUAL_STRING("sleeve_insert_fail", err(r.call("\"cmd\":\"sleeve\"")).c_str());
  TEST_ASSERT_FALSE(r.sc.homed());  // tongue may be in the sleeve: home again
}

static void test_exit_timeout() {
  SimConfig c;
  c.pExitMiss = 1;
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  expectOk(r.call("\"cmd\":\"sleeve\""));
  TEST_ASSERT_EQUAL_STRING("exit_timeout", err(r.call("\"cmd\":\"sort\",\"bin\":1")).c_str());
  TEST_ASSERT_EQUAL_INT(10, r.hal.servo_[SV_PUSHER]);  // pusher parked again
}

// ---- sleeve pick / seating ----------------------------------------------------------

static void test_sleeve_pick_fail_then_retry() {
  SimConfig c;
  c.pSleevePickFail = 1;  // wheels slip: no sleeve reaches the platen
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  std::string rep = r.call("\"cmd\":\"sleeve\"");
  TEST_ASSERT_EQUAL_STRING("sleeve_open_fail", err(rep).c_str());
  TEST_ASSERT_TRUE(rep.find("sleeve_present") != std::string::npos);
  TEST_ASSERT_FALSE(r.hal.out_[OUT_SLEEVE_PICK]);
  TEST_ASSERT_EQUAL_INT(100, r.hal.sleeves);
  TEST_ASSERT_TRUE(r.sc.homed());
  r.hal.cfg.pSleevePickFail = 0;
  expectOk(r.call("\"cmd\":\"sleeve\""));  // picks again
  TEST_ASSERT_EQUAL_INT(99, r.hal.sleeves);
}

static void test_sleeve_pick_run_too_short() {
  Rig r;
  home(r);
  expectOk(r.call("\"cmd\":\"set\",\"key\":\"sleeve_pick_ms\",\"value\":100"));  // sim needs 250
  expectOk(r.call("\"cmd\":\"feed\""));
  TEST_ASSERT_EQUAL_STRING("sleeve_open_fail", err(r.call("\"cmd\":\"sleeve\"")).c_str());
  TEST_ASSERT_FALSE(r.hal.sleeveOnPlaten());
}
static void test_sleeve_pick_stops_at_sleeve_present() {
  Rig r;
  home(r);
  expectOk(r.call("\"cmd\":\"set\",\"key\":\"sleeve_pick_ms\",\"value\":5000"));  // timeout only
  expectOk(r.call("\"cmd\":\"feed\""));
  r.sc.handleLine("{\"id\":91,\"cmd\":\"sleeve\"}");
  TEST_ASSERT_TRUE(r.hal.out_[OUT_SLEEVE_PICK]);
  for (int i = 0; i < 400 && !r.hal.sensor(SN_SLEEVE_PRESENT); i++) {
    r.hal.advance(1);
    r.sc.tick();
  }
  TEST_ASSERT_TRUE(r.hal.sensor(SN_SLEEVE_PRESENT));
  r.hal.advance(1);
  r.sc.tick();
  TEST_ASSERT_FALSE(r.hal.out_[OUT_SLEEVE_PICK]);  // braked on the sensor, long before 5000 ms
  TEST_ASSERT_EQUAL_INT(99, r.hal.sleeves);
}

static void test_sleeve_present_but_no_platen_grip() {
  SimConfig c;
  c.pSleevePickFail = 1;  // nothing really picked...
  Rig r(c);
  r.hal.forceSensor[SN_SLEEVE_PRESENT] = true;  // ...but the sensor reads a sleeve
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  std::string rep = r.call("\"cmd\":\"sleeve\"");
  TEST_ASSERT_EQUAL_STRING("sleeve_open_fail", err(rep).c_str());
  TEST_ASSERT_TRUE(rep.find("platen vacuum low") != std::string::npos);  // 2nd check caught it
}

static void test_staged_sleeve_is_reused() {
  SimConfig c;
  c.pLiftFail = 1;
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  TEST_ASSERT_EQUAL_STRING("sleeve_open_fail", err(r.call("\"cmd\":\"sleeve\"")).c_str());
  TEST_ASSERT_TRUE(r.hal.sleeveOnPlaten());  // the picked sleeve stays
  TEST_ASSERT_EQUAL_INT(99, r.hal.sleeves);
  r.hal.cfg.pLiftFail = 0;
  expectOk(r.call("\"cmd\":\"sleeve\""));
  TEST_ASSERT_EQUAL_INT(99, r.hal.sleeves);  // no second pick
  expectOk(r.call("\"cmd\":\"sort\",\"bin\":1"));
  TEST_ASSERT_EQUAL_INT(1, r.hal.sleevedCards);
  TEST_ASSERT_FALSE(r.hal.sleeveOnPlaten());
}

static void test_magazine_empty_no_pick() {
  SimConfig c;
  c.sleeves = 0;
  Rig r(c);
  home(r);
  expectOk(r.call("\"cmd\":\"feed\""));
  r.sc.handleLine("{\"id\":90,\"cmd\":\"sleeve\"}");
  TEST_ASSERT_FALSE(r.hal.out_[OUT_SLEEVE_PICK]);  // checked before the wheels run
  TEST_ASSERT_FALSE(r.sc.busy());
  TEST_ASSERT_EQUAL_STRING("magazine_empty", err(r.out.lines.back()).c_str());
}

static void test_seat_needed() {
  Rig r;
  home(r);
  // pawl never leaves rest: the card stays ~70 mm in and the tongues pull the sleeve off
  expectOk(r.call("\"cmd\":\"set\",\"key\":\"pusher_seat_deg\",\"value\":10"));
  expectOk(r.call("\"cmd\":\"feed\""));
  expectOk(r.call("\"cmd\":\"sleeve\""));
  TEST_ASSERT_FALSE(r.hal.platenCardSleeved());
  expectOk(r.call("\"cmd\":\"sort\",\"bin\":0"));
  TEST_ASSERT_EQUAL_INT(0, r.hal.sleevedCards);
  // seated: sleeved
  expectOk(r.call("\"cmd\":\"set\",\"key\":\"pusher_seat_deg\",\"value\":65"));
  expectOk(r.call("\"cmd\":\"feed\""));
  expectOk(r.call("\"cmd\":\"sleeve\""));
  expectOk(r.call("\"cmd\":\"sort\",\"bin\":0"));
  TEST_ASSERT_EQUAL_INT(1, r.hal.sleevedCards);
  TEST_ASSERT_EQUAL_INT(10, r.hal.servo_[SV_PUSHER]);  // parked after the sort
}
// ---- e-stop / lid -----------------------------------------------------------------

static void test_estop_input_aborts_job() {
  Rig r;
  home(r);
  r.sc.handleLine("{\"id\":77,\"cmd\":\"feed\"}");
  r.run(200);
  r.hal.estop = true;
  r.run(50);
  bool aborted = false;
  for (const std::string &l : r.out.lines)
    if (l.rfind("{\"id\":77,\"ok\":false,\"err\":\"estop\"", 0) == 0) aborted = true;
  TEST_ASSERT_TRUE(aborted);
  TEST_ASSERT_TRUE(r.sawEvent("estop"));
  TEST_ASSERT_EQUAL_STRING("estop", stateName(r.sc.state()));
  TEST_ASSERT_FALSE(r.hal.enabled);
  for (int a = 0; a < AX_COUNT; a++) TEST_ASSERT_FALSE(r.hal.moving((Axis)a));
  TEST_ASSERT_EQUAL_STRING("estop", err(r.call("\"cmd\":\"home\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("estop", err(r.call("\"cmd\":\"reset\"")).c_str());  // still pressed
  expectOk(r.call("\"cmd\":\"status\""));
  r.hal.estop = false;
  r.run(50);
  std::string rep = r.call("\"cmd\":\"reset\"");
  expectOk(rep);
  TEST_ASSERT_TRUE(rep.find("\"state\":\"unhomed\"") != std::string::npos);
  home(r);
}

static void test_estop_cmd_and_lid() {
  Rig r;
  home(r);
  expectOk(r.call("\"cmd\":\"estop\""));
  TEST_ASSERT_TRUE(r.sawEvent("estop"));
  TEST_ASSERT_EQUAL_STRING("estop", stateName(r.sc.state()));
  expectOk(r.call("\"cmd\":\"reset\""));
  home(r);
  r.hal.lidOpen = true;
  r.run(50);
  TEST_ASSERT_TRUE(r.sawEvent("lid_open"));
  TEST_ASSERT_EQUAL_STRING("estop", stateName(r.sc.state()));
  TEST_ASSERT_EQUAL_STRING("estop", err(r.call("\"cmd\":\"reset\"")).c_str());
  r.hal.lidOpen = false;
  r.run(50);
  expectOk(r.call("\"cmd\":\"reset\""));
}

static void test_estop_debounce() {
  Rig r;
  home(r);
  r.hal.estop = true;
  r.run(5);
  r.hal.estop = false;
  r.run(50);
  TEST_ASSERT_FALSE(r.sawEvent("estop"));
  TEST_ASSERT_EQUAL_STRING("idle", stateName(r.sc.state()));
}

static void test_boot_with_estop_pressed() {
  SimConfig c;
  Rig r(c, false);
  r.hal.estop = true;
  r.sc.begin();
  TEST_ASSERT_EQUAL_STRING("estop", stateName(r.sc.state()));
  TEST_ASSERT_TRUE(r.sawEvent("estop"));
}

// ---- settings -----------------------------------------------------------------------

static void test_set_get() {
  Rig r;
  std::string rep = r.call("\"cmd\":\"set\",\"key\":\"feed_speed\",\"value\":180.5");
  TEST_ASSERT_EQUAL_STRING("{\"id\":1,\"ok\":true,\"key\":\"feed_speed\",\"value\":180.5}", rep.c_str());
  TEST_ASSERT_TRUE(r.store.m["feed_speed"] == 180.5f);
  rep = r.call("\"cmd\":\"get\",\"key\":\"feed_speed\"");
  TEST_ASSERT_EQUAL_STRING("{\"id\":2,\"ok\":true,\"key\":\"feed_speed\",\"value\":180.5}", rep.c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"set\",\"key\":\"nope\",\"value\":1")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"set\",\"key\":\"feed_speed\",\"value\":9999")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"set\",\"key\":\"feed_speed\",\"value\":\"x\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"set\",\"key\":\"jet_ms\",\"value\":1.5")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"get\",\"key\":\"nope\"")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"get\"")).c_str());
  expectOk(r.call("\"cmd\":\"set\",\"key\":\"cur_feed\",\"value\":700"));
  TEST_ASSERT_EQUAL_INT(700, r.hal.current_[AX_FEED]);
}

static void test_settings_load_from_store() {
  SimConfig c;
  Rig r(c, false);
  r.store.m["tongue_depth_mm"] = 30;
  r.store.m["insert_mm"] = 9999;  // out of range: ignored
  r.sc.begin();
  TEST_ASSERT_TRUE(r.sc.settings().tongue_depth_mm == 30.0f);
  TEST_ASSERT_TRUE(r.sc.settings().insert_mm == 70.0f);
}

static void test_setting_keys_fit_nvs() {
  for (int i = 0; i < settingCount(); i++) {
    const SettingDef &d = settingAt(i);
    if (strlen(d.key) > 15) TEST_FAIL_MESSAGE(d.key);
    Settings s;
    if (!(s.*d.field >= d.lo && s.*d.field <= d.hi)) TEST_FAIL_MESSAGE(d.key);  // default in range
  }
}

static void test_lights_validation() {
  Rig r;
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"lights\",\"top\":256")).c_str());
  TEST_ASSERT_EQUAL_STRING("bad_cmd", err(r.call("\"cmd\":\"lights\",\"bottom\":-1")).c_str());
  std::string rep = r.call("\"cmd\":\"lights\",\"bottom\":9");
  TEST_ASSERT_EQUAL_STRING("{\"id\":3,\"ok\":true,\"top\":0,\"bottom\":9}", rep.c_str());
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_ping);
  RUN_TEST(test_bad_input);
  RUN_TEST(test_not_homed);
  RUN_TEST(test_home);
  RUN_TEST(test_home_switch_stuck);
  RUN_TEST(test_status);
  RUN_TEST(test_full_cycle);
  RUN_TEST(test_busy_and_status_during_job);
  RUN_TEST(test_sleeve_and_sort_preconditions);
  RUN_TEST(test_double_feed_then_reject);
  RUN_TEST(test_hopper_empty);
  RUN_TEST(test_pick_fail);
  RUN_TEST(test_feed_jam);
  RUN_TEST(test_sleeve_open_fail);
  RUN_TEST(test_magazine_empty);
  RUN_TEST(test_magazine_low_event);
  RUN_TEST(test_sleeve_insert_fail);
  RUN_TEST(test_exit_timeout);
  RUN_TEST(test_sleeve_pick_fail_then_retry);
  RUN_TEST(test_sleeve_pick_run_too_short);
  RUN_TEST(test_sleeve_pick_stops_at_sleeve_present);
  RUN_TEST(test_sleeve_present_but_no_platen_grip);
  RUN_TEST(test_staged_sleeve_is_reused);
  RUN_TEST(test_magazine_empty_no_pick);
  RUN_TEST(test_seat_needed);
  RUN_TEST(test_estop_input_aborts_job);
  RUN_TEST(test_estop_cmd_and_lid);
  RUN_TEST(test_estop_debounce);
  RUN_TEST(test_boot_with_estop_pressed);
  RUN_TEST(test_set_get);
  RUN_TEST(test_settings_load_from_store);
  RUN_TEST(test_setting_keys_fit_nvs);
  RUN_TEST(test_lights_validation);
  return UNITY_END();
}
