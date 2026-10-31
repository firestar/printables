#include "hal_esp32.h"

#include <Arduino.h>
#include <FastAccelStepper.h>
#include <TMCStepper.h>
#include <Wire.h>
#if __has_include(<esp_arduino_version.h>)
#include <esp_arduino_version.h>
#endif

#include "config.h"

namespace cs {

namespace {

FastAccelStepperEngine engine;
FastAccelStepper *st[AX_COUNT] = {};

const uint8_t STEP_PIN[AX_COUNT] = {PIN_ELEV_STEP, PIN_PICK_STEP, PIN_FEED_STEP, PIN_TONGUE_STEP};
const uint8_t DIR_PIN[AX_COUNT] = {PIN_ELEV_DIR, PIN_PICK_DIR, PIN_FEED_DIR, PIN_TONGUE_DIR};
const bool DIR_INV[AX_COUNT] = {DIR_INVERT_ELEV, DIR_INVERT_PICK, DIR_INVERT_FEED, DIR_INVERT_TONGUE};
const float SPM[AX_COUNT] = {STEPS_PER_MM_ELEV, STEPS_PER_MM_PICK, STEPS_PER_MM_FEED, STEPS_PER_MM_TONGUE};

TMC2209Stepper tmcElev(&Serial1, TMC_R_SENSE, TMC_ADDR_ELEV);
TMC2209Stepper tmcPick(&Serial1, TMC_R_SENSE, TMC_ADDR_PICK);
TMC2209Stepper tmcFeed(&Serial1, TMC_R_SENSE, TMC_ADDR_FEED);
TMC2209Stepper tmcTongue(&Serial1, TMC_R_SENSE, TMC_ADDR_TONGUE);
TMC2209Stepper *const tmc[AX_COUNT] = {&tmcElev, &tmcPick, &tmcFeed, &tmcTongue};

// LEDC channels: servos 0-2 (timers 0/1 at 50 Hz), lights 4-5 (timer 2).
const uint8_t SERVO_PIN[SV_COUNT] = {PIN_SERVO_LIFT, PIN_SERVO_PUSHER, PIN_SERVO_DIVERTER};
const uint8_t SERVO_CH[SV_COUNT] = {0, 1, 2};
const uint8_t CH_LIGHT_TOP = 4, CH_LIGHT_BOTTOM = 5;
const uint8_t SERVO_BITS = 14;

// OUT_SLEEVE_PICK is not a single bit: see Esp32Hal::output
const uint8_t MCP_OUT_BIT[OUT_COUNT] = {MCPO_VAC_PUMP,  MCPO_PICK_CUP,   MCPO_PLATEN,    MCPO_LIFT_CUP,
                                        MCPO_PUFF_PUMP, MCPO_STACK_PUFF, MCPO_MOUTH_JET, MCPO_SLEEVE_PICK_IN1};

// MCP23017 registers, IOCON.BANK = 0 (A/B pairs are adjacent)
const uint8_t MCP_IODIR = 0x00, MCP_GPPU = 0x0C, MCP_GPIO = 0x12, MCP_OLAT = 0x14;

#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
void pwmAttach(uint8_t pin, uint8_t ch, uint32_t hz, uint8_t bits) { ledcAttachChannel(pin, hz, bits, ch); }
void pwmWrite(uint8_t pin, uint8_t, uint32_t duty) { ledcWrite(pin, duty); }
#else
void pwmAttach(uint8_t pin, uint8_t ch, uint32_t hz, uint8_t bits) {
  ledcSetup(ch, hz, bits);
  ledcAttachPin(pin, ch);
}
void pwmWrite(uint8_t, uint8_t ch, uint32_t duty) { ledcWrite(ch, duty); }
#endif

}  // namespace

void Esp32Hal::begin() {
  pinMode(PIN_STEPPER_EN, OUTPUT);
  digitalWrite(PIN_STEPPER_EN, HIGH);  // drivers off until the sequencer enables them

  pinMode(PIN_SCAN_STOP, INPUT_PULLUP);
  pinMode(PIN_SLEEVE_MOUTH, INPUT_PULLUP);
  pinMode(PIN_DOUBLE_FEED, INPUT_PULLUP);
  pinMode(PIN_ESTOP, INPUT_PULLUP);
  analogSetPinAttenuation(PIN_VAC_SENSE, ADC_11db);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_HZ);
  mcpInit();

