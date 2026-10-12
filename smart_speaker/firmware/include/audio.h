#pragma once
#include <Arduino.h>

// I2S audio: INMP441 pair in (I2S1), MAX98357A out (I2S0).
// Mic and speaker each run in their own FreeRTOS task; the WebSocket side
// only touches the ring buffers through these functions.
namespace audio {

bool begin();

// ---- microphones ----
void setMicEnabled(bool enabled);   // when off, frames are discarded
bool micEnabled();
void setMicChannels(uint8_t ch);    // 1 = (L+R)/2 mono, 2 = interleaved L,R
uint8_t micChannels();
void setMicGainDb(float db);
float micGainDb();
size_t readMic(uint8_t *out, size_t maxBytes);  // non-blocking, PCM16LE
void flushMic();
float micLevel();                   // smoothed RMS 0..1 (always updated)

// ---- speaker ----
bool setSpeakerRate(uint32_t rate);
uint32_t speakerRate();
size_t pushSpeaker(const uint8_t *pcm16mono, size_t bytes);  // bytes accepted
size_t speakerFree();
size_t speakerQueued();
void flushSpeaker();
bool speakerActive();               // still clocking out audio
void setVolume(uint8_t pct);
uint8_t volume();
float speakerLevel();               // smoothed RMS 0..1 of what is playing

}  // namespace audio
