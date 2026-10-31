#pragma once
// Tiny stand-in for the Unity test framework, just the macros the tests in
// test/ use.  Only for tools/run_native_tests.py on machines without
// PlatformIO; `pio test -e native` uses the real Unity.

#include <setjmp.h>
#include <stdio.h>
#include <string.h>

void setUp();
void tearDown();

namespace unity_shim {
inline int &tests() { static int n = 0; return n; }
inline int &failures() { static int n = 0; return n; }
inline jmp_buf &env() { static jmp_buf e; return e; }
inline void fail(const char *file, int line, const char *msg) {
  printf("%s:%d: FAIL: %s\n", file, line, msg);
  longjmp(env(), 1);
}
inline void run(void (*fn)(), const char *name) {
  tests()++;
  if (setjmp(env()) == 0) {
    setUp();
    fn();
    tearDown();
    printf("  PASS %s\n", name);
  } else {
    failures()++;
    printf("  FAIL %s\n", name);
  }
}
inline void eqInt(long e, long a, const char *expr, const char *file, int line) {
  if (e == a) return;
  char m[160];
  snprintf(m, sizeof(m), "expected %ld got %ld (%s)", e, a, expr);
  fail(file, line, m);
}
// A function call, so temporaries in the arguments live until the compare is done.
inline void eqStr(const char *e, const char *a, const char *file, int line) {
  if (!strcmp(e, a)) return;
  static char m[1024];
  snprintf(m, sizeof(m), "expected \"%s\" got \"%s\"", e, a);
  fail(file, line, m);
}
}  // namespace unity_shim

#define UNITY_BEGIN() (unity_shim::tests() = 0, unity_shim::failures() = 0, 0)
#define UNITY_END()                                                                               \
  (printf("-----------------------\n%d Tests %d Failures 0 Ignored\n%s\n", unity_shim::tests(), \
          unity_shim::failures(), unity_shim::failures() ? "FAIL" : "OK"),                       \
   unity_shim::failures())
#define RUN_TEST(fn) unity_shim::run(fn, #fn)
#define TEST_FAIL_MESSAGE(m) unity_shim::fail(__FILE__, __LINE__, (m))
#define TEST_ASSERT_TRUE(c) \
  do { if (!(c)) unity_shim::fail(__FILE__, __LINE__, "expected TRUE: " #c); } while (0)
#define TEST_ASSERT_FALSE(c) \
  do { if (c) unity_shim::fail(__FILE__, __LINE__, "expected FALSE: " #c); } while (0)
#define TEST_ASSERT_NULL(p) TEST_ASSERT_TRUE((p) == nullptr)
#define TEST_ASSERT_NOT_NULL(p) TEST_ASSERT_TRUE((p) != nullptr)
#define TEST_ASSERT_EQUAL_INT(e, a) unity_shim::eqInt((long)(e), (long)(a), #a, __FILE__, __LINE__)
#define TEST_ASSERT_EQUAL_STRING(e, a) unity_shim::eqStr((e), (a), __FILE__, __LINE__)
