// Access policy engine, enrollment flow, user store and event log.
// Run: pio test -e native

#include <string.h>
#include <unity.h>

#include "mb_access.h"

using namespace mb;

void setUp() {}
void tearDown() {}

static Uid uid(uint8_t a, uint8_t len = 7) {
  uint8_t b[10];
  for (int i = 0; i < 10; i++) b[i] = (uint8_t)(a + i);
  return Uid::make(b, len);
}

// Store with: 0 = Alice band+finger (band A, finger 1), 1 = Bob band-only
// (band B), 2 = Cara finger-only (finger 7), 3 = Dan disabled (band D, finger 9).
struct Fixture {
  MemoryUserStore users;
  AccessEngine eng{users};
  Fixture() {
    User a;
    a.setName("Alice");
    a.policy = POLICY_BAND_AND_FINGER;
    a.bands[a.nBands++] = uid(0xA0);
    a.fingers[a.nFingers++] = 1;
    users.save(0, a);
    User b;
    b.setName("Bob");
    b.policy = POLICY_BAND_ONLY;
    b.bands[b.nBands++] = uid(0xB0, 4);
    users.save(1, b);
    User c;
    c.setName("Cara");
    c.policy = POLICY_FINGER_ONLY;
    c.bands[c.nBands++] = uid(0xC0);
    c.fingers[c.nFingers++] = 7;
    users.save(2, c);
    User d;
    d.setName("Dan");
    d.policy = POLICY_BAND_ONLY;
    d.enabled = 0;
    d.bands[d.nBands++] = uid(0xD0);
    d.fingers[d.nFingers++] = 9;
    users.save(3, d);
  }
};

static void expect(const Decision &d, Outcome o, Reason r, int slot) {
  TEST_ASSERT_EQUAL_STRING(outcomeName(o), outcomeName(d.outcome));
  TEST_ASSERT_EQUAL_STRING(reasonName(r), reasonName(d.reason));
  TEST_ASSERT_EQUAL_INT(slot, d.slot);
}

// ---- policies -------------------------------------------------------------------------
void test_band_only_grants() {
  Fixture f;
  expect(f.eng.onBand(uid(0xB0, 4), 1000), OUT_GRANT, WHY_OK, 1);
  TEST_ASSERT_FALSE(f.eng.pending());
}

void test_band_and_finger_grants_with_own_finger() {
  Fixture f;
  expect(f.eng.onBand(uid(0xA0), 1000), OUT_NEED_FINGER, WHY_OK, 0);
  TEST_ASSERT_TRUE(f.eng.pending());
  expect(f.eng.onFinger(1, 3000), OUT_GRANT, WHY_OK, 0);
  TEST_ASSERT_FALSE(f.eng.pending());
}

void test_band_and_finger_rejects_wrong_users_finger() {
  Fixture f;
  f.eng.onBand(uid(0xA0), 1000);
  expect(f.eng.onFinger(7, 2000), OUT_DENY, WHY_WRONG_USER, 0);  // Cara's finger after Alice's band
  TEST_ASSERT_FALSE(f.eng.pending());
  expect(f.eng.onFinger(1, 2500), OUT_DENY, WHY_POLICY, 0);  // window closed: Alice's finger alone
}

void test_band_and_finger_times_out() {
  Fixture f;
  f.eng.onBand(uid(0xA0), 1000);
  expect(f.eng.tick(8999), OUT_NONE, WHY_OK, -1);
  expect(f.eng.tick(9000), OUT_DENY, WHY_TIMEOUT, 0);
  TEST_ASSERT_FALSE(f.eng.pending());
}

void test_finger_after_deadline_is_timeout_not_grant() {
  Fixture f;
  f.eng.onBand(uid(0xA0), 1000);
  expect(f.eng.onFinger(1, 9500), OUT_DENY, WHY_TIMEOUT, 0);  // tick() was not called in between
}

void test_band_and_finger_nomatch_allows_retry() {
  Fixture f;
  f.eng.onBand(uid(0xA0), 1000);
  expect(f.eng.onFingerNoMatch(2000), OUT_NEED_FINGER, WHY_RETRY, 0);
  TEST_ASSERT_TRUE(f.eng.pending());
  expect(f.eng.onFinger(1, 3000), OUT_GRANT, WHY_OK, 0);
}

void test_finger_only_grants_and_band_does_not() {
  Fixture f;
  expect(f.eng.onFinger(7, 1000), OUT_GRANT, WHY_OK, 2);
  expect(f.eng.onBand(uid(0xC0), 2000), OUT_DENY, WHY_POLICY, 2);
  TEST_ASSERT_EQUAL_UINT8(0, f.eng.failures());  // a valid credential is not a failure
}

