#pragma once

#define FW_VERSION "0.1.0"

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
#define NUM_LEDS 39

// ---- audio ------------------------------------------------------------------
#define MIC_SAMPLE_RATE 16000     // Hz, mic stream to the hub
#define MIC_FRAME_SAMPLES 512     // per channel per WebSocket frame (32 ms)
#define MIC_GAIN_DB_DEFAULT 12.0f // INMP441 is quiet; extra digital gain
#define MIC_RING_BYTES (16 * 1024)

#define SPK_DEFAULT_RATE 16000    // Hz, hub can change it per stream
#define SPK_RING_BYTES (32 * 1024) // ~1 s at 16 kHz mono 16-bit
#define VOLUME_DEFAULT 60          // %

// ---- LEDs -------------------------------------------------------------------
// Power budget: 39 LEDs at full white = 2.3 A. 150 (~60%) is safe on the
// 5 V 3 A supply; use ~64 (25%) when running from USB only.
#define LED_MAX_BRIGHTNESS_DEFAULT 150
#define LED_FPS 40

// ---- network ----------------------------------------------------------------
#define WS_PORT 8080
#define MDNS_SERVICE "roundspk"     // advertised as _roundspk._tcp
#define AUTH_TIMEOUT_MS 5000        // client must send hello+token within this
#define STATUS_INTERVAL_MS 5000
#define PLAY_BUFFER_INTERVAL_MS 100
#define PORTAL_TIMEOUT_S 180        // Wi-Fi setup portal, then reboot

// ---- binary frame types (first byte of every binary WebSocket message) ------
#define FRAME_MIC 0x01  // device -> hub: PCM16LE mic audio
#define FRAME_SPK 0x02  // hub -> device: PCM16LE mono speaker audio
