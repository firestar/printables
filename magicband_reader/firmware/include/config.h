#pragma once

#define FW_VERSION_MAJOR 0
#define FW_VERSION_MINOR 2
#define FW_VERSION "0.2.0"

// ---- build variants (platformio.ini sets these per env) -------------------------
// HAS_FINGERPRINT 1 = R503 fitted.  0 = band-only reader: users whose policy
//                 needs a finger are DENIED (reason no_fp_hw), never downgraded.
// ALL_IN_ONE      0 = split: reader (no Wi-Fi, no authority) + indoor controller
//                 over RS-485.  1 = the reader's ESP32-S3 is the whole door:
//                 access engine, NVS users, strike, REX, door contact, Wi-Fi/MQTT.
//                 Only for a reader mounted on the SECURE side of the door.
#ifndef HAS_FINGERPRINT
#define HAS_FINGERPRINT 1
#endif
#ifndef ALL_IN_ONE
#define ALL_IN_ONE 0
#endif
#if ALL_IN_ONE && !defined(MB_ROLE_READER)
#error "ALL_IN_ONE is a reader (ESP32-S3) build"
#endif
// Builds that run the door app (src/door): access decisions, strike, HA.
#if defined(MB_ROLE_CONTROLLER) || ALL_IN_ONE
#define MB_DOOR_APP 1
#else
#define MB_DOOR_APP 0
#endif

// ---- link key -------------------------------------------------------------------
// 32-byte HMAC key shared by reader and controller.  `python3 tools/provision.py`
// writes include/secrets.h (git-ignored) with a fresh random key; flash BOTH
// boards after changing it.  Changing the key resets the link counters.
// The all-in-one has no link: secrets.h only supplies OTA_PASSWORD there.
#if __has_include("secrets.h")
#include "secrets.h"
#elif defined(MB_ALLOW_DEV_KEY)
#warning "MagicBand reader: using the public development key, never deploy this"
#define LINK_KEY_HEX "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
#elif !ALL_IN_ONE
#error "include/secrets.h missing: run `python3 tools/provision.py` (see README.md)"
#endif

// ---- link (split mode, both boards) -------------------------------------------------
#define LINK_BAUD 115200
#define HELLO_INTERVAL_MS 1000   // heartbeat period, each direction
#define PEER_TIMEOUT_MS 3500     // no valid frame for this long = peer offline
#define BUS_IDLE_MS 3            // listen-before-talk: bus quiet this long before sending
#define TX_RESERVE_BLOCK 1024    // counter reservation per NVS write
#define RX_WINDOW (1UL << 20)    // max forward jump of a peer counter
#define RX_PERSIST_STEP 256      // heartbeat counters saved every N frames

#if defined(MB_ROLE_READER)
// =================================================================================
// READER: Waveshare ESP32-S3-Zero.  Uses GPIO1-17 (side + bottom headers),
// skips the strapping pins 0/3/45/46 and the USB pins 19/20.  GPIO21 =
// onboard RGB LED.
// =================================================================================
#define PIN_I2C_SDA 1          // PN532 SDA (module set to I2C: SEL0=H, SEL1=L)
#define PIN_I2C_SCL 2          // PN532 SCL
#define PIN_PN532_IRQ 4        // PN532 IRQ (open drain, active LOW)
#define PIN_PN532_RST 5        // PN532 RSTPDN
#if HAS_FINGERPRINT
#define PIN_FP_TX 6            // ESP TX -> R503 RX (green? check your cable)
#define PIN_FP_RX 7            // ESP RX <- R503 TX
#define PIN_FP_TOUCH 8         // R503 WAKEUP (touch) output
#endif                         // nofp: GPIO6-8 unused
#if !ALL_IN_ONE
#define PIN_RS485_TX 9         // MAX3485 DI
#define PIN_RS485_RX 10        // MAX3485 RO
#define PIN_RS485_DE 11        // MAX3485 DE + /RE tied together, HIGH = transmit
#else
// all-in-one: no MAX3485, GPIO9-11 drive the door instead
#define PIN_STRIKE 9           // MOSFET gate (100 R, 10k to GND) / relay module IN, HIGH = coil energised
#define PIN_REX 10             // exit button to GND (NO contact), INPUT_PULLUP
#define PIN_DOOR 11            // door reed to GND, closed (LOW) = door shut
#define PIN_ENROLL 17          // optional enroll button to GND (bottom header)
#endif
#define PIN_I2S_BCLK 12        // MAX98357A BCLK
#define PIN_I2S_LRC 13         // MAX98357A LRC
#define PIN_I2S_DOUT 14        // MAX98357A DIN
#define PIN_LED_DATA 15        // 330 R -> WS2812B DIN (via 74AHCT125 if it flickers)
#define PIN_TAMPER 16          // hatch microswitch to GND, closed = hatch shut

