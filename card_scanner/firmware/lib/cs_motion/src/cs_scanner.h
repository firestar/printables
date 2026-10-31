#pragma once
// The motion controller: host command handling + non-blocking sequencer.
//
// handleLine() takes one JSON request line.  Quick commands (ping, status,
// lights, set, get, estop, reset) reply at once.  Motion commands (home, feed,
// sleeve, sort, eject_reject) start a job and reply when the job ends; only one
// job runs at a time, the rest of the protocol keeps working while it does.
// tick() advances the job; it never blocks and must be called every loop pass.

#include <stdint.h>

#include "cs_hal.h"
#include "cs_json.h"
#include "cs_proto.h"
#include "cs_settings.h"

namespace cs {

class LineSink {
 public:
  virtual ~LineSink() {}
  virtual void sendLine(const char *line) = 0;  // one JSON object, no '\n'
};

enum State : uint8_t {
  ST_UNHOMED,
  ST_IDLE,
  ST_HOMING,
  ST_FEEDING,
  ST_SLEEVING,
  ST_SORTING,
  ST_EJECTING,
  ST_ESTOP,
};
const char *stateName(State s);

class Scanner {
 public:
  Scanner(Hal &hal, LineSink &out, SettingsStore *store, const char *fwVersion);
  void begin();
  void handleLine(const char *line);
  void tick();

  State state() const;
  bool homed() const { return homed_; }
  bool busy() const { return job_ != JOB_NONE; }
  bool sleevedCardOnPlaten() const { return sleeved_; }
  const Settings &settings() const { return s_; }

 private:
  enum Job : uint8_t { JOB_NONE, JOB_HOME, JOB_FEED, JOB_SLEEVE, JOB_SORT, JOB_REJECT };
  struct Debounce {
    bool stable = false, raw = false;
    uint32_t since = 0;
  };

  // commands
  void cmdStatus(int32_t id);
  void cmdLights(int32_t id, const JsonObject &req);
  void cmdSet(int32_t id, const JsonObject &req);
  void cmdGet(int32_t id, const JsonObject &req);
  void cmdReset(int32_t id);
  void cmdHome(int32_t id);
  void cmdFeed(int32_t id);
  void cmdSleeve(int32_t id);
  void cmdSort(int32_t id, const JsonObject &req, bool reject);
  bool canStart(int32_t id, bool needHome);

  // job plumbing
  void startJob(Job j, int32_t id);
  void enter(uint8_t phase, uint32_t timeoutMs);
  uint32_t elapsed();
  bool expired();
  void finishOk();
  void failJob(Err e, const char *msg, bool needHome);
  void step();
  void stepHome();
  void stepFeed();
  void stepSleeve();
  void stepSort();

  // helpers
  void startHomeAxis();
  void startPuff();
  void startGrip();
  void startPush();
  void feedWatch();
  void startPlaten();
  bool gripped();
  uint32_t vacTimeout();
  uint32_t motionMs(float mm, float speed);
  void moveRel(Axis a, float mm, float speed);
  void moveAbs(Axis a, float mm, float speed);
  void stopAll(bool hard);
  void pneumaticsOff();
  uint8_t divAngle(uint8_t bin);
  void applyCurrents();
  void enterEstop(const char *source, bool emitEvent);
  bool debounce(Debounce &d, bool raw, uint32_t now);

  // output
  void send(JsonWriter &w);
  void replyOk(int32_t id);
  void replyErr(int32_t id, Err e, const char *msg);
  void event(const char *name, const char *key = nullptr, const char *val = nullptr);

  Hal &hal_;
  LineSink &out_;
  SettingsStore *store_;
  const char *fw_;
  Settings s_;

  Job job_ = JOB_NONE;
  int32_t jobId_ = 0;
  uint8_t phase_ = 0;
  uint32_t t0_ = 0;
  uint32_t timeout_ = 0;
  uint8_t homeIdx_ = 0;
  uint8_t bin_ = 0;

  bool homed_ = false;
  bool estop_ = false;
  bool hopperEmpty_ = false;
  bool sleeved_ = false;     // a sleeved card waits on the platen for `sort`
  bool doubleSeen_ = false;
  bool sleeveStaged_ = false;  // a picked sleeve passed the platen check and is still unused
  bool scanHit_ = false;
  bool mouthSeen_ = false;
  uint8_t lightTop_ = 0, lightBottom_ = 0;

  Debounce estopIn_, lidIn_, magLowIn_;
};

}  // namespace cs
