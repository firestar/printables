#pragma once
// UserStore persisted in NVS (namespace "mbusers", one blob per slot) with
// an in-RAM copy, so lookups during a scan never touch flash.

#include <Preferences.h>

#include "mb_users.h"

class NvsUserStore : public mb::MemoryUserStore {
 public:
  void begin();
  bool save(int slot, const mb::User &u) override;
  bool erase(int slot) override;
  void wipe();  // delete every user

 private:
  static void keyOf(int slot, char *k);
  Preferences prefs_;
};
