#pragma once

#define FW_VERSION_MAJOR 0
#define FW_VERSION_MINOR 1
#define FW_VERSION "0.1.0"

// =================================================================================
// ESP32-S3-DevKitC-1 (N8R8 / N16R8 / N8).  Host link = the native USB port
// (USB CDC, "USB" connector), NOT the "UART" connector.
// Free of: strapping 0/3/45/46, USB 19/20, UART0 43/44, flash/PSRAM 26-37,
// onboard RGB LED 38 (v1.1) / 48 (v1.0).  All 23 remaining GPIOs are used;
// slow I/O sits on two MCP23017s (I2C).  Full table: ../electronics/WIRING.md
// =================================================================================

// ---- steppers (TMC2209 STEP/DIR) ----
#define PIN_ELEV_STEP 4
#define PIN_ELEV_DIR 5
#define PIN_PICK_STEP 6
#define PIN_PICK_DIR 7
#define PIN_FEED_STEP 15
#define PIN_FEED_DIR 16
#define PIN_TONGUE_STEP 17
#define PIN_TONGUE_DIR 18
#define PIN_STEPPER_EN 8       // all four EN pins, active LOW; 10k pull-up = disabled at reset

// ---- TMC2209 UART bus (UART1), addresses 0-3 via MS1/MS2 ----
#define PIN_TMC_TX 9           // -> 1k -> PDN_UART of all four drivers
#define PIN_TMC_RX 10          // <- PDN_UART bus directly
#define TMC_BAUD 115200
#define TMC_R_SENSE 0.11f      // BTT / FYSETC / MKS TMC2209 modules
#define TMC_ADDR_ELEV 0        // MS1=L MS2=L
#define TMC_ADDR_PICK 1        // MS1=H MS2=L
#define TMC_ADDR_FEED 2        // MS1=L MS2=H
#define TMC_ADDR_TONGUE 3      // MS1=H MS2=H
#define TMC_HOLD_MULT 0.5f     // hold current = run current x this
#define MICROSTEPS 16

// ---- I2C: two MCP23017 port expanders ----
#define PIN_I2C_SDA 11
#define PIN_I2C_SCL 12
#define I2C_HZ 400000
#define MCP_OUT_ADDR 0x20      // A2..A0 = 000: all 16 pins outputs (pneumatics + spares)
#define MCP_IN_ADDR 0x21       // A2..A0 = 001: inputs on GPA0-6, GPB0-6 (GPA7/GPB7 are output-only)
#define IO_POLL_US 1000        // expander input poll period

// ---- servos (LEDC 50 Hz) ----
#define PIN_SERVO_LIFT 13
#define PIN_SERVO_PUSHER 14
#define PIN_SERVO_DIVERTER 21
#define SERVO_MIN_US 500       // 0 deg   (MG90S / SG90: 500-2400 us)
#define SERVO_MAX_US 2400      // 180 deg

// ---- scan lights (LEDC PWM -> logic-level MOSFETs) ----
#define PIN_LIGHT_TOP 39
#define PIN_LIGHT_BOTTOM 40
#define LIGHT_PWM_HZ 20000

// ---- fast sensors on native GPIO (INPUT_PULLUP) ----
#define PIN_SCAN_STOP 41       // microswitch NO -> GND
#define PIN_SLEEVE_MOUTH 42    // TCRT5000 module under the platen, LOW = card seen
#define PIN_DOUBLE_FEED 2      // slot opto on the thickness-gauge flag
#define PIN_ESTOP 47           // e-stop monitor contact NC -> GND (open = pressed)

// ---- vacuum sensor (XGZP6847A, -100..0 kPa, 0.5-4.5 V at 5 V) ----
#define PIN_VAC_SENSE 1        // ADC1_CH0, via 10k / 20k divider (x 2/3)
#define VAC_DIVIDER 1.5f       // sensor volts = pin volts x this
#define VAC_V_AT_ZERO 4.5f     // ambient
#define VAC_V_AT_FULL 0.5f     // -100 kPa
#define VAC_RANGE_KPA 100.0f
#define VAC_FILTER 0.2f        // EMA weight per 2 ms sample

