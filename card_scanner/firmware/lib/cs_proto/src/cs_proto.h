#pragma once
// Host link vocabulary shared by the firmware, the simulator and the tests.
// The wire format is described in PROTOCOL.md.

#include <stdint.h>

namespace cs {

static const int LINE_MAX_LEN = 256;  // longest accepted host->MCU line, bytes (without '\n')
static const int REPLY_MAX_LEN = 640; // longest MCU->host line

enum Err : uint8_t {
  ERR_NONE,
  ERR_HOPPER_EMPTY,
  ERR_MAGAZINE_EMPTY,
  ERR_DOUBLE_FEED,
  ERR_PICK_FAIL,
  ERR_JAM,
  ERR_SLEEVE_OPEN_FAIL,
  ERR_SLEEVE_INSERT_FAIL,
  ERR_EXIT_TIMEOUT,
  ERR_ESTOP,
  ERR_NOT_HOMED,
  ERR_BUSY,
  ERR_BAD_CMD,
};

inline const char *errName(Err e) {
  switch (e) {
    case ERR_NONE: return "none";
    case ERR_HOPPER_EMPTY: return "hopper_empty";
    case ERR_MAGAZINE_EMPTY: return "magazine_empty";
    case ERR_DOUBLE_FEED: return "double_feed";
    case ERR_PICK_FAIL: return "pick_fail";
    case ERR_JAM: return "jam";
    case ERR_SLEEVE_OPEN_FAIL: return "sleeve_open_fail";
    case ERR_SLEEVE_INSERT_FAIL: return "sleeve_insert_fail";
    case ERR_EXIT_TIMEOUT: return "exit_timeout";
    case ERR_ESTOP: return "estop";
    case ERR_NOT_HOMED: return "not_homed";
    case ERR_BUSY: return "busy";
    case ERR_BAD_CMD: return "bad_cmd";
  }
  return "bad_cmd";
}

}  // namespace cs
