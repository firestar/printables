#pragma once
// RS-485 transport for the secure link (both boards): NVS-backed counters,
// half-duplex DE control, listen-before-talk and a small receive queue.

#include <Arduino.h>
#include <Preferences.h>

#include "mb_protocol.h"

// Counters in NVS namespace "mblink".  A different key (fingerprint stored
// next to the counters) wipes them, so re-provisioning starts from zero.
class NvsCounterStore : public mb::CounterStore {
 public:
  void begin(const uint8_t key[mb::KEY_LEN]);
  bool load(const char *key, uint32_t &v) override;
  void save(const char *key, uint32_t v) override;

 private:
  Preferences prefs_;
};

bool parseKeyHex(const char *hex, uint8_t out[mb::KEY_LEN]);

class LinkPort {
 public:
  explicit LinkPort(uint8_t self);
  void begin(HardwareSerial &serial, int rxPin, int txPin, int dePin, uint32_t baud);
  // Returns true and fills `out` for each fresh, authentic frame from the peer.
  bool poll(mb::Frame &out);
  bool send(uint8_t type, const uint8_t *payload = nullptr, size_t len = 0);
  bool peerOnline() const;
  uint32_t lastValidMs() const { return lastValid_; }
  uint32_t rxLast() const { return link_.rxLast(); }
  // Rejected frames since boot: bad tag + replay + out of window + reflected.
  uint32_t rejected() const;

 private:
  bool pumpOne(mb::Frame &out);
  uint8_t key_[mb::KEY_LEN];
  NvsCounterStore store_;
  mb::SecureLink link_;
  HardwareSerial *s_ = nullptr;
  int de_ = -1;
  uint32_t lastRxByte_ = 0, lastValid_ = 0;
  bool everValid_ = false;
  static const int QLEN = 4;
  mb::Frame q_[QLEN];
  int qn_ = 0;
};