  Serial1.begin(TMC_BAUD, SERIAL_8N1, PIN_TMC_RX, PIN_TMC_TX);
  for (int i = 0; i < AX_COUNT; i++) {
    TMC2209Stepper *d = tmc[i];
    d->begin();
    d->pdn_disable(true);       // PDN_UART pin = UART
    d->mstep_reg_select(true);  // microsteps from the register, MS1/MS2 = address
    d->I_scale_analog(false);   // current from the register, not Vref (see WIRING.md)
    d->toff(4);
    d->blank_time(24);
    d->microsteps(MICROSTEPS);
    d->en_spreadCycle(false);   // StealthChop: quiet
    d->pwm_autoscale(true);
  }

  engine.init();
  for (int i = 0; i < AX_COUNT; i++) {
    st[i] = engine.stepperConnectToPin(STEP_PIN[i]);
    if (st[i]) st[i]->setDirectionPin(DIR_PIN[i], !DIR_INV[i]);
  }

  for (int i = 0; i < SV_COUNT; i++) pwmAttach(SERVO_PIN[i], SERVO_CH[i], 50, SERVO_BITS);
  pwmAttach(PIN_LIGHT_TOP, CH_LIGHT_TOP, LIGHT_PWM_HZ, 8);
  pwmAttach(PIN_LIGHT_BOTTOM, CH_LIGHT_BOTTOM, LIGHT_PWM_HZ, 8);
  lights(0, 0);
}

// ---- MCP23017 ---------------------------------------------------------------------

bool Esp32Hal::mcpWrite(uint8_t addr, uint8_t reg, uint8_t a, uint8_t b) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(a);
  Wire.write(b);
  return Wire.endTransmission() == 0;
}

bool Esp32Hal::mcpRead(uint8_t addr, uint8_t reg, uint16_t &v) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)addr, (uint8_t)2) != 2) return false;
  uint8_t a = Wire.read();
  uint8_t b = Wire.read();
  v = (uint16_t)(a | (b << 8));
  return true;
}

void Esp32Hal::mcpInit() {
  bool ok = mcpWrite(MCP_OUT_ADDR, MCP_OLAT, outBits_ & 0xFF, outBits_ >> 8) &&
            mcpWrite(MCP_OUT_ADDR, MCP_IODIR, 0x00, 0x00) &&  // all outputs
            mcpWrite(MCP_IN_ADDR, MCP_OLAT, 0x00, 0x00) &&
            mcpWrite(MCP_IN_ADDR, MCP_IODIR, 0x7F, 0x7F) &&  // GPx0-6 in, GPx7 out (low)
            mcpWrite(MCP_IN_ADDR, MCP_GPPU, 0x7F, 0x7F);
  uint16_t v;
  ok = ok && mcpRead(MCP_IN_ADDR, MCP_GPIO, v);
  if (ok) {
    inBits_ = v;
    outSent_ = outBits_;
  }
  ioFault_ = !ok;
}

void Esp32Hal::poll() {
  uint32_t us = micros();
  if (us - lastPollUs_ >= IO_POLL_US) {
    lastPollUs_ = us;
    if (ioFault_) {
      if (::millis() - lastRetryMs_ >= 1000) {
        lastRetryMs_ = ::millis();
        mcpInit();
      }
    } else {
      uint16_t v;
      if (mcpRead(MCP_IN_ADDR, MCP_GPIO, v)) inBits_ = v;
      else ioFault_ = true;
      if (outBits_ != outSent_) {
        if (mcpWrite(MCP_OUT_ADDR, MCP_OLAT, outBits_ & 0xFF, outBits_ >> 8)) outSent_ = outBits_;
        else ioFault_ = true;
      }
    }
  }
  uint32_t ms = ::millis();
  if (ms - lastVacMs_ >= 2) {
    lastVacMs_ = ms;
    float v = analogReadMilliVolts(PIN_VAC_SENSE) / 1000.0f * VAC_DIVIDER;
    float kpa = (VAC_V_AT_ZERO - v) / (VAC_V_AT_ZERO - VAC_V_AT_FULL) * VAC_RANGE_KPA;
    vac_ += (kpa - vac_) * VAC_FILTER;
  }
}

// ---- Hal ----------------------------------------------------------------------------

uint32_t Esp32Hal::millis() { return ::millis(); }

void Esp32Hal::moveTo(Axis a, float mm, float speed, float accel) {
  FastAccelStepper *s = st[a];
  if (!s) return;
  uint32_t hz = (uint32_t)(speed * SPM[a]);
  s->setSpeedInHz(hz ? hz : 1);
  s->setAcceleration((int32_t)(accel * SPM[a]));
  s->moveTo((int32_t)lroundf(mm * SPM[a]));
}

