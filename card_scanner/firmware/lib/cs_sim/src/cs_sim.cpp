#include "cs_sim.h"

#include <math.h>

namespace cs {

SimHal::SimHal(const SimConfig &c) : cfg(c), hopper(c.hopperCards), sleeves(c.sleeves), rng_(c.seed ? c.seed : 1) {
  for (int i = 0; i < AX_COUNT; i++) pos_[i] = target_[i] = speed_[i] = offset_[i] = 0;
  pos_[AX_ELEV] = target_[AX_ELEV] = cfg.elevStart;
  pos_[AX_PICK] = target_[AX_PICK] = cfg.pickStart;
  pos_[AX_TONGUE] = target_[AX_TONGUE] = cfg.tongueStart;
}

bool SimHal::roll(float p) {
  if (p <= 0) return false;
  rng_ = rng_ * 1664525u + 1013904223u;
  return (float)(rng_ >> 8) / 16777216.0f < p;
}

void SimHal::moveTo(Axis a, float mm, float speed, float) {
  if (!enabled) return;
  target_[a] = mm + offset_[a];
  speed_[a] = speed;
}

void SimHal::stop(Axis a, bool) { target_[a] = pos_[a]; }

void SimHal::enableMotors(bool on) {
  enabled = on;
  if (!on)
    for (int i = 0; i < AX_COUNT; i++) target_[i] = pos_[i];
}

void SimHal::servo(ServoId s, uint8_t deg) {
  if (s == SV_PUSHER) {
    bool out = deg >= 120;
    if (out && !pushing_) {
      pushT0_ = now_;
      exitMiss_ = roll(cfg.pExitMiss);
    }
    pushing_ = out;
  }
  servo_[s] = deg;
}

// Card body over a sensor at `from`: leading edge past it, trailing edge not yet.
bool SimHal::cardAt(float from, float len) const {
  bool inFlight = card_ != C_NONE && cardX_ >= from && cardX_ < from + len;
  bool onPlaten = platen_ && platenX_ >= from && platenX_ < from + len;
  return inFlight || onPlaten;
}

bool SimHal::sensor(Sensor s) {
  if (s < SN_COUNT && forceSensor[s]) return true;
  switch (s) {
    case SN_STACK_TOP: return hopper > 0 && pos_[AX_ELEV] + hopper * cfg.cardThick >= cfg.stackSensorAt;
    case SN_DOUBLE_FEED: return card_ != C_NONE && cardDouble_ && cardX_ >= cfg.doubleAt &&
                                cardX_ < cfg.doubleAt + cfg.cardLen;
    case SN_SCAN_STOP: return cardAt(cfg.scanAt, cfg.cardLen);
    case SN_SLEEVE_PRESENT: return sleeveOnPlaten_;
    case SN_SLEEVE_MOUTH: return cardAt(cfg.mouthAt, cfg.cardLen);
    case SN_EXIT: return falling_;
    case SN_ELEV_HOME: return pos_[AX_ELEV] <= 0;
    case SN_ELEV_LIMIT: return pos_[AX_ELEV] >= cfg.elevLimitAt;
    case SN_PICK_HOME: return pos_[AX_PICK] <= 0;
    case SN_TONGUE_HOME: return pos_[AX_TONGUE] <= 0;
    case SN_MAG_LOW: return sleeves <= 10;
    case SN_MAG_EMPTY: return sleeves <= 0;
    case SN_ESTOP: return estop;
    case SN_LID_OPEN: return lidOpen;
    default: return false;
  }
}

void SimHal::advance(uint32_t ms) {
  for (uint32_t i = 0; i < ms; i++) step1ms();
}

void SimHal::step1ms() {
  now_++;
  float feedBefore = pos_[AX_FEED];
  for (int i = 0; i < AX_COUNT; i++) {
    float d = target_[i] - pos_[i];
    float stepMm = speed_[i] / 1000.0f;
    if (fabsf(d) <= stepMm) pos_[i] = target_[i];
    else pos_[i] += d > 0 ? stepMm : -stepMm;
  }
  float feedDelta = pos_[AX_FEED] - feedBefore;

  // pick cup: grabs the top card when it opens over the stack
  bool pickOpen = out_[OUT_VAC_PUMP] && out_[OUT_PICK_CUP];
  if (pickOpen && !pickWasOpen_) pickSealFail_ = roll(cfg.pPickFail);
  pickWasOpen_ = pickOpen;
  if (card_ == C_NONE && pickOpen && !pickSealFail_ && sensor(SN_STACK_TOP) && pos_[AX_PICK] <= 1.0f) {
    card_ = C_ON_CUP;
    hopper--;
    cardDouble_ = roll(cfg.pDouble);
    cardSleeved_ = false;
    if (cardDouble_ && hopper > 0) hopper--;  // the second card rides along
  }

  // sleeve pick wheels: a long enough run slides the bottom sleeve onto the platen
  if (out_[OUT_SLEEVE_PICK]) {
    if (pickRunMs_++ == 0) pickMiss_ = roll(cfg.pSleevePickFail);
    if (pickRunMs_ >= cfg.sleevePickMs && !sleeveOnPlaten_ && sleeves > 0 && !pickMiss_) {
      sleeves--;
      sleeveOnPlaten_ = true;
    }
  } else {
    pickRunMs_ = 0;
  }

  // lift cup: holds the top ply if it opened with the cup down on a sleeve
  if (out_[OUT_LIFT_CUP] && !liftTried_) {
    liftTried_ = true;
    liftHolding_ = servo_[SV_LIFT] <= 60 && sleeveOnPlaten_ && !roll(cfg.pLiftFail);
  } else if (!out_[OUT_LIFT_CUP]) {
    liftTried_ = false;
    liftHolding_ = false;
  }

  switch (card_) {
    case C_ON_CUP:
      cardX_ = pos_[AX_PICK];
      if (cardX_ >= cfg.nipAt) {
        card_ = C_IN_PATH;  // the rollers take over
      } else if (!pickOpen) {
        card_ = C_NONE;  // dropped back onto the stack
        hopper += cardDouble_ ? 2 : 1;
        cardDouble_ = false;
      }
      break;
    case C_IN_PATH: {
      float before = cardX_;
      cardX_ += feedDelta;
      float mark = cfg.mouthAt + 10;
      if (before < mark && cardX_ >= mark && liftHolding_ && out_[OUT_PLATEN] && pos_[AX_TONGUE] >= 10)
        cardSleeved_ = true;
      if (cardX_ >= cfg.platenAt && feedDelta == 0 && !platen_) {
        platen_ = true;  // out of the rollers, resting on the platen
        platenSleeved_ = cardSleeved_;
        platenSeated_ = false;
        platenX_ = cardX_;
        card_ = C_NONE;
        cardDouble_ = cardSleeved_ = false;
      }
      break;
    }
    case C_NONE: break;
  }

  // a sleeved card is only ~70 mm in: the pawl must seat it before the tongues come out,
  // or the closing mouth pulls the sleeve off with them
  if (platen_ && platenSleeved_ && !platenSeated_) {
    if (pos_[AX_TONGUE] >= 10 && servo_[SV_PUSHER] >= cfg.seatDeg && servo_[SV_PUSHER] < 120) platenSeated_ = true;
    else if (pos_[AX_TONGUE] < 10) platenSleeved_ = false;
  }

  // pusher sweeps the platen card into the diverter chute
  if (pushing_ && !exitMiss_ && platen_ && !falling_ && now_ - pushT0_ >= cfg.pushMs) {
    platen_ = false;
    falling_ = true;
    fallSleeved_ = platenSleeved_;
    fallT0_ = now_;
  }
  if (falling_ && now_ - fallT0_ >= cfg.exitBeamMs) {
    falling_ = false;
    sleeveOnPlaten_ = false;  // the pawl swept the platen clear
    uint8_t d = servo_[SV_DIVERTER];
    binCount[d < 60 ? 0 : d < 120 ? 1 : 2]++;
    if (fallSleeved_) sleevedCards++;
  }

  // vacuum: first order toward the target
  float targetVac = 0;
  if (out_[OUT_VAC_PUMP]) {
    bool leak = (out_[OUT_PICK_CUP] && card_ != C_ON_CUP) || (out_[OUT_PLATEN] && !sleeveOnPlaten_) ||
                (out_[OUT_LIFT_CUP] && !liftHolding_);
    targetVac = leak ? cfg.vacLeak : cfg.vacMax;
  }
  vac_ += (targetVac - vac_) * (1.0f / cfg.vacTauMs);
}

}  // namespace cs
