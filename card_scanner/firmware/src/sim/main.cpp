// Firmware stand-in for host development: the real cs::Scanner on the SimHal
// physics model, speaking the host protocol on stdin/stdout in real time.
//
//   pio run -e sim            -> .pio/build/sim/program
//   python3 tools/mcu_sim.py  -> wraps it in a pseudo-terminal the host opens like /dev/ttyACM0
//
// Options: --speed X (time scale), --hopper N, --sleeves N, --seed N,
//          --double P, --pick-fail P, --lift-fail P, --exit-miss P, --sleeve-pick-fail P  (fault probabilities 0-1)
// Sim control lines on stdin start with '#' (acknowledged on stderr, never on stdout):
//   #estop 1|0   #lid 1|0   #hopper N   #sleeves N   #double P   #pick-fail P
//   #lift-fail P   #exit-miss P   #sleeve-pick-fail P   #state

#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <chrono>
#include <string>

#include "config.h"
#include "cs_scanner.h"
#include "cs_sim.h"

namespace {

struct StdoutSink : cs::LineSink {
  void sendLine(const char *line) override {
    fputs(line, stdout);
    fputc('\n', stdout);
    fflush(stdout);
  }
};

void control(cs::SimHal &hal, const char *cmd) {
  char name[32] = {0};
  double v = 0;
  int n = sscanf(cmd, "#%31s %lf", name, &v);
  std::string k = name;
  if (n >= 1 && k == "state") {
    fprintf(stderr, "sim: hopper=%d sleeves=%d bins=%d/%d/%d sleeved=%d estop=%d lid=%d\n", hal.hopper,
            hal.sleeves, hal.binCount[0], hal.binCount[1], hal.binCount[2], hal.sleevedCards, hal.estop,
            hal.lidOpen);
    return;
  }
  if (n < 2) {
    fprintf(stderr, "sim: bad control line: %s\n", cmd);
    return;
  }
  if (k == "estop") hal.estop = v != 0;
  else if (k == "lid") hal.lidOpen = v != 0;
  else if (k == "hopper") hal.hopper = (int)v;
  else if (k == "sleeves") hal.sleeves = (int)v;
  else if (k == "double") hal.cfg.pDouble = (float)v;
  else if (k == "pick-fail") hal.cfg.pPickFail = (float)v;
  else if (k == "lift-fail") hal.cfg.pLiftFail = (float)v;
  else if (k == "exit-miss") hal.cfg.pExitMiss = (float)v;
  else if (k == "sleeve-pick-fail") hal.cfg.pSleevePickFail = (float)v;
  else {
    fprintf(stderr, "sim: unknown control: %s\n", name);
    return;
  }
  fprintf(stderr, "sim: %s = %g\n", name, v);
}

}  // namespace

int main(int argc, char **argv) {
  cs::SimConfig cfg;
  double speed = 1.0;
  for (int i = 1; i + 1 < argc; i += 2) {
    std::string k = argv[i];
    double v = atof(argv[i + 1]);
    if (k == "--speed") speed = v > 0 ? v : 1.0;
    else if (k == "--hopper") cfg.hopperCards = (int)v;
    else if (k == "--sleeves") cfg.sleeves = (int)v;
    else if (k == "--seed") cfg.seed = (uint32_t)v;
    else if (k == "--double") cfg.pDouble = (float)v;
    else if (k == "--pick-fail") cfg.pPickFail = (float)v;
    else if (k == "--lift-fail") cfg.pLiftFail = (float)v;
    else if (k == "--exit-miss") cfg.pExitMiss = (float)v;
    else if (k == "--sleeve-pick-fail") cfg.pSleevePickFail = (float)v;
    else {
      fprintf(stderr, "unknown option %s\n", argv[i]);
      return 2;
    }
  }

  cs::SimHal hal(cfg);
  StdoutSink sink;
  cs::Scanner scanner(hal, sink, nullptr, FW_VERSION "-sim");
  scanner.begin();
  fprintf(stderr, "sim: card scanner firmware %s-sim ready (speed x%g)\n", FW_VERSION, speed);

  using clock = std::chrono::steady_clock;
  auto t0 = clock::now();
  double simMs = 0;
  std::string buf;
  char rd[512];
  for (;;) {
    struct pollfd p = {0, POLLIN, 0};
    if (poll(&p, 1, 1) > 0) {
      ssize_t n = read(0, rd, sizeof(rd));
      if (n <= 0) break;  // host closed stdin
      buf.append(rd, (size_t)n);
      size_t nl;
      while ((nl = buf.find('\n')) != std::string::npos) {
        std::string line = buf.substr(0, nl);
        buf.erase(0, nl + 1);
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (!line.empty() && line[0] == '#') control(hal, line.c_str());
        else if (line.size() > (size_t)cs::LINE_MAX_LEN)
          sink.sendLine("{\"id\":-1,\"ok\":false,\"err\":\"bad_cmd\",\"msg\":\"line too long\"}");
        else scanner.handleLine(line.c_str());
      }
    }
    double target = std::chrono::duration<double, std::milli>(clock::now() - t0).count() * speed;
    while (simMs + 1 <= target) {
      hal.advance(1);
      scanner.tick();
      simMs += 1;
    }
  }
  return 0;
}
