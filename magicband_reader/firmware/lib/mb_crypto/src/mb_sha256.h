#pragma once
// Portable SHA-256 + HMAC-SHA256 (FIPS 180-4, RFC 2104).
// On ESP32 (ESP_PLATFORM defined) hmacSha256() uses mbedtls; the portable
// code is always compiled so the native tests exercise it.  No Arduino headers.

#include <stddef.h>
#include <stdint.h>

namespace mb {

static const size_t SHA256_LEN = 32;
static const size_t SHA256_BLOCK = 64;

class Sha256 {
 public:
  Sha256() { reset(); }
  void reset();
  void update(const uint8_t *data, size_t len);
  void finish(uint8_t out[SHA256_LEN]);

 private:
  void block(const uint8_t *p);
  uint32_t h_[8];
  uint64_t bits_;
  uint8_t buf_[SHA256_BLOCK];
  size_t used_;
};

void sha256(const uint8_t *data, size_t len, uint8_t out[SHA256_LEN]);

// Portable HMAC-SHA256.  Any key length (keys > 64 bytes are hashed first).
void hmacSha256Portable(const uint8_t *key, size_t keyLen, const uint8_t *msg, size_t msgLen,
                        uint8_t out[SHA256_LEN]);

// HMAC-SHA256 via mbedtls on ESP32, portable elsewhere.
void hmacSha256(const uint8_t *key, size_t keyLen, const uint8_t *msg, size_t msgLen,
                uint8_t out[SHA256_LEN]);

// Constant-time compare (tag check).
bool ctEqual(const uint8_t *a, const uint8_t *b, size_t len);

}  // namespace mb
