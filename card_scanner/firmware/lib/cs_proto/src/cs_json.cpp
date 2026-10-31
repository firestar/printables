#include "cs_json.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace cs {

namespace {

void skipWs(const char *&s) {
  while (*s == ' ' || *s == '\t' || *s == '\r' || *s == '\n') s++;
}

int hexVal(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

// "..." into out (NUL terminated).  \uXXXX outside ASCII becomes '?'.
bool parseString(const char *&s, char *out, size_t cap) {
  if (*s != '"') return false;
  s++;
  size_t n = 0;
  while (*s != '"') {
    char c = *s;
    if (c == 0 || (unsigned char)c < 0x20) return false;
    if (c == '\\') {
      s++;
      switch (*s) {
        case '"': c = '"'; break;
        case '\\': c = '\\'; break;
        case '/': c = '/'; break;
        case 'b': c = '\b'; break;
        case 'f': c = '\f'; break;
        case 'n': c = '\n'; break;
        case 'r': c = '\r'; break;
        case 't': c = '\t'; break;
        case 'u': {
          unsigned v = 0;
          for (int i = 0; i < 4; i++) {
            int d = hexVal(*++s);
            if (d < 0) return false;
            v = v * 16 + (unsigned)d;
          }
          if (v == 0) return false;
          c = v < 0x80 ? (char)v : '?';
          break;
        }
        default: return false;
      }
    }
    if (n + 1 >= cap) return false;
    out[n++] = c;
    s++;
  }
  s++;
  out[n] = 0;
  return true;
}

// JSON number grammar, then strtod over exactly that span.
bool parseNumber(const char *&s, double &out) {
  const char *p = s;
  if (*p == '-') p++;
  if (*p == '0') {
    p++;
  } else if (*p >= '1' && *p <= '9') {
    while (*p >= '0' && *p <= '9') p++;
  } else {
    return false;
  }
  if (*p == '.') {
    p++;
    if (!(*p >= '0' && *p <= '9')) return false;
    while (*p >= '0' && *p <= '9') p++;
  }
  if (*p == 'e' || *p == 'E') {
    p++;
    if (*p == '+' || *p == '-') p++;
    if (!(*p >= '0' && *p <= '9')) return false;
    while (*p >= '0' && *p <= '9') p++;
  }
  char tmp[32];
  size_t len = (size_t)(p - s);
  if (len >= sizeof(tmp)) return false;
  memcpy(tmp, s, len);
  tmp[len] = 0;
  out = strtod(tmp, nullptr);
  s = p;
  return isfinite(out);
}

}  // namespace

bool JsonObject::parse(const char *s) {
  n_ = 0;
  if (!s) return false;
  skipWs(s);
  if (*s++ != '{') return false;
  skipWs(s);
  if (*s == '}') {
    s++;
  } else {
    for (;;) {
      if (n_ >= MAX_FIELDS) return false;
      JsonField &f = f_[n_];
      skipWs(s);
      if (!parseString(s, f.key, sizeof(f.key))) return false;
      if (find(f.key)) return false;  // duplicate key
      skipWs(s);
      if (*s++ != ':') return false;
      skipWs(s);
      f.num = 0;
      f.b = false;
      f.str[0] = 0;
      if (*s == '"') {
        if (!parseString(s, f.str, sizeof(f.str))) return false;
        f.type = JT_STR;
      } else if (!strncmp(s, "true", 4)) {
        s += 4;
        f.type = JT_BOOL;
        f.b = true;
      } else if (!strncmp(s, "false", 5)) {
        s += 5;
        f.type = JT_BOOL;
      } else if (!strncmp(s, "null", 4)) {
        s += 4;
        f.type = JT_NULL;
      } else {
        if (!parseNumber(s, f.num)) return false;
        f.type = JT_NUM;
      }
      n_++;
      skipWs(s);
      if (*s == ',') {
        s++;
        continue;
      }
      if (*s == '}') {
        s++;
        break;
      }
      return false;
    }
  }
  skipWs(s);
  if (*s != 0) {
    n_ = 0;
    return false;
  }
  return true;
}

const JsonField *JsonObject::find(const char *key) const {
  for (int i = 0; i < n_; i++)
    if (!strcmp(f_[i].key, key)) return &f_[i];
  return nullptr;
}

bool JsonObject::getNum(const char *key, double &out) const {
  const JsonField *f = find(key);
  if (!f || f->type != JT_NUM) return false;
  out = f->num;
  return true;
}

bool JsonObject::getInt(const char *key, int32_t &out) const {
  double v;
  if (!getNum(key, v)) return false;
  if (v != floor(v) || v < -2147483648.0 || v > 2147483647.0) return false;
  out = (int32_t)v;
  return true;
}

const char *JsonObject::getStr(const char *key) const {
  const JsonField *f = find(key);
  return (f && f->type == JT_STR) ? f->str : nullptr;
}

// ---- writer ---------------------------------------------------------------------

JsonWriter::JsonWriter(char *buf, size_t cap) : buf_(buf), cap_(cap) {
  if (cap_) buf_[0] = 0;
  else overflow_ = true;
}

void JsonWriter::ch(char c) {
  if (len_ + 1 >= cap_) {
    overflow_ = true;
    return;
  }
  buf_[len_++] = c;
  buf_[len_] = 0;
}

void JsonWriter::raw(const char *s) {
  while (*s) ch(*s++);
}

void JsonWriter::quoted(const char *s) {
  ch('"');
  for (; *s; s++) {
    unsigned char c = (unsigned char)*s;
    if (c == '"' || c == '\\') {
      ch('\\');
      ch((char)c);
    } else if (c < 0x20) {
      char t[8];
      snprintf(t, sizeof(t), "\\u%04x", c);
      raw(t);
    } else {
      ch((char)c);
    }
  }
  ch('"');
}

void JsonWriter::key(const char *k) {
  if (depth_ > 0 && depth_ <= MAX_DEPTH) {
    if (!first_[depth_ - 1]) ch(',');
    first_[depth_ - 1] = false;
  }
  if (k && depth_ > 0) {
    quoted(k);
    ch(':');
  }
}

JsonWriter &JsonWriter::open(const char *k) {
  key(k);
  ch('{');
  if (depth_ < MAX_DEPTH) first_[depth_] = true;
  depth_++;
  return *this;
}

JsonWriter &JsonWriter::close() {
  ch('}');
  if (depth_ > 0) depth_--;
  return *this;
}

JsonWriter &JsonWriter::num(const char *k, double v, int decimals) {
  key(k);
  char t[32];
  if (!isfinite(v)) {
    raw("null");
    return *this;
  }
  if (decimals >= 0)
    snprintf(t, sizeof(t), "%.*f", decimals, v);
  else if (v == floor(v) && fabs(v) < 1e9)
    snprintf(t, sizeof(t), "%ld", (long)v);
  else
    snprintf(t, sizeof(t), "%.6g", v);
  raw(t);
  return *this;
}

JsonWriter &JsonWriter::integer(const char *k, long v) {
  key(k);
  char t[24];
  snprintf(t, sizeof(t), "%ld", v);
  raw(t);
  return *this;
}

JsonWriter &JsonWriter::str(const char *k, const char *v) {
  key(k);
  quoted(v ? v : "");
  return *this;
}

JsonWriter &JsonWriter::boolean(const char *k, bool v) {
  key(k);
  raw(v ? "true" : "false");
  return *this;
}

}  // namespace cs
