#pragma once

#define FW_VERSION "0.1.0"
#define FW_NAME "Round speaker"  // Improv firmware name; matches the ESP Web Tools manifest
#define PROJECT_ID "speaker"     // "project" in the serial settings protocol
#define HW_NAME "ESP32"

// ---- pins (see electronics/WIRING.md) ----------------------------------------
// Speaker: MAX98357A on I2S0
#define PIN_SPK_BCLK 26
#define PIN_SPK_LRC 25
#define PIN_SPK_DIN 22
// Mics: 2x INMP441 sharing I2S1 (left mic L/R=GND, right mic L/R=3V3)
#define PIN_MIC_SCK 32
#define PIN_MIC_WS 33
#define PIN_MIC_SD 35
// LED halo ring: WS2812B, 330 ohm in series
#define PIN_LED 27

// ---- audio ------------------------------------------------------------------
#define MIC_SAMPLE_RATE 16000     // Hz, mic stream to the hub
#define MIC_FRAME_SAMPLES 512     // per channel per WebSocket frame (32 ms)
#define MIC_GAIN_DB_DEFAULT 12.0f // INMP441 is quiet; extra digital gain
#define MIC_RING_BYTES (16 * 1024)

#define SPK_DEFAULT_RATE 16000    // Hz, hub can change it per stream
#define SPK_RING_BYTES (32 * 1024) // ~1 s at 16 kHz mono 16-bit
#define VOLUME_DEFAULT 60          // %

// ---- LEDs -------------------------------------------------------------------
// LED count and max brightness are stored settings; these are their defaults.
#define LED_COUNT_DEFAULT 39
#define LED_MAX_BRIGHTNESS_DEFAULT 150
// Power budget on the 5 V 3 A supply: 3 A less the ESP32 peak (0.35 A) and the
// amp peak (0.8 A) leaves about 1.8 A for the LEDs. Whatever the settings say,
// brightness is limited so count * full white stays inside this budget, which
// allows at most 196 of 255 at 39 LEDs and 25 of 255 at 300 LEDs.
// The firmware can't tell what's powering it. On USB only, also set the max
// brightness to about 64 (39 LEDs); the budget above doesn't protect a USB port.
#define LED_POWER_BUDGET_MA 1800
#define LED_FULL_WHITE_MA 60  // per WS2812B at full white
#define LED_FPS 40

// ---- network ----------------------------------------------------------------
#define WS_PORT 8080
#define MDNS_SERVICE "roundspk"     // advertised as _roundspk._tcp
#define AUTH_TIMEOUT_MS 5000        // client must send hello+token within this
#define STATUS_INTERVAL_MS 5000
#define PLAY_BUFFER_INTERVAL_MS 100
#define PORTAL_TIMEOUT_S 180        // Wi-Fi setup portal, then reboot
#define WIFI_CONNECT_TIMEOUT_MS 20000  // saved network or Improv credentials
#define WIFI_SCAN_TIMEOUT_MS 15000
#define SERIAL_SESSION_MS 60000     // recent USB traffic: don't reboot on portal timeout

// ---- binary frame types (first byte of every binary WebSocket message) ------
#define FRAME_MIC 0x01  // device -> hub: PCM16LE mic audio
#define FRAME_SPK 0x02  // hub -> device: PCM16LE mono speaker audio
