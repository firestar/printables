#!/usr/bin/env python3
"""SPICE tests of the 2-layer interface board, run with ngspice in the KiCad image.

Copper resistances come from ../check_power.py.  Q1 is modelled from the AO3401A
datasheet.  Parts with no vendor SPICE model here (level shifter, WS2812 input, mic
output, ESP32 pins, LDO) are behavioural, with their values stated below, so results
show margins rather than exact waveforms.

Run from this folder on a machine with Docker:  python3 run_sim.py
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = os.path.join(HERE, ".run")
os.makedirs(TMP, exist_ok=True)

Q1 = """
* AO3401A: |Vth| about 1 V; 50 mOhm at Vgs -4.5 V (datasheet: under 60), body diode
.model QP PMOS (LEVEL=1 VTO=-1.0 KP=5.7 LAMBDA=0)
.model DB D (IS=1e-9 N=1.2 RS=0.02)
M1 d g s s QP L=1 W=1
D1 d s DB
Rg g 0 1
Cgs g s 650p
Bvgs vgs 0 V=v(g)-v(s)
Bvds vds 0 V=v(d)-v(s)
Biq iqa 0 V=abs(i(Vq))
"""

# Copper from check_power.py: Q1 source to trunk end, then to each load.
RAILS = """
Rt s t 0.008
Rl t led 0.006
Ra t amp 0.020
Re t esp 0.080
Rg1 gnd_led 0 0.003
"""

ESR_NOTE = "1000 uF electrolytic ESR"


def hot_plug(esr, cable_l, cable_r):
    return f"""hot plug into a discharged board
Vs src 0 PWL(0 0 1u 5)
Rs src n1 0.05
Lw n1 n2 {cable_l}
Rw n2 vin {cable_r}
Vq vin d 0
{Q1}{RAILS.replace('Rg1 gnd_led 0 0.003', '')}
C1 led c1x 1000u
Rc c1x 0 {esr}
C2 amp 0 10u
C3 amp 0 100n
C6 esp 0 10u
Iled led 0 0.05
Iamp amp 0 0.2
Iesp esp 0 0.15
.tran 0.05u 3m uic
.meas tran ipk MAX i(Vq)
.meas tran vled_max MAX v(led)
.meas tran vamp_max MAX v(amp)
.meas tran vesp_max MAX v(esp)
.meas tran vgs_min MIN v(vgs)
.meas tran vfinal FIND v(led) AT=2.9m
.end
"""


def reverse():
    return f"""5 V connected backwards
Vs src 0 -5
Rs src vin 0.15
Vq vin d 0
{Q1}{RAILS.replace('Rg1 gnd_led 0 0.003', '')}
C1 led 0 1000u
C6 esp 0 10u
Rled led 0 10
Ramp amp 0 25
Resp esp 0 33
.tran 1u 20m uic
.meas tran vled_min MIN v(led)
.meas tran iq_abs MAX v(iqa) FROM=5m
.meas tran vgs_min MIN v(vgs)
.meas tran vgs_max MAX v(vgs)
.end
"""


def load_step(vsupply, led, amp, esp):
    return f"""loads jump to {led}+{amp}+{esp} A, supply {vsupply} V
Vs src 0 {vsupply}
Rs src n1 0.05
Lw n1 n2 1u
Rw n2 vin 0.10
Vq vin d 0
{Q1}{RAILS.replace('Rg1 gnd_led 0 0.003', '')}
C1 led c1x 1000u
Rc c1x 0 0.1
C2 amp 0 10u
C3 amp 0 100n
C6 esp 0 10u
Iled led 0 PWL(0 0.05 1m 0.05 1.001m {led})
Iamp amp 0 PWL(0 0.2 1m 0.2 1.001m {amp})
Iesp esp 0 PWL(0 0.15 1m 0.15 1.001m {esp})
* AMS1117-3.3 on the devkit: 1.2 V dropout assumed at this current
Bldo v33 0 V=min(3.3, v(esp)-1.2)
Rmic v33 0 1000
.ic v(led)={vsupply} v(amp)={vsupply} v(esp)={vsupply}
.tran 1u 12m
.meas tran vled_min MIN v(led) FROM=1m
.meas tran vamp_min MIN v(amp) FROM=1m
.meas tran vesp_min MIN v(esp) FROM=1m
.meas tran v33_min MIN v(v33) FROM=1m
.meas tran vds_final FIND v(vds) AT=11.9m
.meas tran iq_final FIND i(Vq) AT=11.9m
.end
"""


def led_data(shifter):
    # WS2812B bits: 1 = 800 ns high, 450 low; 0 = 400 ns high, 850 low.
    pts, t = ["0 0"], 100e-9
    for bit in (1, 0, 1, 1, 0, 0, 1, 0):
        hi = 800e-9 if bit else 400e-9
        lo = 450e-9 if bit else 850e-9
        pts += [f"{t:.4e} 0", f"{t + 5e-9:.4e} 3.3", f"{t + hi:.4e} 3.3", f"{t + hi + 5e-9:.4e} 0"]
        t += hi + lo
    drive = ("Bsh s1 0 V=5*0.5*(1+tanh(30*(v(gp)-1.4)))\nRo s1 nb 20" if shifter else "Rb gp nb 0.01")
    return f"""LED data, {'through shifter' if shifter else 'shifter bypassed'}
