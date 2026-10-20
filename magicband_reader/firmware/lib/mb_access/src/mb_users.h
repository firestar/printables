#pragma once
// Users and the allowlist.  UserStore is the storage interface: the
// controller uses an NVS (Preferences) implementation, tests use
// MemoryUserStore.  Slots are stable user ids.  No Arduino headers.

#include <stddef.h>
#include <stdint.h>

namespace mb {

static const int MAX_USERS = 16;
static const int MAX_BANDS = 4;    // per user
static const int MAX_FINGERS = 4;  // per user
static const int NAME_LEN = 24;    // including the terminating 0
static const size_t UID_BYTES = 10;
static const uint16_t FINGER_PAGES = 200;  // R503 template capacity

enum Policy : uint8_t { POLICY_BAND_ONLY = 0, POLICY_BAND_AND_FINGER = 1, POLICY_FINGER_ONLY = 2 };

struct Uid {
  uint8_t len = 0;
  uint8_t b[UID_BYTES] = {0};
  bool operator==(const Uid &o) const;
  bool valid() const { return len >= 4 && len <= UID_BYTES; }
  // Upper-case hex, "04A1B2C3D4E5F6"; `out` needs 2*len+1 bytes.
  void toHex(char *out) const;
  static Uid make(const uint8_t *p, size_t n);
};

// Plain-old-data so it can be stored as one NVS blob.
struct User {
  char name[NAME_LEN] = {0};
  uint8_t policy = POLICY_BAND_AND_FINGER;
  uint8_t enabled = 1;
  uint8_t nBands = 0;
  uint8_t nFingers = 0;
  Uid bands[MAX_BANDS];
  uint16_t fingers[MAX_FINGERS] = {0};

  void setName(const char *n);
  bool hasBand(const Uid &u) const;
  bool hasFinger(uint16_t page) const;
};

const char *policyName(uint8_t p);
// Parses "band_only" / "band_and_finger" / "finger_only"; -1 if unknown.
int parsePolicy(const char *s);

class UserStore {
 public:
  virtual ~UserStore() {}
  virtual bool load(int slot, User &u) const = 0;  // false = empty slot
  virtual bool save(int slot, const User &u) = 0;
  virtual bool erase(int slot) = 0;

  // Helpers built on the three calls above.  Return -1 when not found.
  int findByUid(const Uid &uid) const;
  int findByFinger(uint16_t page) const;
  int findByName(const char *name) const;
  int freeSlot() const;
  int count() const;
  // Lowest R503 page id not bound to any user, -1 if full.
  int freeFingerPage(uint16_t pages = FINGER_PAGES) const;
  bool addBand(int slot, const Uid &uid);
  bool addFinger(int slot, uint16_t page);
};

class MemoryUserStore : public UserStore {
 public:
  bool load(int slot, User &u) const override;
  bool save(int slot, const User &u) override;
  bool erase(int slot) override;

 protected:
  bool used_[MAX_USERS] = {false};
  User users_[MAX_USERS];
};

}  // namespace mb
