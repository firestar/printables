#include "mb_sha256.h"

#include <string.h>

#if defined(ESP_PLATFORM)
#include "mbedtls/md.h"
#endif

namespace mb {

namespace {

const uint32_t K[64] = {
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};

inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

}  // namespace

void Sha256::reset() {
  static const uint32_t H0[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                                 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
  memcpy(h_, H0, sizeof(h_));
  bits_ = 0;
  used_ = 0;
}

void Sha256::block(const uint8_t *p) {
  uint32_t w[64];
  for (int i = 0; i < 16; i++)
    w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 | (uint32_t)p[4 * i + 2] << 8 |
           p[4 * i + 3];
  for (int i = 16; i < 64; i++) {
    uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
    uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
    w[i] = w[i - 16] + s0 + w[i - 7] + s1;
  }
  uint32_t a = h_[0], b = h_[1], c = h_[2], d = h_[3], e = h_[4], f = h_[5], g = h_[6], h = h_[7];
  for (int i = 0; i < 64; i++) {
    uint32_t t1 = h + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
    uint32_t t2 = (rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
    h = g;
    g = f;
    f = e;
    e = d + t1;
    d = c;
    c = b;
    b = a;
    a = t1 + t2;
  }
  h_[0] += a;
  h_[1] += b;
  h_[2] += c;
  h_[3] += d;
  h_[4] += e;
  h_[5] += f;
  h_[6] += g;
  h_[7] += h;
}

void Sha256::update(const uint8_t *data, size_t len) {
  bits_ += (uint64_t)len * 8;
  while (len > 0) {
    size_t n = SHA256_BLOCK - used_;
    if (n > len) n = len;
    memcpy(buf_ + used_, data, n);
    used_ += n;
    data += n;
    len -= n;
    if (used_ == SHA256_BLOCK) {
      block(buf_);
      used_ = 0;
    }
  }
}

void Sha256::finish(uint8_t out[SHA256_LEN]) {
  uint64_t bits = bits_;
  uint8_t pad = 0x80;
  update(&pad, 1);
  pad = 0;
  while (used_ != 56) update(&pad, 1);
  uint8_t len[8];
  for (int i = 0; i < 8; i++) len[i] = (uint8_t)(bits >> (56 - 8 * i));
  update(len, 8);
  for (int i = 0; i < 8; i++) {
    out[4 * i] = (uint8_t)(h_[i] >> 24);
    out[4 * i + 1] = (uint8_t)(h_[i] >> 16);
    out[4 * i + 2] = (uint8_t)(h_[i] >> 8);
    out[4 * i + 3] = (uint8_t)h_[i];
  }
  reset();
}

void sha256(const uint8_t *data, size_t len, uint8_t out[SHA256_LEN]) {
  Sha256 s;
  s.update(data, len);
  s.finish(out);
}

void hmacSha256Portable(const uint8_t *key, size_t keyLen, const uint8_t *msg, size_t msgLen,
                        uint8_t out[SHA256_LEN]) {
  uint8_t k[SHA256_BLOCK] = {0};
  if (keyLen > SHA256_BLOCK)
    sha256(key, keyLen, k);
  else if (keyLen)
    memcpy(k, key, keyLen);
  uint8_t pad[SHA256_BLOCK];
  uint8_t inner[SHA256_LEN];
  Sha256 s;
  for (size_t i = 0; i < SHA256_BLOCK; i++) pad[i] = k[i] ^ 0x36;
  s.update(pad, SHA256_BLOCK);
  s.update(msg, msgLen);
  s.finish(inner);
  for (size_t i = 0; i < SHA256_BLOCK; i++) pad[i] = k[i] ^ 0x5c;
  s.update(pad, SHA256_BLOCK);
  s.update(inner, SHA256_LEN);
  s.finish(out);
  memset(k, 0, sizeof(k));
  memset(pad, 0, sizeof(pad));
}

void hmacSha256(const uint8_t *key, size_t keyLen, const uint8_t *msg, size_t msgLen,
                uint8_t out[SHA256_LEN]) {
#if defined(ESP_PLATFORM)
  if (mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), key, keyLen, msg, msgLen, out) == 0)
    return;
#endif
  hmacSha256Portable(key, keyLen, msg, msgLen, out);
}

bool ctEqual(const uint8_t *a, const uint8_t *b, size_t len) {
  uint8_t d = 0;
  for (size_t i = 0; i < len; i++) d |= a[i] ^ b[i];
  return d == 0;
}

}  // namespace mb
