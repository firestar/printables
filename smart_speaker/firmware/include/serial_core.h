#pragma once
// Hardware-free core of the USB serial link: settings model and validation,
// the newline-delimited JSON settings protocol, and the byte demultiplexer that
// separates Improv Serial packets from JSON lines on the shared UART.
//
// No Arduino includes in here or in serial_core.cpp, so tools/run_native_tests.py
// can build and run all of it with g++ on a PC.
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

#include "config.h"

namespace lumen {

// ---- settings model ---------------------------------------------------------
const size_t NAME_MAX_BYTES = 32;
const size_t TOKEN_MAX_BYTES = 64;
const uint16_t LED_COUNT_MIN = 1;
const uint16_t LED_COUNT_MAX = 300;
const int SCHEMA_VERSION = 1;

struct Settings {
  std::string name;
  std::string token;  // secret: never returned, logged or echoed in an error
  uint16_t ledCount;
  uint8_t ledMaxBrightness;
};

Settings defaultSettings(const std::string &defaultName);

// 1..NAME_MAX_BYTES bytes of valid UTF-8 without control characters.
bool isValidName(const char *s, size_t len);
// 0..TOKEN_MAX_BYTES bytes of valid UTF-8 without control characters.
bool isValidToken(const char *s, size_t len);
// Clamps a value read back from flash, which may predate these limits.
uint16_t sanitizeLedCount(uint32_t count);

// The highest brightness (0..255) that keeps `count` LEDs at full white inside
// LED_POWER_BUDGET_MA, never above `requestedMax`.
uint8_t powerCappedBrightness(uint16_t count, uint8_t requestedMax);

// Persistent storage, implemented over NVS on the device.
class SettingsStore {
 public:
  virtual ~SettingsStore() {}
  // Write `after`. On failure return false, with `before` still in effect.
  virtual bool save(const Settings &before, const Settings &after) = 0;
  // Clear all stored settings and the saved Wi-Fi network.
  virtual bool erase() = 0;
};

// ---- settings protocol ------------------------------------------------------
enum class LineAction : uint8_t {
  NONE,              // nothing to do beyond sending the reply
  SETTINGS_CHANGED,  // settings were updated: apply them to the running device
  RESTART,           // restart after sending the reply
  ERASED,            // settings and Wi-Fi are gone: apply, then restart
};

struct LineResult {
  std::string reply;  // one JSON object, no newline; empty = send nothing
  LineAction action = LineAction::NONE;
};

// Handles one complete line. `settings` only changes if the whole request was
// valid and the store accepted it. Lines not starting with '{' are log output,
// and '{' lines without a "lumen" key aren't for us: neither gets a reply.
LineResult handleLine(const char *line, size_t len, Settings &settings,
                      const std::string &defaultName, SettingsStore &store);

// Reply for a line that exceeded MAX_LINE_BYTES, given the bytes that were kept.
// Empty if it wasn't a JSON line.
std::string oversizedLineReply(const char *prefix, size_t len);

// Adds the framing for the shared UART: a leading newline so the reply starts a
// line even if a log line was cut short, and a trailing one to end it.
std::string frameReply(const std::string &reply);

// ---- byte demultiplexer -----------------------------------------------------
// Long enough for a valid set request with every string fully \u-escaped.
const size_t MAX_LINE_BYTES = 1024;
// A partial line or packet is dropped after this long without a byte, so a
// truncated Improv packet can't swallow later requests for long.
const uint32_t SERIAL_IDLE_RESET_MS = 1000;

// Improv packets are found by their 7-byte signature, "IMPROV" and version 1.
// Valid JSON can't contain that sequence, because a raw 0x01 isn't allowed in
// it, so JSON text containing "IMPROV" still passes through untouched. Packets
// are framed by their length byte, so newlines and '{' inside them are data.
class SerialDemux {
 public:
  enum EventType : uint8_t {
    EV_NONE,
    EV_LINE,                 // data/len: the line, without its line ending
    EV_LINE_TOO_LONG,        // data/len: the first MAX_LINE_BYTES of the line
    EV_IMPROV_PACKET,        // improvType, data/len: the checksum was good
    EV_IMPROV_BAD_CHECKSUM,  // the packet was consumed and must be rejected
  };
  struct Event {
    EventType type;
    uint8_t improvType;
    const uint8_t *data;  // valid until the next feed()
    size_t len;
  };

  Event feed(uint8_t byte, uint32_t nowMs);

 private:
  Event feedPacket(uint8_t byte);
  Event feedLine(uint8_t byte);
  void pushLine(uint8_t byte);

  uint8_t line_[MAX_LINE_BYTES];
  size_t lineLen_ = 0;
  bool lineOverflow_ = false;
  uint8_t packet_[2 + 255 + 1];  // type, length, data, checksum
  size_t packetPos_ = 0;
  bool inPacket_ = false;
  uint8_t sigPos_ = 0;
  uint32_t lastByteMs_ = 0;
  bool seenByte_ = false;
};

// ---- Improv Serial ----------------------------------------------------------
typedef std::vector<uint8_t> Bytes;

// What the Improv RPC handler needs from the device.
class ImprovHost {
 public:
  virtual ~ImprovHost() {}
  virtual uint8_t improvState() = 0;  // an improv::State value
  virtual std::string deviceName() = 0;
  // Start connecting without blocking. False if it can't start now.
  virtual bool startProvisioning(const std::string &ssid, const std::string &password) = 0;
  // Start a scan without blocking; results follow with improvScanPackets().
  virtual void startScan() = 0;
};

struct ScanEntry {
  std::string ssid;
  int rssi;
  bool secured;
};

// Packets are framed with a newline on both sides. The Improv browser client
// only recognises a packet at the start of a line.
Bytes improvStatePacket(uint8_t state);
Bytes improvErrorPacket(uint8_t error);
Bytes improvRpcResultPacket(uint8_t command, const std::vector<std::string> &strings);

// Handles an EV_IMPROV_PACKET or EV_IMPROV_BAD_CHECKSUM, adding replies to `out`.
void handleImprovEvent(const SerialDemux::Event &ev, ImprovHost &host, std::vector<Bytes> &out);

// Outcome of a provisioning attempt started by ImprovHost::startProvisioning().
void improvProvisionedPackets(std::vector<Bytes> &out);
void improvProvisionFailedPackets(std::vector<Bytes> &out);

// One result per network, strongest signal per SSID, hidden networks dropped,
// followed by the empty result that ends the list.
void improvScanPackets(const std::vector<ScanEntry> &entries, std::vector<Bytes> &out);

}  // namespace lumen
