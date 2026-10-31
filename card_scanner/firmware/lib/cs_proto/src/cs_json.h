#pragma once
// Minimal JSON for the host link: parse one flat request object per line, write
// replies and events.  No heap, no dependencies, so the same code builds on the
// ESP32-S3 and in `pio test -e native`.

#include <stddef.h>
#include <stdint.h>

namespace cs {

enum JsonType : uint8_t { JT_NUM, JT_STR, JT_BOOL, JT_NULL };

struct JsonField {
  char key[16];  // keys up to 15 chars (also the NVS key limit)
  JsonType type;
  double num;
  bool b;
  char str[40];
};

// A flat JSON object: {"key": number | "string" | true | false | null, ...}.
// Rejected: nested objects/arrays, duplicate keys, more than MAX_FIELDS fields,
// keys over 15 chars, strings over 39 chars, trailing garbage.
class JsonObject {
 public:
  static const int MAX_FIELDS = 8;
  bool parse(const char *s);
  const JsonField *find(const char *key) const;
  bool has(const char *key) const { return find(key) != nullptr; }
  bool getNum(const char *key, double &out) const;
  bool getInt(const char *key, int32_t &out) const;  // a number with no fraction
  const char *getStr(const char *key) const;          // nullptr if missing / not a string
  int size() const { return n_; }

 private:
  JsonField f_[MAX_FIELDS];
  int n_ = 0;
};

// Appends to a caller-owned buffer.  ok() is false if anything was truncated.
class JsonWriter {
 public:
  JsonWriter(char *buf, size_t cap);
  JsonWriter &open(const char *key = nullptr);  // '{', or "key":{ inside an object
  JsonWriter &close();
  JsonWriter &num(const char *key, double v, int decimals = -1);  // -1 = shortest
  JsonWriter &integer(const char *key, long v);
  JsonWriter &str(const char *key, const char *v);
  JsonWriter &boolean(const char *key, bool v);
  bool ok() const { return !overflow_; }
  const char *c_str() const { return buf_; }
  size_t length() const { return len_; }

 private:
  static const int MAX_DEPTH = 4;
  void ch(char c);
  void raw(const char *s);
  void key(const char *k);
  void quoted(const char *s);
  char *buf_;
  size_t cap_;
  size_t len_ = 0;
  bool overflow_ = false;
  bool first_[MAX_DEPTH];
  int depth_ = 0;
};

}  // namespace cs
