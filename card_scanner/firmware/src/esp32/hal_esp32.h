#pragma once
// cs::Hal on the ESP32-S3: FastAccelStepper (RMT step generation), TMC2209
// over UART1, LEDC servos + light PWM, two MCP23017s on I2C, ADC vacuum sensor.

#include "cs_hal.h"

namespace cs {

class Esp32Hal : public Hal {
 public:
  void begin();
  void poll();  // every loop pass: expander inputs, vacuum filter, output flush

  uint32_t millis() override;
  void moveTo(Axis a, float mm, float speed, float accel) override;
  void stop(Axis a, bool hard) override;
  bool moving(Axis a) override;
  float position(Axis a) override;
  void zero(Axis a) override;
  void enableMotors(bool on) override;
  void setCurrent(Axis a, uint16_t mA) override;
  void servo(ServoId s, uint8_t deg) override;
  void output(Output o, bool on) override;
  void lights(uint8_t top, uint8_t bottom) override;
  bool sensor(Sensor s) override;
  float vacuumKpa() override { return vac_; }

 private:
  bool mcpWrite(uint8_t addr, uint8_t reg, uint8_t a, uint8_t b);
  bool mcpRead(uint8_t addr, uint8_t reg, uint16_t &v);
  void mcpInit();
  uint16_t outBits_ = 0, outSent_ = 0xFFFF;
  uint16_t inBits_ = 0xFFFF;
  bool ioFault_ = true;  // expander missing: inputs fail safe (lid open)
  uint32_t lastPollUs_ = 0, lastVacMs_ = 0, lastRetryMs_ = 0;
  float vac_ = 0;
};

}  // namespace cs
