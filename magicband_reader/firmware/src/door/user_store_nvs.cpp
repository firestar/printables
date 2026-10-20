#include "user_store_nvs.h"

#include <Arduino.h>

using namespace mb;

static const uint32_t LAYOUT = 0x4D420000u | sizeof(User);  // bump on struct changes

void NvsUserStore::keyOf(int slot, char *k) { snprintf(k, 8, "u%d", slot); }

void NvsUserStore::begin() {
  prefs_.begin("mbusers", false);
  if (prefs_.getUInt("layout", 0) != LAYOUT) {
    if (prefs_.isKey("layout")) log_e("user store layout changed: users cleared");
    prefs_.clear();
    prefs_.putUInt("layout", LAYOUT);
  }
  char k[8];
  for (int i = 0; i < MAX_USERS; i++) {
    keyOf(i, k);
    User u;
    if (prefs_.getBytesLength(k) == sizeof(User) && prefs_.getBytes(k, &u, sizeof(User)) == sizeof(User)) {
      u.name[NAME_LEN - 1] = 0;
      MemoryUserStore::save(i, u);
    }
  }
}

bool NvsUserStore::save(int slot, const User &u) {
  if (!MemoryUserStore::save(slot, u)) return false;
  char k[8];
  keyOf(slot, k);
  return prefs_.putBytes(k, &u, sizeof(User)) == sizeof(User);
}

bool NvsUserStore::erase(int slot) {
  if (!MemoryUserStore::erase(slot)) return false;
  char k[8];
  keyOf(slot, k);
  prefs_.remove(k);
  return true;
}

void NvsUserStore::wipe() {
  for (int i = 0; i < MAX_USERS; i++) erase(i);
}