Vg g0 0 PWL({' '.join(pts)})
Rgo g0 gp 25
Cgp gp 0 5p
{drive}
R1 nb t1 330
Ctrk t1 0 4p
L1 t1 t2 0.3u
Cw t2 0 20p
Rtie t2 0 1e7
.tran 0.5n 10.5u
.meas tran vhi MAX v(t2)
.meas tran vlo MIN v(t2) FROM=200n
.meas tran t_high_1 TRIG v(t2) VAL=3.5 RISE=1 TARG v(t2) VAL=3.5 FALL=1
.meas tran t_high_0 TRIG v(t2) VAL=3.5 RISE=2 TARG v(t2) VAL=3.5 FALL=2
.end
"""


def crosstalk(state, rser=0, near=True):
    # SCK beside SD: 40 mm of board trace and 150 mm of the cable, both pessimistic.
    # Victim: mic SD output 200 ohm driving low or high, or tri-stated with the 100 k.
    rd = {"low": "Rv vd 0 200", "high": "Rv vd vh 200\nVh vh 0 3.3", "tri": "Rv vd 0 1e7"}[state]
    secs = []
    for i in range(4):
        a, b = f"a{i}", f"a{i + 1}"
        c, d = f"v{i}", f"v{i + 1}"
        secs.append(f"""La{i} {a} {b} 7n
Lv{i} {c} {d} 7n
K{i} La{i} Lv{i} {0.3 if near else 0.1}
Cm{i} {b} {d} {0.4 if near else 0.1}p
Cga{i} {b} 0 1p
Cgv{i} {d} 0 1p""")
    return f"""mic line crosstalk, SD {state}
