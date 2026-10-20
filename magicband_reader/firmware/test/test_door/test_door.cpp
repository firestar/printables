// Door decision core (controller + all-in-one reader) and HELLO capability
// negotiation driving it.  Run: pio test -e native

#include <string.h>
#include <unity.h>

#include "mb_door.h"
#include "mb_protocol.h"

using namespace mb;

void setUp() {}
void tearDown() {}

static Uid uid(uint8_t a, uint8_t len = 7) {
  uint8_t b[10];
  for (int i = 0; i < 10; i++) b[i] = (uint8_t)(a + i);
  return Uid::make(b, len);
}

// 0 = Alice band+finger (band A0, finger 1), 1 = Bob band-only (band B0),
// 2 = Cara finger-only (band C0, finger 7).
struct Door {
  MemoryUserStore users;
  DoorCore core{users};
  Door() {
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
    core.setConfig(DoorConfig(), AccessConfig(), EnrollConfig());
  }
};

static void expectFeedback(const DoorAction &a, uint8_t state) {
  TEST_ASSERT_TRUE(a.feedback);
  TEST_ASSERT_EQUAL_STRING(feedbackName(state), feedbackName(a.fbState));
}

static void expectLog(const DoorAction &a, uint8_t kind, Outcome o, Reason r, int slot) {
  TEST_ASSERT_TRUE(a.log);
  TEST_ASSERT_EQUAL_STRING(eventKindName(kind), eventKindName(a.kind));
  TEST_ASSERT_EQUAL_STRING(outcomeName(o), outcomeName(a.decision.outcome));
  TEST_ASSERT_EQUAL_STRING(reasonName(r), reasonName(a.decision.reason));
  TEST_ASSERT_EQUAL_INT(slot, a.decision.slot);
}

// What the controller / AIO does with a reader HELLO.
static void applyHello(DoorCore &core, uint8_t caps) {
  Hello h;
  h.caps = caps;
  uint8_t p[MAX_PAYLOAD];
  Frame f;
  f.type = MSG_HELLO;
  f.len = (uint8_t)packHello(h, p);
  memcpy(f.payload, p, f.len);
  Hello got;
  TEST_ASSERT_TRUE(unpackHello(f, got));
  core.setFingerHw(got.caps & CAP_FINGERPRINT);
}

// ---- local decision path (what the all-in-one runs) ----------------------------------------
void test_band_only_unlocks_with_granted_feedback() {
  Door d;
  DoorAction a = d.core.band(uid(0xB0, 4), 1000);
  TEST_ASSERT_TRUE(a.unlock);
  expectFeedback(a, FB_GRANTED);
  TEST_ASSERT_EQUAL_UINT32(1500, a.fbHoldMs);
  expectLog(a, EV_BAND, OUT_GRANT, WHY_OK, 1);
  TEST_ASSERT_TRUE(a.uid == uid(0xB0, 4));
}

void test_band_then_finger_unlocks() {
  Door d;
  DoorAction a = d.core.band(uid(0xA0), 1000);
  TEST_ASSERT_FALSE(a.unlock);
  expectFeedback(a, FB_NEED_FINGER);
  TEST_ASSERT_EQUAL_UINT32(8000, a.fbHoldMs);
  a = d.core.finger(1, 2000);
  TEST_ASSERT_TRUE(a.unlock);
  expectLog(a, EV_FINGER, OUT_GRANT, WHY_OK, 0);
  TEST_ASSERT_EQUAL_UINT16(1, a.page);
}

void test_finger_window_timeout_from_tick() {
  Door d;
  d.core.band(uid(0xA0), 1000);
  TEST_ASSERT_FALSE(d.core.tick(5000).log);
  DoorAction a = d.core.tick(9000);
  TEST_ASSERT_FALSE(a.unlock);
  expectFeedback(a, FB_DENIED);
  expectLog(a, EV_TIMEOUT, OUT_DENY, WHY_TIMEOUT, 0);
}

void test_unknown_band_denied_and_lockout_feedback() {
  Door d;
  DoorAction a;
  for (int i = 0; i < 5; i++) a = d.core.band(uid(0x55), 1000);
  TEST_ASSERT_FALSE(a.unlock);
  expectFeedback(a, FB_LOCKOUT);
  TEST_ASSERT_EQUAL_UINT32(30000, a.fbHoldMs);
}

void test_tamper_denies_scans_but_not_rex() {
  Door d;
  d.core.setTampered(true);
  DoorAction a = d.core.band(uid(0xB0, 4), 1000);
  TEST_ASSERT_FALSE(a.unlock);
  expectLog(a, EV_BAND, OUT_DENY, WHY_TAMPER, -1);
  a = d.core.finger(7, 1000);
  expectLog(a, EV_FINGER, OUT_DENY, WHY_TAMPER, -1);
  a = d.core.rex();
  TEST_ASSERT_TRUE(a.unlock);
  TEST_ASSERT_FALSE(a.feedback);
  expectLog(a, EV_REX, OUT_GRANT, WHY_OK, -1);
  a = d.core.remoteUnlock();
  TEST_ASSERT_TRUE(a.unlock);
  expectFeedback(a, FB_GRANTED);
  expectLog(a, EV_REMOTE, OUT_GRANT, WHY_OK, -1);
}