void test_finger_alone_for_band_and_finger_user_denied() {
  Fixture f;
  expect(f.eng.onFinger(1, 1000), OUT_DENY, WHY_POLICY, 0);
}

void test_unknown_band_and_finger() {
  Fixture f;
  expect(f.eng.onBand(uid(0x55), 1000), OUT_DENY, WHY_UNKNOWN_BAND, -1);
  expect(f.eng.onFinger(150, 1000), OUT_DENY, WHY_UNKNOWN_FINGER, -1);
  expect(f.eng.onFingerNoMatch(1000), OUT_DENY, WHY_NO_MATCH, -1);
  TEST_ASSERT_EQUAL_UINT8(3, f.eng.failures());
}

void test_disabled_user_denied() {
  Fixture f;
  expect(f.eng.onBand(uid(0xD0), 1000), OUT_DENY, WHY_DISABLED, 3);
  expect(f.eng.onFinger(9, 1000), OUT_DENY, WHY_DISABLED, 3);
}

void test_same_uid_bytes_different_length_is_unknown() {
  Fixture f;
  expect(f.eng.onBand(uid(0xB0, 7), 1000), OUT_DENY, WHY_UNKNOWN_BAND, -1);
}

// ---- lockout -------------------------------------------------------------------------------
void test_lockout_after_failures_and_backoff() {
  Fixture f;  // 5 failures, 30 s first lockout
  for (int i = 0; i < 4; i++) expect(f.eng.onBand(uid(0x55), 1000 + i), OUT_DENY, WHY_UNKNOWN_BAND, -1);
  expect(f.eng.onBand(uid(0x55), 1004), OUT_LOCKED, WHY_UNKNOWN_BAND, -1);
  TEST_ASSERT_TRUE(f.eng.lockedOut(1005));
  // Even a valid band is refused while locked out.
  expect(f.eng.onBand(uid(0xB0, 4), 20000), OUT_LOCKED, WHY_LOCKOUT, -1);
  expect(f.eng.onFinger(7, 20000), OUT_LOCKED, WHY_LOCKOUT, -1);
  TEST_ASSERT_EQUAL_UINT32(30000 - (20000 - 1004), f.eng.lockoutRemaining(20000));
  f.eng.tick(31004);
  TEST_ASSERT_FALSE(f.eng.lockedOut(31004));
  // Second lockout doubles.
  for (int i = 0; i < 5; i++) f.eng.onBand(uid(0x55), 40000);
  TEST_ASSERT_EQUAL_UINT32(60000, f.eng.lockoutRemaining(40000));
}

void test_lockout_capped() {
  MemoryUserStore users;
  AccessConfig c;
  c.maxFailures = 1;
  c.lockoutMs = 1000;
  c.lockoutMaxMs = 5000;
  AccessEngine eng(users, c);
  uint32_t t = 0;
  for (int i = 0; i < 10; i++) {
    eng.onBand(uid(0x55), t);
    TEST_ASSERT_TRUE(eng.lockoutRemaining(t) <= 5000);
    t += eng.lockoutRemaining(t);
    eng.tick(t);
  }
  eng.onBand(uid(0x55), t);
  TEST_ASSERT_EQUAL_UINT32(5000, eng.lockoutRemaining(t));
}

void test_success_resets_failures() {
  Fixture f;
  for (int i = 0; i < 4; i++) f.eng.onBand(uid(0x55), 1000);
  f.eng.onBand(uid(0xB0, 4), 1000);
  TEST_ASSERT_EQUAL_UINT8(0, f.eng.failures());
  for (int i = 0; i < 4; i++) expect(f.eng.onBand(uid(0x55), 1000), OUT_DENY, WHY_UNKNOWN_BAND, -1);
}

void test_nomatch_retries_count_toward_lockout() {
  Fixture f;
  f.eng.onBand(uid(0xA0), 1000);
  for (int i = 0; i < 4; i++) expect(f.eng.onFingerNoMatch(1100 + i), OUT_NEED_FINGER, WHY_RETRY, 0);
  expect(f.eng.onFingerNoMatch(1200), OUT_LOCKED, WHY_NO_MATCH, 0);
  TEST_ASSERT_FALSE(f.eng.pending());
}