void Esp32Hal::stop(Axis a, bool hard) {
  if (!st[a]) return;
  if (hard) st[a]->forceStop();
  else st[a]->stopMove();
}

bool Esp32Hal::moving(Axis a) { return st[a] && st[a]->isRunning(); }

float Esp32Hal::position(Axis a) { return st[a] ? st[a]->getCurrentPosition() / SPM[a] : 0; }

void Esp32Hal::zero(Axis a) {
  if (st[a]) st[a]->setCurrentPosition(0);
}

void Esp32Hal::enableMotors(bool on) { digitalWrite(PIN_STEPPER_EN, on ? LOW : HIGH); }

void Esp32Hal::setCurrent(Axis a, uint16_t mA) { tmc[a]->rms_current(mA, TMC_HOLD_MULT); }

void Esp32Hal::servo(ServoId s, uint8_t deg) {
  uint32_t us = SERVO_MIN_US + (uint32_t)(SERVO_MAX_US - SERVO_MIN_US) * deg / 180;
  pwmWrite(SERVO_PIN[s], SERVO_CH[s], us * ((1u << SERVO_BITS) - 1) / 20000);
}

void Esp32Hal::output(Output o, bool on) {
  if (o == OUT_SLEEVE_PICK) {  // DRV8833: on = IN1 1 / IN2 0 (forward), off = 1 / 1 (brake)
    outBits_ |= (uint16_t)(1u << MCPO_SLEEVE_PICK_IN1);
    uint16_t in2 = (uint16_t)(1u << MCPO_SLEEVE_PICK_IN2);
    outBits_ = on ? (outBits_ & ~in2) : (outBits_ | in2);
  } else {
    uint16_t bit = (uint16_t)(1u << MCP_OUT_BIT[o]);
    outBits_ = on ? (outBits_ | bit) : (outBits_ & ~bit);
  }
  if (!ioFault_ && outBits_ != outSent_) {
    if (mcpWrite(MCP_OUT_ADDR, MCP_OLAT, outBits_ & 0xFF, outBits_ >> 8)) outSent_ = outBits_;
    else ioFault_ = true;
  }
}

void Esp32Hal::lights(uint8_t top, uint8_t bottom) {
  pwmWrite(PIN_LIGHT_TOP, CH_LIGHT_TOP, top);
  pwmWrite(PIN_LIGHT_BOTTOM, CH_LIGHT_BOTTOM, bottom);
}

bool Esp32Hal::sensor(Sensor s) {
  auto mcp = [this](uint8_t bit, int active) { return (int)((inBits_ >> bit) & 1) == active; };
  switch (s) {
    case SN_SCAN_STOP: return digitalRead(PIN_SCAN_STOP) == ACTIVE_SCAN_STOP;
    case SN_SLEEVE_MOUTH: return digitalRead(PIN_SLEEVE_MOUTH) == ACTIVE_SLEEVE_MOUTH;
    case SN_DOUBLE_FEED: return digitalRead(PIN_DOUBLE_FEED) == ACTIVE_DOUBLE_FEED;
    case SN_ESTOP: return digitalRead(PIN_ESTOP) == ACTIVE_ESTOP;
    case SN_STACK_TOP: return mcp(MCPI_STACK_TOP, ACTIVE_STACK_TOP);
    case SN_SLEEVE_PRESENT: return mcp(MCPI_SLEEVE_PRESENT, ACTIVE_SLEEVE_PRESENT);
    case SN_EXIT: return mcp(MCPI_EXIT, ACTIVE_EXIT);
    case SN_ELEV_HOME: return mcp(MCPI_ELEV_HOME, ACTIVE_HOME);
    case SN_ELEV_LIMIT: return mcp(MCPI_ELEV_LIMIT, ACTIVE_HOME);
    case SN_PICK_HOME: return mcp(MCPI_PICK_HOME, ACTIVE_HOME);
    case SN_TONGUE_HOME: return mcp(MCPI_TONGUE_HOME, ACTIVE_HOME);
    case SN_MAG_LOW: return mcp(MCPI_MAG_LOW, ACTIVE_MAG);
    case SN_MAG_EMPTY: return mcp(MCPI_MAG_EMPTY, ACTIVE_MAG);
    case SN_LID_OPEN: return ioFault_ || mcp(MCPI_LID, ACTIVE_LID_OPEN);  // lost expander = unsafe
    default: return false;
  }
}

}  // namespace cs