// 0 = no tamper switch fitted (e.g. an indoor housing): GPIO16 is ignored.
#ifndef HAS_TAMPER_SWITCH
#define HAS_TAMPER_SWITCH 1
#endif

// ---- LEDs ----
#define LED_HALO_COUNT 42      // halo ring LEDs (first in the chain; CAD ring = 42 @ 144/m)
#define LED_MICKEY_COUNT 0     // optional Mickey backlight after the halo, 0 = none
#define LED_BRIGHTNESS_DEFAULT 96   // 0-255, SET_CONFIG can change it
#define LED_MAX_BRIGHTNESS 128      // hard cap regardless of SET_CONFIG
#define LED_CURRENT_LIMIT_MA 1200   // estimated strip current cap (see WIRING.md power budget)
#define LED_MA_PER_CHANNEL 20       // WS2812B worst case per colour channel at 255

// ---- audio ----
#define AUDIO_SAMPLE_RATE 22050
#define AUDIO_VOLUME_DEFAULT 60     // 0-100

// ---- NFC / fingerprint ----
#define NFC_REPEAT_MS 2500     // same UID again within this = the band is still held there
#define FP_BAUD 57600
#define FP_TOUCH_ACTIVE_HIGH 1 // R503 WAKEUP is high while a finger touches
#define FP_MIN_SCORE 50        // R503 confidence below this = no match
#define FP_ENROLL_TIMEOUT_MS 50000

// ---- behaviour ----
#define FEEDBACK_TIMEOUT_MS 1500   // split: no FEEDBACK after an event: retry / show error
#define EVENT_RETRIES 2
#define TAMPER_DEBOUNCE_MS 50

#elif defined(MB_ROLE_CONTROLLER)
// =================================================================================
// CONTROLLER: ESP32-WROOM-32 devkit (30-pin).  Avoids strapping pins
// (0, 2*, 5, 12, 15), flash pins (6-11) and input-only 34-39.  *GPIO2 = LED.
// =================================================================================
#define PIN_RS485_RX 16        // MAX3485 RO (UART2)
#define PIN_RS485_TX 17        // MAX3485 DI
#define PIN_RS485_DE 4         // MAX3485 DE + /RE, HIGH = transmit
#define PIN_STRIKE 25          // MOSFET gate / relay module IN, HIGH = coil energised
#define PIN_REX 32             // exit button to GND (NO contact), INPUT_PULLUP
#define PIN_DOOR 33            // door reed to GND, closed (LOW) = door shut
#define PIN_ENROLL 27          // optional enroll push button to GND
#define PIN_LED 2              // onboard LED: on = reader online
#endif

#if MB_DOOR_APP
// =================================================================================
// DOOR APP: controller, or the all-in-one reader
// =================================================================================
#if ALL_IN_ONE
#define HA_MODEL "ESP32-S3 all-in-one MagicBand reader"
#else
#define HA_MODEL "ESP32 door controller + RS-485 reader"
#endif

// ---- lock output ----
// 1 = fail-secure electric strike: energise to unlock (default).
// 0 = maglock / fail-safe: energised = locked, de-energise to unlock.
#define STRIKE_ENERGIZE_TO_UNLOCK 1
#define UNLOCK_PULSE_MS 5000       // how long the door stays released
#define RELOCK_ON_DOOR_CLOSE 1     // end the pulse early once the door opened and closed again

// ---- access policy ----
#define FINGER_TIMEOUT_MS 8000     // band -> finger window
#define MAX_FAILURES 5             // consecutive failures before a lockout
#define LOCKOUT_MS 30000           // first lockout, doubles each time
#define LOCKOUT_MAX_MS 900000      // 15 min cap
#define ENROLL_BAND_TIMEOUT_MS 30000
#define ENROLL_FINGER_TIMEOUT_MS 60000
#define TAMPER_DENIES_ACCESS 1     // reader hatch open or link lost: deny scans (REX still works)
#define SHOW_FULL_UID 0            // 0 = MQTT shows only first/last byte of band UIDs
#define GRANTED_HOLD_MS 1500       // reader shows GRANTED this long
#define DENIED_HOLD_MS 2000
#define EVENT_DEDUP_MS 1000        // a retransmitted reader event within this is not re-evaluated
#define LINK_ERROR_ALERT 20        // bad tags/replays per minute that raise tamper

// ---- network ----
#define HOSTNAME "magicband"       // mDNS / OTA: magicband.local
#define MQTT_BASE "magicband"      // topics: magicband/<...>
#define HA_DISCOVERY_PREFIX "homeassistant"
#define PORTAL_TIMEOUT_S 180
#define MQTT_RETRY_MS 5000
#define WDT_TIMEOUT_S 30
#ifndef OTA_PASSWORD
#define OTA_PASSWORD ""            // set it in secrets.h
#endif
#endif