void test_clock_wraparound() {
  Fixture f;
  uint32_t t = 0xFFFFF000u;
  f.eng.onBand(uid(0xA0), t);
  expect(f.eng.tick(t + 7999), OUT_NONE, WHY_OK, -1);  // crosses 2^32
  expect(f.eng.onFinger(1, t + 7999), OUT_GRANT, WHY_OK, 0);
}

// ---- no fingerprint hardware (reader_nofp / reader_aio_nofp) ---------------------------------
void test_no_fp_band_only_still_grants() {
  Fixture f;
  f.eng.setFingerHw(false);
  expect(f.eng.onBand(uid(0xB0, 4), 1000), OUT_GRANT, WHY_OK, 1);
}

void test_no_fp_band_and_finger_denied_not_downgraded() {
  Fixture f;
  f.eng.setFingerHw(false);
  expect(f.eng.onBand(uid(0xA0), 1000), OUT_DENY, WHY_NO_FP_HW, 0);  // never band-only
  TEST_ASSERT_FALSE(f.eng.pending());
  TEST_ASSERT_EQUAL_UINT8(0, f.eng.failures());  // a config problem, not a failed attempt
  TEST_ASSERT_EQUAL_STRING("no_fp_hw", reasonName(WHY_NO_FP_HW));
}

void test_no_fp_finger_only_denied() {
  Fixture f;
  f.eng.setFingerHw(false);
  expect(f.eng.onBand(uid(0xC0), 1000), OUT_DENY, WHY_NO_FP_HW, 2);
  expect(f.eng.onFinger(7, 1000), OUT_DENY, WHY_NO_FP_HW, -1);  // forged/unexpected finger event
  expect(f.eng.onFingerNoMatch(1000), OUT_DENY, WHY_NO_FP_HW, -1);
  TEST_ASSERT_EQUAL_UINT8(0, f.eng.failures());
}

void test_no_fp_disabled_and_unknown_unchanged() {
  Fixture f;
  f.eng.setFingerHw(false);
  expect(f.eng.onBand(uid(0xD0), 1000), OUT_DENY, WHY_DISABLED, 3);
  expect(f.eng.onBand(uid(0x55), 1000), OUT_DENY, WHY_UNKNOWN_BAND, -1);
  TEST_ASSERT_EQUAL_UINT8(2, f.eng.failures());
}

void test_losing_fp_cancels_pending_and_flags_problem() {
  Fixture f;
  TEST_ASSERT_FALSE(f.eng.fingerProblem());
  f.eng.onBand(uid(0xA0), 1000);
  TEST_ASSERT_TRUE(f.eng.pending());
  f.eng.setFingerHw(false);
  TEST_ASSERT_FALSE(f.eng.pending());
  TEST_ASSERT_TRUE(f.eng.fingerProblem());  // Alice and Cara can't get in
  MemoryUserStore only;
  User b;
  b.policy = POLICY_BAND_ONLY;
  b.bands[b.nBands++] = uid(0xB0, 4);
  only.save(0, b);
  AccessEngine eng(only);
  eng.setFingerHw(false);
  TEST_ASSERT_FALSE(eng.fingerProblem());  // band-only users only: nothing to warn about
}

void test_no_fp_enroll_finger_rejected_and_band_only_default() {
  Fixture f;
  EnrollFlow e(f.users);
  e.setFingerHw(false);
  TEST_ASSERT_EQUAL_INT(ENROLL_START_NO_FP, e.startFinger(1, 0));
  TEST_ASSERT_FALSE(e.active());
  e.startNewUser("Hal", 0);
  EnrollResultEv r = e.onBand(uid(0x70), 10);
  TEST_ASSERT_EQUAL(ENR_USER_CREATED, r.event);
  User u;
  f.users.load(r.slot, u);
  TEST_ASSERT_EQUAL_UINT8(POLICY_BAND_ONLY, u.policy);  // band+finger could never be satisfied
  e.setFingerHw(true);
  TEST_ASSERT_TRUE(e.startFinger(1, 20) >= 0);
  e.setFingerHw(false);  // sensor gone mid-enrollment
  TEST_ASSERT_FALSE(e.active());
}

// ---- enrollment ------------------------------------------------------------------------------
void test_enroll_new_user_with_next_band() {
  MemoryUserStore users;
  EnrollFlow e(users);
  TEST_ASSERT_TRUE(e.startNewUser("Eve", 0));
  TEST_ASSERT_EQUAL(ENR_WAIT_BAND, e.state());
  EnrollResultEv r = e.onBand(uid(0xE0), 1000);
  TEST_ASSERT_EQUAL(ENR_USER_CREATED, r.event);
  TEST_ASSERT_FALSE(e.active());
  User u;
  TEST_ASSERT_TRUE(users.load(r.slot, u));
  TEST_ASSERT_EQUAL_STRING("Eve", u.name);
  TEST_ASSERT_EQUAL_UINT8(POLICY_BAND_AND_FINGER, u.policy);
  TEST_ASSERT_EQUAL_INT(r.slot, users.findByUid(uid(0xE0)));
}

