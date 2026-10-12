#include "motor.h"

#include <AccelStepper.h>
#include <Arduino.h>
#include <esp_timer.h>

#include "config.h"

// HALF4WIRE wants the coils in IN1-IN3-IN2-IN4 order for the 28BYJ-48
static AccelStepper stepper(AccelStepper::HALF4WIRE, PIN_STEP_IN1, PIN_STEP_IN3, PIN_STEP_IN2,
                            PIN_STEP_IN4, false);
static portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
static esp_timer_handle_t timer;
static volatile bool powered = false;
static bool stopping = false;  // stop() issued, decelerating
static uint16_t lastSpeed = 0;

static void powerOff() {
  stepper.disableOutputs();  // all four coils low: no holding current, no heat
  powered = false;
  stopping = false;
}

// esp_timer task context (not an ISR), so AccelStepper's float math is fine
static void tick(void *) {
  portENTER_CRITICAL(&mux);
  if (powered) {
    stepper.run();
    if (stepper.distanceToGo() == 0 && stepper.speed() == 0) powerOff();
  }
  portEXIT_CRITICAL(&mux);
}

void motor::begin() {
  stepper.enableOutputs();  // pinMode OUTPUT
  powerOff();
  stepper.setAcceleration(MOTOR_ACCEL);
  stepper.setMaxSpeed(MOTOR_SPEED_DEFAULT);
  lastSpeed = MOTOR_SPEED_DEFAULT;

  esp_timer_create_args_t args = {};
  args.callback = tick;
  args.name = "stepper";
  esp_timer_create(&args, &timer);
  esp_timer_start_periodic(timer, STEPPER_TICK_US);
}

void motor::command(int32_t target, bool halt, uint16_t maxSpeed) {
  portENTER_CRITICAL(&mux);
  if (maxSpeed != lastSpeed) {
    stepper.setMaxSpeed(maxSpeed);
    lastSpeed = maxSpeed;
  }
  const int32_t pos = stepper.currentPosition();
  if (halt) {
    if (powered) {
      stepper.setCurrentPosition(pos);  // speed 0, target = here
      powerOff();
    }
  } else if ((int32_t)((uint32_t)target - (uint32_t)pos) > 0) {
    if (!powered) {
      stepper.enableOutputs();
      powered = true;
    }
    if (stepper.targetPosition() != target) {
      stepper.moveTo(target);
      stopping = false;
    }
  } else if (powered && !stopping && stepper.distanceToGo() != 0) {
    if (stepper.speed() == 0) {  // not moving yet: just cancel
      stepper.setCurrentPosition(pos);
      powerOff();
    } else {
      stepper.stop();  // decelerate forward, never reverse
      stopping = true;
    }
  }
  portEXIT_CRITICAL(&mux);
}

int32_t motor::position() {
  portENTER_CRITICAL(&mux);
  int32_t p = stepper.currentPosition();
  portEXIT_CRITICAL(&mux);
  return p;
}

bool motor::energised() { return powered; }