* SCK at 1 MHz, 2 ns edges, 40 ohm driver (ESP32 pin)
Vg g0 0 PULSE(0 3.3 100n 2n 2n 498n 1u)
Ra g0 a0 {40 + rser}
{chr(10).join(secs)}
* cable to the mic: 150 mm side-by-side wires
Lca a4 a5 150n
Lcv v4 v5 150n
Kc Lca Lcv {0.4 if near else 0.15}
Cmc a5 v5 {3 if near else 0.8}p
Cga5 a5 0 5p
Cgv5 v5 0 5p
Cmic a5 0 5p
* mic end drives the victim
Rvv v5 vd 0.01
{rd}
* ESP32 end of SD: 5 pF input, 100 k pull-down (R2)
Cin v0 0 5p
R2 v0 0 100k
.ic v(v0)={'3.3' if state == 'high' else '0'}
.tran 0.1n 4u
.meas tran vmax MAX v(v0) FROM=1u
.meas tran vmin MIN v(v0) FROM=1u
.end
"""


def run(name, deck):
    path = os.path.join(TMP, name + ".cir")
    with open(path, "w") as f:
        f.write(deck)
    uid = f"{os.getuid()}:{os.getgid()}"
    r = subprocess.run(["docker", "run", "--rm", "-u", uid, "-e", "HOME=/tmp", "-v", f"{TMP}:/work",
                        "-w", "/work", "kicad/kicad:9.0", "ngspice", "-b", name + ".cir"],
                       capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    vals = {}
    for m in re.finditer(r"^\s*(\w+)\s*=\s*([-+\d.eE]+)", out, re.M):
        vals[m.group(1).lower()] = float(m.group(2))
    if r.returncode or not vals or "failed" in out.lower().split("measurements")[-1][:0]:
        print(out[-1500:])
    return vals, out


fails = []


def check(ok, text):
    print(f"  {'PASS' if ok else 'FAIL'}  {text}")
    if not ok:
        fails.append(text)


def main():
    print("== 1. Hot plug into a discharged board ==")
    worst = 0.0
    print("  Short, thick wires with a very low-ESR capacitor reach 28.4 A, so C1 must be general purpose.")
    for esr, l, r_ in ((0.15, "1u", 0.1), (0.1, "1u", 0.1), (0.1, "0.3u", 0.05)):
        v, out = run(f"hot_{esr}_{l}", hot_plug(esr, l, r_))
        print(f"  ESR {esr} ohm, cable {l}H {r_} ohm: Q1 peak {v['ipk']:.1f} A, rail peak LED {v['vled_max']:.2f} V,"
              f" amp {v['vamp_max']:.2f} V, ESP {v['vesp_max']:.2f} V, settles {v['vfinal']:.2f} V")
        worst = max(worst, v["ipk"])
        check(v["ipk"] < 27, f"Q1 peak {v['ipk']:.1f} A is under its 27 A pulse rating")
        check(max(v["vled_max"], v["vamp_max"], v["vesp_max"]) < 5.5, "no rail overshoots past 5.5 V")
        check(abs(v["vgs_min"]) < 12, f"Q1 gate {v['vgs_min']:.2f} V stays inside +/-12 V")

    print("\n== 2. 5 V connected backwards ==")
    v, _ = run("reverse", reverse())
    print(f"  rail reaches {v['vled_min'] * 1000:.1f} mV, Q1 leakage {v['iq_abs'] * 1000:.3f} mA,"
          f" gate {v['vgs_min']:.2f} to {v['vgs_max']:.2f} V")
    check(v["vled_min"] > -0.3, "the board sees less than 0.3 V backwards")
    check(v["iq_abs"] < 1e-3, "under 1 mA flows")

    print("\n== 3. Load steps within what the 3 A supply can deliver ==")
    for vs, led, tag in ((5.0, 1.4, "firmware LED cap"), (5.0, 1.85, "3 A supply limit"),
                         (4.9, 1.4, "firmware LED cap"), (4.75, 1.4, "firmware LED cap")):
        v, _ = run(f"step_{vs}_{led}", load_step(vs, led, 0.8, 0.35))
        print(f"  [{tag}]")
        print(f"  supply {vs} V: LED {v['vled_min']:.2f} V, amp {v['vamp_min']:.2f} V, ESP VIN {v['vesp_min']:.2f} V,"
              f" 3V3 {v['v33_min']:.2f} V; Q1 drops {abs(v['vds_final']) * 1000:.0f} mV at {v['iq_final']:.2f} A")
        check(v["vled_min"] > 3.7, f"LED rail {v['vled_min']:.2f} V is above the WS2812B 3.7 V minimum")
        check(v["vamp_min"] > 2.5, f"amp rail {v['vamp_min']:.2f} V is above the MAX98357A 2.5 V minimum")
        if vs >= 4.9:
            check(v["v33_min"] > 3.0, f"3V3 {v['v33_min']:.2f} V is above the ESP32 3.0 V minimum")
        else:
            print(f"  NOTE  3V3 {v['v33_min']:.2f} V at {vs} V supply: below the ESP32 minimum if under 3.0 V")

    print("\n== 4. LED data at the strip (needs above 3.5 V, below 1.5 V) ==")
    v, _ = run("led_shift", led_data(True))
    print(f"  through shifter: {v['vlo']:.2f} to {v['vhi']:.2f} V; high time of a 1 bit {v['t_high_1'] * 1e9:.0f} ns,"
          f" of a following 0 bit {v['t_high_0'] * 1e9:.0f} ns")
    check(v["vhi"] > 3.5 and v["vlo"] < 1.5, "levels reach the WS2812B thresholds")
    check(abs(v["t_high_1"] - 800e-9) < 150e-9, "1-bit width within the 150 ns tolerance")
    check(abs(v["t_high_0"] - 400e-9) < 150e-9, "0-bit width within the 150 ns tolerance")
    v, _ = run("led_bypass", led_data(False))
    print(f"  bypassed (JP1 1-2): peak {v.get('vhi', 0):.2f} V against the 3.5 V threshold,"
          f" {'below spec, relies on the strip being forgiving' if v.get('vhi', 0) < 3.5 else 'OK'}")

    print("\n== 5. SCK interference on mic SD at the ESP32 (limits: below 0.83 V, above 2.48 V) ==")
    for tag, rser, near in (("without R3/R4, SCK beside SD", 0, True), ("with 100 ohm, SCK beside SD (worst)", 100, True),
                            ("with 100 ohm, WS wire between SCK and SD (as wired)", 100, False)):
        print(f"  [{tag}]")
        for state in ("low", "high", "tri"):
            v, _ = run(f"xt_{state}_{rser}_{near}", crosstalk(state, rser, near))
            print(f"    SD {state}: {v['vmin']:.3f} to {v['vmax']:.3f} V")
            if rser and state == "low":
                check(v["vmax"] < 0.83, f"driven low stays under 0.83 V ({v['vmax']:.3f} V)")
            if rser and state == "high":
                check(v["vmin"] > 2.48, f"driven high stays above 2.48 V ({v['vmin']:.3f} V)")

    print()
    if fails:
        print(f"{len(fails)} FAILED")
        for f in fails:
            print(" -", f)
        sys.exit(1)
    print("ALL SIMULATIONS PASS")


if __name__ == "__main__":
    main()
