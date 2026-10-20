#include "mb_users.h"

#include <string.h>

namespace mb {

bool Uid::operator==(const Uid &o) const { return len == o.len && memcmp(b, o.b, len) == 0; }

void Uid::toHex(char *out) const {
  static const char H[] = "0123456789ABCDEF";
  for (uint8_t i = 0; i < len; i++) {
    out[2 * i] = H[b[i] >> 4];
    out[2 * i + 1] = H[b[i] & 15];
  }
  out[2 * len] = 0;
}

Uid Uid::make(const uint8_t *p, size_t n) {
  Uid u;
  if (n > UID_BYTES) n = UID_BYTES;
  u.len = (uint8_t)n;
  memcpy(u.b, p, n);
  return u;
}

void User::setName(const char *n) {
  strncpy(name, n ? n : "", NAME_LEN - 1);
  name[NAME_LEN - 1] = 0;
}

bool User::hasBand(const Uid &u) const {
  for (uint8_t i = 0; i < nBands && i < MAX_BANDS; i++)
    if (bands[i] == u) return true;
  return false;
}

bool User::hasFinger(uint16_t page) const {
  for (uint8_t i = 0; i < nFingers && i < MAX_FINGERS; i++)
    if (fingers[i] == page) return true;
  return false;
}

const char *policyName(uint8_t p) {
  switch (p) {
    case POLICY_BAND_ONLY: return "band_only";
    case POLICY_BAND_AND_FINGER: return "band_and_finger";
    case POLICY_FINGER_ONLY: return "finger_only";
  }
  return "?";
}

int parsePolicy(const char *s) {
  for (int p = 0; p <= POLICY_FINGER_ONLY; p++)
    if (s && strcmp(s, policyName((uint8_t)p)) == 0) return p;
  return -1;
}

int UserStore::findByUid(const Uid &uid) const {
  User u;
  for (int i = 0; i < MAX_USERS; i++)
    if (load(i, u) && u.hasBand(uid)) return i;
  return -1;
}

int UserStore::findByFinger(uint16_t page) const {
  User u;
  for (int i = 0; i < MAX_USERS; i++)
    if (load(i, u) && u.hasFinger(page)) return i;
  return -1;
}

int UserStore::findByName(const char *name) const {
  User u;
  for (int i = 0; i < MAX_USERS; i++)
    if (load(i, u) && strncmp(u.name, name, NAME_LEN) == 0) return i;
  return -1;
}

int UserStore::freeSlot() const {
  User u;
  for (int i = 0; i < MAX_USERS; i++)
    if (!load(i, u)) return i;
  return -1;
}

int UserStore::count() const {
  User u;
  int n = 0;
  for (int i = 0; i < MAX_USERS; i++)
    if (load(i, u)) n++;
  return n;
}

int UserStore::freeFingerPage(uint16_t pages) const {
  for (uint16_t p = 0; p < pages; p++)
    if (findByFinger(p) < 0) return p;
  return -1;
}

bool UserStore::addBand(int slot, const Uid &uid) {
  User u;
  if (!uid.valid() || !load(slot, u) || u.hasBand(uid) || u.nBands >= MAX_BANDS) return false;
  if (findByUid(uid) >= 0) return false;  // a band belongs to one user only
  u.bands[u.nBands++] = uid;
  return save(slot, u);
}

bool UserStore::addFinger(int slot, uint16_t page) {
  User u;
  if (!load(slot, u) || u.nFingers >= MAX_FINGERS || findByFinger(page) >= 0) return false;
  u.fingers[u.nFingers++] = page;
  return save(slot, u);
}

bool MemoryUserStore::load(int slot, User &u) const {
  if (slot < 0 || slot >= MAX_USERS || !used_[slot]) return false;
  u = users_[slot];
  return true;
}

bool MemoryUserStore::save(int slot, const User &u) {
  if (slot < 0 || slot >= MAX_USERS) return false;
  users_[slot] = u;
  used_[slot] = true;
  return true;
}

bool MemoryUserStore::erase(int slot) {
  if (slot < 0 || slot >= MAX_USERS) return false;
  used_[slot] = false;
  users_[slot] = User();
  return true;
}

}  // namespace mb
