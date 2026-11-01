#pragma once
// Physics model of the card scanner behind the Hal interface.  Used by the
// native unit tests and by the `sim` env (a stdin/stdout firmware stand-in for
// host development, see tools/mcu_sim.py).  Simple on purpose: constant-speed
// axes, one card in flight, first-order vacuum, seeded fault injection.

#include <stdint.h>

#include "cs_hal.h"

namespace cs {

struct SimConfig {
  int hopperCards = 50;
  int sleeves = 100;
  float cardThick = 0.32f;
  float stackSensorAt = 145;  // elevator pos + stack height that reaches stack_top
  float elevLimitAt = 150;
  float elevStart = 20, pickStart = 4, tongueStart = 2;  // true positions at power-up
  // card path: leading edge, mm from the pick point
  float nipAt = 22;       // a card released past here is carried by the feed rollers (CAD: edge 44 -> nip 66)
  float doubleAt = 60;    // double-feed gauge
  float scanAt = 120;     // scan_stop lever
  float mouthAt = 160;    // sleeve_mouth beam
  float platenAt = 190;   // leading edge past here = card on the platen, pushable
  float cardLen = 88;
  float vacMax = 60;      // kPa with every open cup sealed
  float vacLeak = 4;      // kPa with an open, unsealed cup
  float vacTauMs = 60;
  uint32_t pushMs = 250;  // pusher out -> card into the chute
  uint32_t exitBeamMs = 150;
  uint32_t sleevePickMs = 250;  // pick wheels on this long -> bottom sleeve against the fence
  uint8_t seatDeg = 40;         // pusher at/above this (and below the push angle 120) seats the card
  // fault injection, probability per event (0-1)
  float pDouble = 0, pPickFail = 0, pLiftFail = 0, pExitMiss = 0, pSleevePickFail = 0;
  uint32_t seed = 1;
};

class SimHal : public Hal {
 public:
  explicit SimHal(const SimConfig &cfg = SimConfig());

  // Hal
  uint32_t millis() override { return now_; }
  void moveTo(Axis a, float mm, float speed, float accel) override;
  void stop(Axis a, bool hard) override;
  bool moving(Axis a) override { return pos_[a] != target_[a]; }
  float position(Axis a) override { return pos_[a] - offset_[a]; }
  void zero(Axis a) override { offset_[a] = pos_[a]; }
  void enableMotors(bool on) override;
  void setCurrent(Axis a, uint16_t mA) override { current_[a] = mA; }
  void servo(ServoId s, uint8_t deg) override;
  void output(Output o, bool on) override {
    if (o == OUT_SLEEVE_PICK && on && !out_[o]) pickRunMs_ = 0;  // a new run, even with no tick between
    out_[o] = on;
  }
  void lights(uint8_t top, uint8_t bottom) override {
    lightTop = top;
    lightBottom = bottom;
  }
  bool sensor(Sensor s) override;
  float vacuumKpa() override { return vac_; }

  // simulation
  void advance(uint32_t ms);  // physics in 1 ms steps
  SimConfig cfg;
  bool estop = false, lidOpen = false;
  bool forceSensor[SN_COUNT] = {};  // test hooks: stuck-active sensors
  int hopper;                       // cards left in the stack
  int sleeves;                      // sleeves left in the magazine
  int binCount[3] = {0, 0, 0};
  int sleevedCards = 0;             // cards that left with a sleeve on
  uint8_t lightTop = 0, lightBottom = 0;
  uint16_t current_[AX_COUNT] = {};
  bool out_[OUT_COUNT] = {};
  uint8_t servo_[SV_COUNT] = {};
  bool enabled = false;
  float truePos(Axis a) const { return pos_[a]; }
  bool sleeveOnPlaten() const { return sleeveOnPlaten_; }
  bool platenCardSleeved() const { return platen_ && platenSleeved_; }

 private:
  enum CardState : uint8_t { C_NONE, C_ON_CUP, C_IN_PATH };
  void step1ms();
  bool roll(float p);
  bool cardAt(float from, float len) const;

  uint32_t now_ = 0;
  float pos_[AX_COUNT], target_[AX_COUNT], speed_[AX_COUNT], offset_[AX_COUNT];
  float vac_ = 0;
  uint32_t rng_;
  // the card in flight (hopper -> rollers -> scan station -> sleeve)
  CardState card_ = C_NONE;
  float cardX_ = 0;
  bool cardDouble_ = false, cardSleeved_ = false, pickSealFail_ = false, pickWasOpen_ = false;
  // the card resting on the platen, waiting for the pusher
  bool platen_ = false, platenSleeved_ = false, platenSeated_ = false;
  float platenX_ = 0;
  // the card dropping through the exit beam
  bool falling_ = false, fallSleeved_ = false;
  bool liftHolding_ = false, liftTried_ = false;
  uint32_t pushT0_ = 0, fallT0_ = 0;
  bool pushing_ = false, exitMiss_ = false;
  // the sleeve picked onto the platen, and the pick wheel run time
  bool sleeveOnPlaten_ = false, pickMiss_ = false;
  uint32_t pickRunMs_ = 0;
};

}  // namespace cs
