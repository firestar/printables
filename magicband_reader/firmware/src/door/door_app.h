#pragma once
// Door application shared by the indoor controller (split mode) and the
// all-in-one reader: strike, exit button, door contact, enroll button, NVS
// users, the DoorCore decisions (lib/mb_access/mb_door.h) and Home
// Assistant over MQTT.  Access works without Wi-Fi.
//
// The role supplies the "front" = the reader's lights, sound and R503:
//   controller: FEEDBACK / ENROLL_FINGER / ... frames over RS-485
//   all-in-one: direct calls into the local LED / audio / R503 code

#include <stdint.h>

// ---- implemented by the role ---------------------------------------------------------
void frontFeedback(uint8_t state, uint32_t holdMs);  // mb::Feedback, hold 0 = stay
void frontEnrollFinger(uint16_t page);               // run the R503 two-touch enrollment
void frontDeleteFinger(uint16_t page);               // 0xFFFF = empty the library
void frontConfig(uint8_t brightness, uint8_t volume);

// ---- door app --------------------------------------------------------------------------
void doorBegin();  // pins, NVS users + settings, Wi-Fi/MQTT (portal if ENROLL held at power-up)
void doorLoop();   // inputs, timers, relock, HA

// Reader events (from the link, or local in the all-in-one)
void doorBand(const uint8_t *uid, uint8_t len);
void doorFinger(uint16_t page);
void doorFingerNoMatch();
void doorEnrollResult(uint16_t page, uint8_t status);
void doorResendFeedback();  // retransmitted reader event: answer again, don't re-evaluate

// Reader status.  Offline, hatch open or a link alarm refuse scans (TAMPER_DENIES_ACCESS).
void doorReaderOnline(bool online);
void doorReaderTamper(bool open, bool logEvent);
void doorReaderCaps(uint8_t caps);  // mb::CAP_* from HELLO (split) or the build (all-in-one)
void doorLinkErrors(uint32_t rejected, bool alarm);
bool doorIsOpen();  // door contact