// ---- MCP23017 #1 (0x20) outputs: bit 0-7 = GPA0-7, 8-15 = GPB0-7 ----
#define MCPO_VAC_PUMP 0
#define MCPO_PICK_CUP 1
#define MCPO_PLATEN 2
#define MCPO_LIFT_CUP 3
#define MCPO_PUFF_PUMP 4
#define MCPO_STACK_PUFF 5
#define MCPO_MOUTH_JET 6
// sleeve_pick: DRV8833 channel A (N20 gearmotor, VM = 5V_SERVO).  No free ESP32 GPIO for PWM, and
// none needed: the pick is a fixed-speed run until sleeve_present.  IN1/IN2 = 1/0 forward, 1/1 brake, 0/0 coast
// (power-up, pins high-Z: the DRV8833 input pull-downs coast the motor).
#define MCPO_SLEEVE_PICK_IN1 7   // GPA7 -> DRV8833 AIN1
#define MCPO_SLEEVE_PICK_IN2 8   // GPB0 -> DRV8833 AIN2
// GPB1-7: spare (beacon, buzzer, extra valves)

// ---- MCP23017 #2 (0x21) inputs, pull-ups on ----
#define MCPI_STACK_TOP 0       // GPA0  IR reflective (TCRT5000 module), LOW = card seen
#define MCPI_EXIT 1            // GPA1  TCRT5000 module in the diverter lead-in, LOW = card seen
#define MCPI_ELEV_HOME 2       // GPA2  microswitch NC -> GND, open = at home
#define MCPI_ELEV_LIMIT 3      // GPA3  microswitch NC -> GND, open = at top
#define MCPI_PICK_HOME 4       // GPA4  microswitch NC -> GND
#define MCPI_TONGUE_HOME 5     // GPA5  microswitch NC -> GND
#define MCPI_LID 6             // GPA6  lid switch NC (closed while shut) -> GND, open = lid open
#define MCPI_MAG_LOW 8         // GPB0  IR reflective at the low mark, HIGH = no sleeve seen
#define MCPI_MAG_EMPTY 9       // GPB1  IR reflective at the bottom,   HIGH = no sleeve seen
#define MCPI_SLEEVE_PRESENT 10 // GPB2  TCRT5000 module under the platen at (6, +26), LOW = sleeve seen
// GPB3-6: spare inputs.  GPA7 / GPB7: output-only on current MCP23017 silicon, unused.

// ---- sensor polarity: level that means "active" ----
#define ACTIVE_SCAN_STOP LOW
#define ACTIVE_SLEEVE_MOUTH LOW
#define ACTIVE_DOUBLE_FEED HIGH
#define ACTIVE_ESTOP HIGH
#define ACTIVE_STACK_TOP LOW
#define ACTIVE_EXIT LOW
#define ACTIVE_SLEEVE_PRESENT LOW
#define ACTIVE_HOME HIGH       // NC switches: open (pulled HIGH) = pressed or wire cut
#define ACTIVE_LID_OPEN HIGH
#define ACTIVE_MAG HIGH

// ---- mechanics: microsteps per mm (MICROSTEPS = 16, 1.8 deg motors) ----
#define STEPS_PER_MM_ELEV 400.0f    // T8 leadscrew, 8 mm lead: 3200 / 8
#define STEPS_PER_MM_PICK 80.0f     // GT2 belt, 20T pulley: 3200 / 40
#define STEPS_PER_MM_FEED 46.3f     // ~22 mm effective roller dia: 3200 / 69.1 (calibrate)
#define STEPS_PER_MM_TONGUE 80.0f   // GT2 belt, 20T pulley
#define DIR_INVERT_ELEV 0           // 1 = flip if the axis runs backwards
#define DIR_INVERT_PICK 0
#define DIR_INVERT_FEED 0
#define DIR_INVERT_TONGUE 0

// ---- host link ----
#define HOST_BAUD 115200            // nominal; USB CDC ignores it
