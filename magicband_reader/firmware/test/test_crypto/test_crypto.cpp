// SHA-256 (FIPS 180-4 examples) and HMAC-SHA256 (RFC 4231) vectors for the
// portable implementation.  Run: pio test -e native

#include <stdio.h>
#include <string.h>
#include <unity.h>

#include "mb_sha256.h"

using namespace mb;

void setUp() {}
void tearDown() {}

static void hex2bin(const char *hex, uint8_t *out, size_t *n) {
  size_t k = 0;
  for (; hex[2 * k] && hex[2 * k + 1]; k++) {
    unsigned v;
    sscanf(hex + 2 * k, "%2x", &v);
    out[k] = (uint8_t)v;
  }
  *n = k;
}

static void expectHex(const char *hex, const uint8_t *got, size_t n) {
  uint8_t want[64];
  size_t wn;
  hex2bin(hex, want, &wn);
  TEST_ASSERT_EQUAL_UINT(wn, n);
  TEST_ASSERT_EQUAL_HEX8_ARRAY(want, got, n);
}

static void sha(const char *msg, const char *hex) {
  uint8_t d[32];
  sha256((const uint8_t *)msg, strlen(msg), d);
  expectHex(hex, d, 32);
}

void test_sha256_empty() { sha("", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"); }
void test_sha256_abc() { sha("abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"); }
void test_sha256_two_blocks() {
  sha("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq",
      "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
}

void test_sha256_million_a_chunked() {
  uint8_t chunk[1000];
  memset(chunk, 'a', sizeof(chunk));
  Sha256 s;
  for (int i = 0; i < 1000; i++) s.update(chunk, sizeof(chunk));
  uint8_t d[32];
  s.finish(d);
  expectHex("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0", d, 32);
}

void test_sha256_odd_chunks_match_oneshot() {
  uint8_t msg[300];
  for (int i = 0; i < 300; i++) msg[i] = (uint8_t)(i * 7 + 3);
  uint8_t a[32], b[32];
  sha256(msg, sizeof(msg), a);
  Sha256 s;
  size_t pos = 0, step = 1;
  while (pos < sizeof(msg)) {
    size_t n = step < sizeof(msg) - pos ? step : sizeof(msg) - pos;
    s.update(msg + pos, n);
    pos += n;
    step = step * 3 % 67 + 1;
  }
  s.finish(b);
  TEST_ASSERT_EQUAL_HEX8_ARRAY(a, b, 32);
}

// ---- RFC 4231 ---------------------------------------------------------------------
static void hmacCase(const uint8_t *key, size_t kn, const uint8_t *msg, size_t mn, const char *hex,
                     size_t cmpLen = 32) {
  uint8_t d[32];
  hmacSha256Portable(key, kn, msg, mn, d);
  expectHex(hex, d, cmpLen);
  hmacSha256(key, kn, msg, mn, d);  // the dispatching entry point too
  expectHex(hex, d, cmpLen);
}

void test_rfc4231_case1() {
  uint8_t k[20];
  memset(k, 0x0b, 20);
  hmacCase(k, 20, (const uint8_t *)"Hi There", 8,
           "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7");
}

void test_rfc4231_case2() {
  const char *m = "what do ya want for nothing?";
  hmacCase((const uint8_t *)"Jefe", 4, (const uint8_t *)m, strlen(m),
           "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843");
}

void test_rfc4231_case3() {
  uint8_t k[20], m[50];
  memset(k, 0xaa, 20);
  memset(m, 0xdd, 50);
  hmacCase(k, 20, m, 50, "773ea91e36800e46854db8ebd09181a72959098b3ef8c122d9635514ced565fe");
}

void test_rfc4231_case4() {
  uint8_t k[25], m[50];
  for (int i = 0; i < 25; i++) k[i] = (uint8_t)(i + 1);
  memset(m, 0xcd, 50);
  hmacCase(k, 25, m, 50, "82558a389a443c0ea4cc819899f2083a85f0faa3e578f8077a2e3ff46729665b");
}

void test_rfc4231_case5_truncated() {
  uint8_t k[20];
  memset(k, 0x0c, 20);
  hmacCase(k, 20, (const uint8_t *)"Test With Truncation", 20, "a3b6167473100ee06e0c796c2955552b", 16);
}

void test_rfc4231_case6_long_key() {
  uint8_t k[131];
  memset(k, 0xaa, sizeof(k));
  const char *m = "Test Using Larger Than Block-Size Key - Hash Key First";
  hmacCase(k, sizeof(k), (const uint8_t *)m, strlen(m),
           "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54");
}

void test_rfc4231_case7_long_key_and_data() {
  uint8_t k[131];
  memset(k, 0xaa, sizeof(k));
  const char *m =
      "This is a test using a larger than block-size key and a larger than block-size data. The key needs to "
      "be hashed before being used by the HMAC algorithm.";
  hmacCase(k, sizeof(k), (const uint8_t *)m, strlen(m),
           "9b09ffa71b942fcb27635fbcd5b0e944bfdc63644f0713938a7f51535c3a35e2");
}

void test_ct_equal() {
  uint8_t a[4] = {1, 2, 3, 4}, b[4] = {1, 2, 3, 4};
  TEST_ASSERT_TRUE(ctEqual(a, b, 4));
  b[3] = 5;
  TEST_ASSERT_FALSE(ctEqual(a, b, 4));
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_sha256_empty);
  RUN_TEST(test_sha256_abc);
  RUN_TEST(test_sha256_two_blocks);
  RUN_TEST(test_sha256_million_a_chunked);
  RUN_TEST(test_sha256_odd_chunks_match_oneshot);
  RUN_TEST(test_rfc4231_case1);
  RUN_TEST(test_rfc4231_case2);
  RUN_TEST(test_rfc4231_case3);
  RUN_TEST(test_rfc4231_case4);
  RUN_TEST(test_rfc4231_case5_truncated);
  RUN_TEST(test_rfc4231_case6_long_key);
  RUN_TEST(test_rfc4231_case7_long_key_and_data);
  RUN_TEST(test_ct_equal);
  return UNITY_END();
}