void test_enroll_default_name_and_known_band() {
  Fixture f;
  EnrollFlow e(f.users);
  e.startNewUser("", 0);
  EnrollResultEv r = e.onBand(uid(0xA0), 10);  // Alice's band
  TEST_ASSERT_EQUAL(ENR_BAND_KNOWN, r.event);
  TEST_ASSERT_EQUAL_INT(0, r.slot);
  TEST_ASSERT_EQUAL_INT(4, f.users.count());
  e.startNewUser("", 20);
  r = e.onBand(uid(0xF0), 30);
  TEST_ASSERT_EQUAL(ENR_USER_CREATED, r.event);
  User u;
  f.users.load(r.slot, u);
  TEST_ASSERT_EQUAL_STRING("User 5", u.name);
}

void test_enroll_band_timeout() {
  MemoryUserStore users;
  EnrollFlow e(users);
  e.startNewUser("x", 0);
  TEST_ASSERT_EQUAL(ENR_NONE, e.tick(29999).event);
  TEST_ASSERT_EQUAL(ENR_TIMEOUT, e.tick(30000).event);
  TEST_ASSERT_FALSE(e.active());
  TEST_ASSERT_EQUAL(ENR_NONE, e.onBand(uid(0xE0), 30001).event);  // not consumed anymore
  TEST_ASSERT_EQUAL_INT(0, users.count());
}

void test_enroll_add_band_to_existing_user() {
  Fixture f;
  EnrollFlow e(f.users);
  TEST_ASSERT_TRUE(e.startAddBand(0, 0));
  EnrollResultEv r = e.onBand(uid(0x11), 100);
  TEST_ASSERT_EQUAL(ENR_BAND_ADDED, r.event);
  TEST_ASSERT_EQUAL_INT(0, f.users.findByUid(uid(0x11)));
}

void test_enroll_finger_binds_page() {
  Fixture f;
  EnrollFlow e(f.users);
  int page = e.startFinger(1, 0);  // Bob; pages 1, 7, 9 are taken
  TEST_ASSERT_EQUAL_INT(0, page);
  TEST_ASSERT_EQUAL(ENR_WAIT_FINGER, e.state());
  TEST_ASSERT_EQUAL(ENR_NONE, e.onBand(uid(0x55), 10).event);  // band scans ignored meanwhile
  TEST_ASSERT_EQUAL(ENR_NONE, e.onEnrollResult(5, 0, 20).event);  // wrong page ignored
  EnrollResultEv r = e.onEnrollResult(0, 0, 30);
  TEST_ASSERT_EQUAL(ENR_FINGER_ADDED, r.event);
  TEST_ASSERT_EQUAL_INT(1, f.users.findByFinger(0));
  TEST_ASSERT_EQUAL_INT(2, e.startFinger(1, 40));  // next free page skips 1
}

void test_enroll_finger_failure_and_timeout() {
  Fixture f;
  EnrollFlow e(f.users);
  int page = e.startFinger(0, 0);
  EnrollResultEv r = e.onEnrollResult((uint16_t)page, 2, 100);
  TEST_ASSERT_EQUAL(ENR_FINGER_FAILED, r.event);
  TEST_ASSERT_EQUAL_INT(-1, f.users.findByFinger((uint16_t)page));
  e.startFinger(0, 1000);
  TEST_ASSERT_EQUAL(ENR_TIMEOUT, e.tick(61000).event);
}

void test_enroll_store_full() {
  MemoryUserStore users;
  for (int i = 0; i < MAX_USERS; i++) {
    User u;
    u.bands[u.nBands++] = uid((uint8_t)(i * 10));
    users.save(i, u);
  }
  EnrollFlow e(users);
  TEST_ASSERT_FALSE(e.startNewUser("x", 0));
  User u;
  users.load(0, u);
  u.nFingers = MAX_FINGERS;
  users.save(0, u);
  TEST_ASSERT_EQUAL_INT(-1, e.startFinger(0, 0));
  TEST_ASSERT_EQUAL_INT(-1, e.startFinger(42, 0));
}

