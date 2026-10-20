#pragma once
// MAX98357A I2S output.  All sounds are short original chimes synthesised
// on the fly (sine partials with a decay envelope), no samples stored.

#include <stdint.h>

enum Cue : uint8_t { CUE_READ, CUE_NEED_FINGER, CUE_GRANTED, CUE_DENIED, CUE_ERROR, CUE_ENROLL_OK };

void audioBegin();
void audioPlay(Cue c);          // non-blocking; a new cue replaces the playing one
void audioSetVolume(uint8_t v);  // 0-100
