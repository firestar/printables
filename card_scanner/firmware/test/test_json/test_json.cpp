// Host link JSON: flat request parsing and reply writing.  Run: pio test -e native

#include <math.h>
#include <string.h>
#include <unity.h>

#include "cs_json.h"

using namespace cs;

void setUp() {}
void tearDown() {}

static void test_parse_request() {
  JsonObject o;
  TEST_ASSERT_TRUE(o.parse(" {\"id\": 12, \"cmd\":\"lights\",\"top\":255,\"bottom\":0} "));
  TEST_ASSERT_EQUAL_INT(4, o.size());
  int32_t id = 0;
  TEST_ASSERT_TRUE(o.getInt("id", id));
  TEST_ASSERT_EQUAL_INT(12, id);
  TEST_ASSERT_EQUAL_STRING("lights", o.getStr("cmd"));
  int32_t top = 0;
  TEST_ASSERT_TRUE(o.getInt("top", top));
  TEST_ASSERT_EQUAL_INT(255, top);
  TEST_ASSERT_NULL(o.getStr("top"));  // a number is not a string
  TEST_ASSERT_FALSE(o.has("nope"));
}

static void test_parse_values() {
  JsonObject o;
  TEST_ASSERT_TRUE(o.parse("{\"a\":-1.5e2,\"b\":true,\"c\":false,\"d\":null,\"e\":\"x\\\"y\\\\z\\u0041\\n\"}"));
  double a = 0;
  TEST_ASSERT_TRUE(o.getNum("a", a));
  TEST_ASSERT_TRUE(a == -150.0);
  int32_t ai;
  TEST_ASSERT_TRUE(o.getInt("a", ai));
  TEST_ASSERT_EQUAL_INT(-150, ai);
  TEST_ASSERT_TRUE(o.find("b")->type == JT_BOOL && o.find("b")->b);
  TEST_ASSERT_TRUE(o.find("c")->type == JT_BOOL && !o.find("c")->b);
  TEST_ASSERT_TRUE(o.find("d")->type == JT_NULL);
  TEST_ASSERT_EQUAL_STRING("x\"y\\zA\n", o.getStr("e"));
  TEST_ASSERT_TRUE(o.parse("{}"));
  TEST_ASSERT_EQUAL_INT(0, o.size());
  TEST_ASSERT_TRUE(o.parse("{\"v\":0.25}"));
  TEST_ASSERT_FALSE(o.getInt("v", ai));  // fraction is not an int
}

static void test_parse_rejects() {
  JsonObject o;
  const char *bad[] = {
      "",
      "[]",
      "{",
      "{\"id\":1,}",
      "{\"id\":1} x",
      "{\"id\":01}",
      "{\"id\":+1}",
      "{\"id\":1.}",
      "{\"id\":.5}",
      "{\"id\":NaN}",
      "{\"id\":1,\"id\":2}",
      "{\"a\":{\"b\":1}}",
      "{\"a\":[1]}",
      "{\"a\":tru}",
      "{\"a\":\"unterminated}",
      "{\"key_longer_than_15\":1}",
      "{\"s\":\"0123456789012345678901234567890123456789\"}",
      "{\"a\":1,\"b\":2,\"c\":3,\"d\":4,\"e\":5,\"f\":6,\"g\":7,\"h\":8,\"i\":9}",
      "{\"a\":\"\\q\"}",
      "{\"a\":\"\\u00zz\"}",
      "{\"a\":\"\\u0000\"}",
      "{a:1}",
  };
  for (const char *s : bad) {
    if (o.parse(s)) TEST_FAIL_MESSAGE(s);
  }
  TEST_ASSERT_FALSE(o.parse(nullptr));
}

static void test_writer() {
  char buf[200];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", 3).boolean("ok", true).str("msg", "a\"b\\c\n").num("v", 12.5).num("k", 7, 1);
  w.open("s").boolean("x", false).integer("y", -2).close();
  w.num("i", 150).num("n", NAN).close();
  TEST_ASSERT_TRUE(w.ok());
  TEST_ASSERT_EQUAL_STRING(
      "{\"id\":3,\"ok\":true,\"msg\":\"a\\\"b\\\\c\\u000a\",\"v\":12.5,\"k\":7.0,\"s\":{\"x\":false,\"y\":-2},"
      "\"i\":150,\"n\":null}",
      w.c_str());
}
static void test_writer_overflow() {
  char buf[16];
  JsonWriter w(buf, sizeof(buf));
  w.open().str("msg", "this is far too long").close();
  TEST_ASSERT_FALSE(w.ok());
  TEST_ASSERT_TRUE(strlen(buf) < sizeof(buf));
}

static void test_roundtrip() {
  char buf[128];
  JsonWriter w(buf, sizeof(buf));
  w.open().integer("id", 9).str("cmd", "set").str("key", "feed_speed").num("value", 180.5).close();
  JsonObject o;
  TEST_ASSERT_TRUE(o.parse(buf));
  double v;
  TEST_ASSERT_TRUE(o.getNum("value", v));
  TEST_ASSERT_TRUE(v == 180.5);
  TEST_ASSERT_EQUAL_STRING("feed_speed", o.getStr("key"));
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_parse_request);
  RUN_TEST(test_parse_values);
  RUN_TEST(test_parse_rejects);
  RUN_TEST(test_writer);
  RUN_TEST(test_writer_overflow);
  RUN_TEST(test_roundtrip);
  return UNITY_END();
}
