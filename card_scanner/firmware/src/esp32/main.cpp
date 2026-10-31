// Card scanner motion controller: ESP32-S3 <-> Raspberry Pi 5 over USB CDC.
// Newline-delimited JSON, see PROTOCOL.md.  All sequencing lives in
// lib/cs_motion (unit-tested natively); this file is just the board glue.

#include <Arduino.h>
#include <Preferences.h>

#include "config.h"
#include "cs_scanner.h"
#include "hal_esp32.h"

namespace {

class SerialSink : public cs::LineSink {
 public:
  void sendLine(const char *line) override {
    Serial.write((const uint8_t *)line, strlen(line));
    Serial.write('\n');
  }
};

class NvsStore : public cs::SettingsStore {
 public:
  void begin() { prefs_.begin("cs", false); }
  bool load(const char *key, float &v) override {
    if (!prefs_.isKey(key)) return false;
    v = prefs_.getFloat(key, v);
    return true;
  }
  void save(const char *key, float v) override { prefs_.putFloat(key, v); }

 private:
  Preferences prefs_;
};

cs::Esp32Hal hal;
SerialSink sink;
NvsStore store;
cs::Scanner scanner(hal, sink, &store, FW_VERSION);

char line[cs::LINE_MAX_LEN + 1];
size_t lineLen = 0;
bool overflow = false;

void readHost() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflow) {
        sink.sendLine("{\"id\":-1,\"ok\":false,\"err\":\"bad_cmd\",\"msg\":\"line too long\"}");
      } else {
        line[lineLen] = 0;
        scanner.handleLine(line);
      }
      lineLen = 0;
      overflow = false;
    } else if (lineLen < cs::LINE_MAX_LEN) {
      line[lineLen++] = c;
    } else {
      overflow = true;
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(HOST_BAUD);
  store.begin();
  hal.begin();
  scanner.begin();
}

void loop() {
  hal.poll();
  readHost();
  scanner.tick();
}