void test_enrolled_user_then_access() {
  MemoryUserStore users;
  EnrollFlow e(users);
  AccessEngine eng(users);
  e.startNewUser("Gus", 0);
  int slot = e.onBand(uid(0x60), 100).slot;
  int page = e.startFinger(slot, 200);
  e.onEnrollResult((uint16_t)page, 0, 5000);
  expect(eng.onBand(uid(0x60), 6000), OUT_NEED_FINGER, WHY_OK, slot);
  expect(eng.onFinger((uint16_t)page, 7000), OUT_GRANT, WHY_OK, slot);
}

// ---- store + log ------------------------------------------------------------------------------
void test_store_band_unique_across_users() {
  Fixture f;
  TEST_ASSERT_FALSE(f.users.addBand(1, uid(0xA0)));  // Alice's
  TEST_ASSERT_TRUE(f.users.addBand(1, uid(0x22)));
  TEST_ASSERT_FALSE(f.users.addBand(1, uid(0x22)));
  TEST_ASSERT_FALSE(f.users.addFinger(1, 7));  // Cara's page
  TEST_ASSERT_EQUAL_INT(0, f.users.findByName("Alice"));
  TEST_ASSERT_TRUE(f.users.erase(0));
  TEST_ASSERT_EQUAL_INT(-1, f.users.findByUid(uid(0xA0)));
}

void test_uid_hex_and_policy_names() {
  char hex[21];
  uint8_t b[4] = {0x04, 0xA1, 0x0F, 0xFF};
  Uid::make(b, 4).toHex(hex);
  TEST_ASSERT_EQUAL_STRING("04A10FFF", hex);
  TEST_ASSERT_EQUAL_INT(POLICY_FINGER_ONLY, parsePolicy("finger_only"));
  TEST_ASSERT_EQUAL_INT(-1, parsePolicy("nope"));
}

void test_event_log_ring() {
  EventLog log;
  for (int i = 0; i < EventLog::CAP + 5; i++) {
    LogEvent e;
    e.t = (uint32_t)i;
    log.add(e);
  }
  TEST_ASSERT_EQUAL_INT(EventLog::CAP, log.size());
  TEST_ASSERT_EQUAL_UINT32(5, log.at(0).t);
  TEST_ASSERT_EQUAL_UINT32(EventLog::CAP + 4, log.latest().t);
  TEST_ASSERT_EQUAL_UINT32(EventLog::CAP + 5, log.latest().seq);
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_band_only_grants);
  RUN_TEST(test_band_and_finger_grants_with_own_finger);
  RUN_TEST(test_band_and_finger_rejects_wrong_users_finger);
  RUN_TEST(test_band_and_finger_times_out);
  RUN_TEST(test_finger_after_deadline_is_timeout_not_grant);
  RUN_TEST(test_band_and_finger_nomatch_allows_retry);
  RUN_TEST(test_finger_only_grants_and_band_does_not);
  RUN_TEST(test_finger_alone_for_band_and_finger_user_denied);
  RUN_TEST(test_unknown_band_and_finger);
  RUN_TEST(test_disabled_user_denied);
  RUN_TEST(test_same_uid_bytes_different_length_is_unknown);
  RUN_TEST(test_lockout_after_failures_and_backoff);
  RUN_TEST(test_lockout_capped);
  RUN_TEST(test_success_resets_failures);
  RUN_TEST(test_nomatch_retries_count_toward_lockout);
  RUN_TEST(test_no_fp_band_only_still_grants);
  RUN_TEST(test_no_fp_band_and_finger_denied_not_downgraded);
  RUN_TEST(test_no_fp_finger_only_denied);
  RUN_TEST(test_no_fp_disabled_and_unknown_unchanged);
  RUN_TEST(test_losing_fp_cancels_pending_and_flags_problem);
  RUN_TEST(test_no_fp_enroll_finger_rejected_and_band_only_default);
  RUN_TEST(test_clock_wraparound);
  RUN_TEST(test_enroll_new_user_with_next_band);
  RUN_TEST(test_enroll_default_name_and_known_band);
  RUN_TEST(test_enroll_band_timeout);
  RUN_TEST(test_enroll_add_band_to_existing_user);
  RUN_TEST(test_enroll_finger_binds_page);
  RUN_TEST(test_enroll_finger_failure_and_timeout);
  RUN_TEST(test_enroll_store_full);
  RUN_TEST(test_enrolled_user_then_access);
  RUN_TEST(test_store_band_unique_across_users);
  RUN_TEST(test_uid_hex_and_policy_names);
  RUN_TEST(test_event_log_ring);
  return UNITY_END();
}
