#pragma once
// Hardware abstraction for the motion controller.  The sequencer (cs_scanner)
// only talks to this interface: src/esp32 implements it on the real board,
// lib/cs_sim implements it as a physics model for the tests and the simulator.

#include <stdint.h>

namespace cs {

enum Axis : uint8_t { AX_ELEV, AX_PICK, AX_FEED, AX_TONGUE, AX_COUNT };

enum ServoId : uint8_t { SV_LIFT, SV_PUSHER, SV_DIVERTER, SV_COUNT };

// On/off loads.  Valves are normally closed: on = open = vacuum/air flows.
enum Output : uint8_t {
  OUT_VAC_PUMP,    // 12 V vacuum pump
  OUT_PICK_CUP,    // valve: pick arm suction cup
  OUT_PLATEN,      // valve: sleeve platen (holds the bottom ply)
  OUT_LIFT_CUP,    // valve: lift cup (holds the top ply)
  OUT_PUFF_PUMP,   // 12 V air pump
  OUT_STACK_PUFF,  // valve: air knife at the hopper stack top
  OUT_MOUTH_JET,   // valve: air jet into the sleeve mouth
  OUT_SLEEVE_PICK, // N20 sleeve-pick wheels (DRV8833): on = forward, off = brake
  OUT_COUNT
};

// Logical sensor state: true = "active" as named (polarity is the HAL's job).
enum Sensor : uint8_t {
  SN_STACK_TOP,     // top card at the pick height
  SN_DOUBLE_FEED,   // more than one card thickness under the gauge
  SN_SCAN_STOP,     // card at the scan station
  SN_SLEEVE_PRESENT,// sleeve on the platen, against the fence
  SN_SLEEVE_MOUTH,  // beam at the sleeve mouth broken
  SN_EXIT,          // beam below the diverter broken
  SN_ELEV_HOME,     // elevator at the bottom
  SN_ELEV_LIMIT,    // elevator at the top
  SN_PICK_HOME,     // pick arm retracted
  SN_TONGUE_HOME,   // tongue retracted
  SN_MAG_LOW,       // sleeve magazine low
  SN_MAG_EMPTY,     // sleeve magazine empty
  SN_ESTOP,         // e-stop pressed (or its wire cut)
  SN_LID_OPEN,      // lid open (or its wire cut / IO expander lost)
  SN_COUNT
};

const char *axisName(Axis a);
const char *sensorName(Sensor s);  // status JSON keys

class Hal {
 public:
  virtual ~Hal() {}
  virtual uint32_t millis() = 0;

  // Steppers, in mm from the axis zero.  moveTo may retarget a running move.
  virtual void moveTo(Axis a, float mm, float speedMmS, float accelMmS2) = 0;
  virtual void stop(Axis a, bool hard) = 0;  // hard = no ramp (sensor stops)
  virtual bool moving(Axis a) = 0;
  virtual float position(Axis a) = 0;
  virtual void zero(Axis a) = 0;  // current position := 0 (axis stopped)
  virtual void enableMotors(bool on) = 0;
  virtual void setCurrent(Axis a, uint16_t mARms) = 0;

  virtual void servo(ServoId s, uint8_t deg) = 0;
  virtual void output(Output o, bool on) = 0;
  virtual void lights(uint8_t top, uint8_t bottom) = 0;

  virtual bool sensor(Sensor s) = 0;
  virtual float vacuumKpa() = 0;  // vacuum below ambient, kPa (0 = none, positive = suction)
};

}  // namespace cs
