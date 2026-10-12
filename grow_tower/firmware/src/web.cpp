// Web UI (single PROGMEM page) and JSON REST API.
//
//   GET  /             UI
//   GET  /api/status   live state
//   GET  /api/config   settings
//   POST /api/config   partial settings update (JSON), saved to NVS
//   POST /api/manual   {"target":"pump|motor","state":"on|off|auto","minutes":N}
//                      {"action":"rotate","degrees":N} | {"action":"home"}
//                      {"action":"clear_faults"}

#include "web.h"

#include <ArduinoJson.h>
#include <WebServer.h>
#include <WiFi.h>

#include "app.h"
#include "config.h"

static WebServer server(HTTP_PORT);

static const char INDEX_HTML[] PROGMEM = R"HTML(<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Grow tower</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#f3f6f1;color:#1d2a1d}
header{background:#2f6b3a;color:#fff;padding:.8em 1em;font-size:1.2em}
main{max-width:760px;margin:auto;padding:1em}
section{background:#fff;border-radius:8px;padding:1em;margin-bottom:1em;box-shadow:0 1px 3px #0002}
h2{margin:.1em 0 .6em;font-size:1.05em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.5em}
.k{font-size:.8em;color:#5a6b5a}.v{font-size:1.1em;font-weight:600}
.bad{color:#b3261e}.ok{color:#2f6b3a}
label{display:flex;justify-content:space-between;align-items:center;gap:1em;margin:.35em 0}
input,select,button{font:inherit;padding:.3em .5em}
input[type=number]{width:6em}
button{border:0;border-radius:6px;background:#2f6b3a;color:#fff;cursor:pointer;margin:.15em}
button.alt{background:#6b7a6b}
.row{display:flex;flex-wrap:wrap;align-items:center;gap:.4em;margin:.3em 0}
fieldset{border:1px solid #ccd6cc;border-radius:6px;margin:.6em 0}
.hint{font-size:.85em;color:#5a6b5a}
#msg{margin-left:.5em}
</style></head><body>
<header>Grow tower <small id="conn"></small></header>
<main>
<section><h2>Status</h2><div class="grid" id="st"></div></section>
<section><h2>Manual control</h2>
<div class="row">Override duration <input type="number" id="mmin" min="1" max="240" value="10"> min</div>
<div class="row"><b style="width:4em">Pump</b>
<button onclick="man('pump','on')">On</button><button onclick="man('pump','off')">Off</button>
<button class="alt" onclick="man('pump','auto')">Auto</button></div>
<div class="row"><b style="width:4em">Tower</b>
<button onclick="man('motor','on')">Turn</button><button onclick="man('motor','off')">Hold</button>
<button class="alt" onclick="man('motor','auto')">Auto</button></div>
<div class="row"><b style="width:4em">Rotate</b>
<button onclick="act({action:'rotate',degrees:15})">+15°</button>
<button onclick="act({action:'rotate',degrees:90})">+90°</button>
<button onclick="act({action:'rotate',degrees:360})">+1 rev</button>
<button class="alt" id="homeb" onclick="act({action:'home'})">Home</button></div>
<div class="row"><button class="alt" onclick="act({action:'clear_faults'})">Clear alerts / faults</button></div>
</section>
<section><h2>Settings</h2><form id="cfg" onsubmit="save(event)">
<fieldset><legend>Day window</legend>
<label>Day starts <input type="time" name="day_start" required></label>
<label>Day ends <input type="time" name="day_end" required></label>
<label>Time zone <select id="tzsel" onchange="tzChanged()">
<option value="UTC0">UTC</option>
<option value="GMT0BST,M3.5.0/1,M10.5.0">UK / Ireland</option>
<option value="WET0WEST,M3.5.0/1,M10.5.0">Portugal (WET)</option>
<option value="CET-1CEST,M3.5.0,M10.5.0/3">Central Europe</option>
<option value="EET-2EEST,M3.5.0/3,M10.5.0/4">Eastern Europe</option>
<option value="IST-5:30">India</option>
<option value="JST-9">Japan</option>
<option value="AWST-8">Australia West</option>
<option value="AEST-10AEDT,M10.1.0,M4.1.0/3">Australia East</option>
<option value="NZST-12NZDT,M9.5.0,M4.1.0/3">New Zealand</option>
<option value="HST10">US Hawaii</option>
<option value="AKST9AKDT,M3.2.0,M11.1.0">US Alaska</option>
<option value="PST8PDT,M3.2.0,M11.1.0">US Pacific</option>
<option value="MST7">US Arizona</option>
<option value="MST7MDT,M3.2.0,M11.1.0">US Mountain</option>
<option value="CST6CDT,M3.2.0,M11.1.0">US Central</option>
<option value="EST5EDT,M3.2.0,M11.1.0">US Eastern</option>
<option value="custom">Other (POSIX TZ string)</option>
</select></label>
<label id="tzrow" hidden>POSIX TZ <input name="tz" maxlength="63"></label>
</fieldset>
<fieldset><legend>Pump cycle (minutes)</legend>
<label>Day ON <input type="number" name="day_on_min" min="0" max="1440"></label>
<label>Day OFF <input type="number" name="day_off_min" min="0" max="1440"></label>
<label>Night ON <input type="number" name="night_on_min" min="0" max="1440"></label>
<label>Night OFF <input type="number" name="night_off_min" min="0" max="1440"></label>
</fieldset>
<fieldset><legend>Rotation</legend>
<label>Mode <select name="rot_mode">
<option value="off">Off</option><option value="interval">Small moves</option>
<option value="continuous">Continuous</option>
</select></label>
<label>Move size (°) <input type="number" name="rot_step_deg" min="1" max="360" oninput="rate()"></label>
<label>Rate (° per hour) <input type="number" name="rot_deg_per_hour" min="1" max="3600" oninput="rate()"></label>
<div class="hint" id="rate"></div>
<label>Also rotate at night <input type="checkbox" name="rot_at_night"></label>
<label>Stepper speed (half-steps/s) <input type="number" name="motor_speed" min="50" max="800" step="10"></label>
</fieldset>
<fieldset><legend>Revolution sensor</legend>
<label>Sensor fitted <input type="checkbox" name="rev_sensor"></label>
<label>Stall after (% of a revolution without pulse) <input type="number" name="stall_pct" min="110" max="300"></label>
</fieldset>
<fieldset><legend>Safety</legend>
<label>Manual override timeout (min) <input type="number" name="manual_timeout_min" min="1" max="240"></label>
</fieldset>
<button type="submit">Save</button><span id="msg"></span>
</form></section>
</main>
<script>
const $=id=>document.getElementById(id),F=()=>$('cfg').elements;
async function api(p,b){const r=await fetch(p,b?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}:{});
if(!r.ok)throw new Error((await r.json().catch(()=>({}))).error||r.status);return r.json()}
function dur(s){if(s==null)return'-';const h=s/3600|0,m=s%3600/60|0;return h?h+'h '+m+'m':m?m+'m '+s%60+'s':s+'s'}
function item(k,v,c){return`<div><div class="k">${k}</div><div class="v ${c||''}">${v}</div></div>`}
function mode(o){return o.mode=='auto'?'':` (manual ${o.mode}, ${dur(o.manual_left_s)})`}
function show(s){$('conn').textContent='';const m=s.motor;$('homeb').disabled=!s.revs.sensor;$('st').innerHTML=
item('Pump',(s.pump.on?'ON':'off')+mode(s.pump),s.pump.on?'ok':'')+
item('Pump phase left',dur(s.pump.phase_left_s))+
item('Tower',(m.moving?'turning':'still')+mode(m)+(m.homing?' (homing)':''),m.moving?'ok':'')+
item('Angle',m.angle_deg==null?'not homed':m.angle_deg.toFixed(1)+'°')+
item('Water',s.water_low?'LOW':'ok',s.water_low?'bad':'ok')+
item('Low-water alert',s.alerts.low_water?'yes':'no',s.alerts.low_water?'bad':'')+
item('Stall',s.alerts.stall?'FAULT':'no',s.alerts.stall?'bad':'')+
item('Water temp',s.temp_c==null?'-':s.temp_c.toFixed(1)+' °C')+
item('Revolutions',s.revs.today.toFixed(2)+' today / '+s.revs.total.toFixed(1))+
item('Cycle',s.is_day?'day':'night')+
item('Time',s.time||'not synced',s.time?'':'bad')+
item('Uptime',dur(s.uptime_s))+item('Wi-Fi',s.rssi+' dBm')}
async function poll(){try{show(await api('/api/status'))}catch(e){$('conn').textContent='(offline)'}}
function act(b){api('/api/manual',b).then(show).catch(e=>alert(e.message))}
function man(t,st){act({target:t,state:st,minutes:+$('mmin').value})}
function rate(){const f=F(),d=+f.rot_step_deg.value,h=+f.rot_deg_per_hour.value;
$('rate').textContent=d&&h?`${d}° every ${dur(Math.round(d*3600/h))} = ${(h/360).toFixed(2)} rev/h`:''}
function tzChanged(){const v=$('tzsel').value,c=v=='custom';$('tzrow').hidden=!c;if(!c)F().tz.value=v}
async function load(){const c=await api('/api/config'),f=F();
for(const k in c){const e=f[k];if(!e)continue;if(e.type=='checkbox')e.checked=c[k];else e.value=c[k]}
const o=[...$('tzsel').options].find(o=>o.value==c.tz);$('tzsel').value=o?c.tz:'custom';tzChanged();
$('mmin').value=c.manual_timeout_min;rate()}
async function save(ev){ev.preventDefault();const b={};
for(const e of F()){if(!e.name)continue;b[e.name]=e.type=='checkbox'?e.checked:e.type=='number'?+e.value:e.value}
try{await api('/api/config',b);$('msg').textContent='saved';load()}catch(e){$('msg').textContent=e.message}
setTimeout(()=>$('msg').textContent='',3000)}
load();poll();setInterval(poll,2000);
</script></body></html>
)HTML";

static const char *manualName(uint8_t m) {
  return m == sched::MAN_ON ? "on" : m == sched::MAN_OFF ? "off" : "auto";
}

static void hhmm(char *buf, size_t n, uint16_t minutes) {
  snprintf(buf, n, "%02u:%02u", minutes / 60, minutes % 60);
}

static bool parseHHMM(const char *s, uint16_t &out) {
  unsigned h, m;
  char extra;
  if (sscanf(s, "%u:%u%c", &h, &m, &extra) != 2 || h > 23 || m > 59) return false;
  out = h * 60 + m;
  return true;
}

static void sendJson(int code, JsonDocument &d) {
  String s;
  serializeJson(d, s);
  server.send(code, "application/json", s);
}

static void sendError(int code, const char *msg) {
  JsonDocument d;
  d["error"] = msg;
  sendJson(code, d);
}

static void sendStatus() {
  const sched::Status &s = app::scheduler.status();
  const sched::Config &c = app::scheduler.config();
  const float rev = (float)sched::stepsPerTowerRev(c);
  JsonDocument d;
  d["fw"] = FW_VERSION;
  d["uptime_s"] = app::nowS();
  struct tm t;
  bool tv = app::localTime(t);
  d["time_valid"] = tv;
  if (tv) {
    char buf[24];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &t);
    d["time"] = buf;
  } else {
    d["time"] = nullptr;
  }
  d["is_day"] = s.day;

  JsonObject p = d["pump"].to<JsonObject>();
  p["on"] = s.pumpOn;
  p["mode"] = manualName(s.pumpManual);
  p["manual_left_s"] = s.pumpManualLeftS;
  p["phase_left_s"] = s.pumpPhaseLeftS;

  JsonObject m = d["motor"].to<JsonObject>();
  m["moving"] = app::tele.motorEnergised;
  m["mode"] = manualName(s.motorManual);
  m["manual_left_s"] = s.motorManualLeftS;
  m["steps_to_go"] = s.stepsToGo;
  m["homed"] = s.homed;
  m["homing"] = s.homing;
  if (s.homed)
    m["angle_deg"] = roundf(s.angleSteps * 3600.0f / rev) / 10;
  else
    m["angle_deg"] = nullptr;
  m["steps_since_pulse"] = s.stepsSincePulse;

  d["water_low"] = s.waterLow;
  JsonObject a = d["alerts"].to<JsonObject>();
  a["low_water"] = s.alertLowWater;
  a["stall"] = s.faultStall;

  if (app::tele.tempValid)
    d["temp_c"] = roundf(app::tele.tempC * 10) / 10;
  else
    d["temp_c"] = nullptr;

  JsonObject r = d["revs"].to<JsonObject>();
  r["sensor"] = c.revSensor;
  r["pulses"] = app::tele.revPulses;
  r["total"] = roundf(s.stepsTotal * 100.0f / rev) / 100;  // from steps, sensor not needed
  r["today"] = roundf(s.stepsToday * 100.0f / rev) / 100;

  d["rssi"] = WiFi.RSSI();
  d["ip"] = WiFi.localIP().toString();
  d["heap"] = ESP.getFreeHeap();
  sendJson(200, d);
}

static void sendConfig() {
  const sched::Config &c = app::scheduler.config();
  JsonDocument d;
  char buf[8];
  d["day_on_min"] = c.dayOnMin;
  d["day_off_min"] = c.dayOffMin;
  d["night_on_min"] = c.nightOnMin;
  d["night_off_min"] = c.nightOffMin;
  hhmm(buf, sizeof(buf), c.dayStartMin);
  d["day_start"] = buf;
  hhmm(buf, sizeof(buf), c.dayEndMin);
  d["day_end"] = buf;
  d["tz"] = app::tz;
  d["rot_mode"] = sched::rotModeName(c.rotMode);
  d["rot_step_deg"] = c.rotStepDeg;
  d["rot_deg_per_hour"] = c.rotDegPerHour;
  d["rot_at_night"] = c.rotAtNight;
  d["rev_sensor"] = c.revSensor;
  d["stall_pct"] = c.stallPct;
  d["motor_speed"] = c.motorSpeed;
  d["manual_timeout_min"] = c.manualTimeoutMin;
  d["steps_per_rev"] = sched::stepsPerTowerRev(c);  // read-only, from gearing
  sendJson(200, d);
}

// numbers are clamped by sched::sanitize(); out-of-range input is pinned first
static void readNum(JsonDocument &d, const char *key, uint16_t &field) {
  if (!d[key].is<long>()) return;
  long v = d[key].as<long>();
  field = (uint16_t)(v < 0 ? 0 : v > 65535 ? 65535 : v);
}

static void readBool(JsonDocument &d, const char *key, bool &field) {
  if (d[key].is<bool>()) field = d[key].as<bool>();
}

static void handleConfigPost() {
  JsonDocument d;
  if (deserializeJson(d, server.arg("plain"))) return sendError(400, "bad json");

  sched::Config c = app::scheduler.config();
  readNum(d, "day_on_min", c.dayOnMin);
  readNum(d, "day_off_min", c.dayOffMin);
  readNum(d, "night_on_min", c.nightOnMin);
  readNum(d, "night_off_min", c.nightOffMin);
  readNum(d, "rot_step_deg", c.rotStepDeg);
  readNum(d, "rot_deg_per_hour", c.rotDegPerHour);
  readNum(d, "stall_pct", c.stallPct);
  readNum(d, "motor_speed", c.motorSpeed);
  readNum(d, "manual_timeout_min", c.manualTimeoutMin);
  readBool(d, "rot_at_night", c.rotAtNight);
  readBool(d, "rev_sensor", c.revSensor);

  if (!d["day_start"].isNull() && !parseHHMM(d["day_start"] | "", c.dayStartMin))
    return sendError(400, "day_start must be HH:MM");
  if (!d["day_end"].isNull() && !parseHHMM(d["day_end"] | "", c.dayEndMin))
    return sendError(400, "day_end must be HH:MM");
  if (!d["rot_mode"].isNull() && !sched::rotModeFromString(d["rot_mode"] | "", c.rotMode))
    return sendError(400, "rot_mode must be off|interval|continuous");

  String tz = app::tz;
  if (!d["tz"].isNull()) {
    tz = d["tz"].as<String>();
    tz.trim();
    if (tz.length() == 0 || tz.length() > 63) return sendError(400, "tz must be a POSIX TZ string");
  }

  app::scheduler.setConfig(c);
  app::tz = tz;
  app::saveConfig();
  sendConfig();
}

static void handleManual() {
  JsonDocument d;
  if (deserializeJson(d, server.arg("plain"))) return sendError(400, "bad json");

  const char *action = d["action"] | "";
  if (strcmp(action, "clear_faults") == 0) {
    app::scheduler.clearFaults();
    return sendStatus();
  }
  if (strcmp(action, "rotate") == 0) {
    long deg = d["degrees"] | 0L;
    if (deg < 1 || deg > 3600) return sendError(400, "degrees must be 1-3600");
    if (!app::scheduler.rotate((uint16_t)deg)) return sendError(409, "motor stalled: clear faults first");
    return sendStatus();
  }
  if (strcmp(action, "home") == 0) {
    if (!app::scheduler.home()) return sendError(409, "needs the rev sensor and no stall fault");
    return sendStatus();
  }
  if (*action) return sendError(400, "action must be clear_faults|rotate|home");

  const char *target = d["target"] | "";
  const char *state = d["state"] | "";
  uint8_t mode;
  if (strcmp(state, "on") == 0)
    mode = sched::MAN_ON;
  else if (strcmp(state, "off") == 0)
    mode = sched::MAN_OFF;
  else if (strcmp(state, "auto") == 0)
    mode = sched::MAN_AUTO;
  else
    return sendError(400, "state must be on|off|auto");

  long minutes = d["minutes"] | 0L;
  if (minutes < 0) minutes = 0;
  if (minutes > 240) minutes = 240;

  if (strcmp(target, "pump") == 0)
    app::scheduler.setManualPump(mode, app::nowS(), (uint16_t)minutes);
  else if (strcmp(target, "motor") == 0)
    app::scheduler.setManualMotor(mode, app::nowS(), (uint16_t)minutes);
  else
    return sendError(400, "target must be pump|motor");
  // the new state is applied on the next control step (<100 ms)
  sendStatus();
}

void web::begin() {
  server.on("/", HTTP_GET, []() { server.send_P(200, "text/html", INDEX_HTML); });
  server.on("/api/status", HTTP_GET, sendStatus);
  server.on("/api/config", HTTP_GET, sendConfig);
  server.on("/api/config", HTTP_POST, handleConfigPost);
  server.on("/api/manual", HTTP_POST, handleManual);
  server.onNotFound([]() { sendError(404, "not found"); });
  server.begin();
}

void web::loop() { server.handleClient(); }