void test_enroll_band_and_finger_locally() {
  Door d;
  DoorAction a = d.core.startEnrollBand(-1, "Eve", 0);
  TEST_ASSERT_EQUAL_STRING("waiting_band", a.enrollStatus);
  expectFeedback(a, FB_ENROLL_BAND);
  a = d.core.band(uid(0xE0), 100);
  TEST_ASSERT_FALSE(a.unlock);  // enrollment never opens the door
  TEST_ASSERT_EQUAL(ENR_USER_CREATED, a.enroll.event);
  TEST_ASSERT_EQUAL_STRING("user_created", a.enrollStatus);
  expectFeedback(a, FB_ENROLL_OK);
  int slot = a.enroll.slot;
  a = d.core.startEnrollFinger(slot, 200);
  TEST_ASSERT_EQUAL_STRING("waiting_finger", a.enrollStatus);
  TEST_ASSERT_TRUE(a.enrollFingerPage >= 0);
  uint16_t page = (uint16_t)a.enrollFingerPage;
  TEST_ASSERT_TRUE(d.core.finger(1, 300).resendFeedback);  // finger events during enroll: ack only
  a = d.core.enrollResult(page, ENROLL_OK, 5000);
  TEST_ASSERT_EQUAL(ENR_FINGER_ADDED, a.enroll.event);
  TEST_ASSERT_EQUAL_INT(slot, d.users.findByFinger(page));
}

void test_stale_enroll_result_deletes_orphan_template() {
  Door d;
  DoorAction a = d.core.enrollResult(42, ENROLL_OK, 1000);  // nothing pending
  TEST_ASSERT_EQUAL_INT(42, a.deleteFingerPage);
  expectFeedback(a, FB_IDLE);
  a = d.core.enrollResult(1, ENROLL_OK, 1000);  // page 1 is Alice's: keep it
  TEST_ASSERT_EQUAL_INT(-1, a.deleteFingerPage);
}

// ---- capability negotiation -> no-FP rules --------------------------------------------------
void test_hello_caps_drive_finger_hw() {
  Door d;
  applyHello(d.core, CAP_NFC);  // reader_nofp
  TEST_ASSERT_FALSE(d.core.fingerHw());
  TEST_ASSERT_TRUE(d.core.fingerProblem());
  applyHello(d.core, CAP_NFC | CAP_FINGERPRINT);  // reader
  TEST_ASSERT_TRUE(d.core.fingerHw());
  TEST_ASSERT_FALSE(d.core.fingerProblem());
}

void test_no_fp_deny_rule_per_policy() {
  Door d;
  applyHello(d.core, CAP_NFC);
  DoorAction a = d.core.band(uid(0xB0, 4), 1000);  // BAND_ONLY
  TEST_ASSERT_TRUE(a.unlock);
  expectLog(a, EV_BAND, OUT_GRANT, WHY_OK, 1);
  a = d.core.band(uid(0xA0), 2000);  // BAND_AND_FINGER: not downgraded
  TEST_ASSERT_FALSE(a.unlock);
  expectFeedback(a, FB_DENIED);
  expectLog(a, EV_BAND, OUT_DENY, WHY_NO_FP_HW, 0);
  TEST_ASSERT_FALSE(d.core.engine().pending());
  a = d.core.band(uid(0xC0), 3000);  // FINGER_ONLY
  TEST_ASSERT_FALSE(a.unlock);
  expectLog(a, EV_BAND, OUT_DENY, WHY_NO_FP_HW, 2);
  a = d.core.finger(7, 4000);  // a finger event despite no capability
  TEST_ASSERT_FALSE(a.unlock);
  expectLog(a, EV_FINGER, OUT_DENY, WHY_NO_FP_HW, -1);
  TEST_ASSERT_EQUAL_UINT8(0, d.core.engine().failures());
}

void test_no_fp_enroll_finger_rejected() {
  Door d;
  applyHello(d.core, CAP_NFC);
  DoorAction a = d.core.startEnrollFinger(1, 0);
  TEST_ASSERT_EQUAL_STRING("no_fingerprint_hw", a.enrollStatus);
  TEST_ASSERT_EQUAL_INT(-1, a.enrollFingerPage);  // nothing sent to the reader
  expectFeedback(a, FB_ENROLL_FAIL);
  TEST_ASSERT_FALSE(d.core.enrollFlow().active());
  // new users default to band-only on such a reader
  d.core.startEnrollBand(-1, "Hal", 10);
  a = d.core.band(uid(0x70), 20);
  User u;
  TEST_ASSERT_TRUE(d.users.load(a.enroll.slot, u));
  TEST_ASSERT_EQUAL_UINT8(POLICY_BAND_ONLY, u.policy);
  TEST_ASSERT_TRUE(d.core.band(uid(0x70), 30).unlock);
}

void test_fp_lost_during_finger_enroll() {
  Door d;
  DoorAction a = d.core.startEnrollFinger(1, 0);
  TEST_ASSERT_TRUE(a.enrollFingerPage >= 0);
  a = d.core.setFingerHw(false);  // reader swapped for a nofp one
  TEST_ASSERT_EQUAL_STRING("no_fingerprint_hw", a.enrollStatus);
  TEST_ASSERT_FALSE(d.core.enrollFlow().active());
  TEST_ASSERT_EQUAL(FB_IDLE, d.core.restingFeedback());
}

int main(int, char **) {
  UNITY_BEGIN();
  RUN_TEST(test_band_only_unlocks_with_granted_feedback);
  RUN_TEST(test_band_then_finger_unlocks);
  RUN_TEST(test_finger_window_timeout_from_tick);
  RUN_TEST(test_unknown_band_denied_and_lockout_feedback);
  RUN_TEST(test_tamper_denies_scans_but_not_rex);
  RUN_TEST(test_enroll_band_and_finger_locally);
  RUN_TEST(test_stale_enroll_result_deletes_orphan_template);
  RUN_TEST(test_hello_caps_drive_finger_hw);
  RUN_TEST(test_no_fp_deny_rule_per_policy);
  RUN_TEST(test_no_fp_enroll_finger_rejected);
  RUN_TEST(test_fp_lost_during_finger_enroll);
  return UNITY_END();
}
