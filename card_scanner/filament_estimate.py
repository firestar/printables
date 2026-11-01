"""Estimate PETG filament mass from the exported STLs.

No numpy-stl / trimesh available in this environment (no .pydeps dir, and neither
package is installed system-wide) -- binary STL is a trivial fixed-record format,
so this parses it directly with numpy (signed tetrahedron-volume sum, the same
method numpy-stl/trimesh use internally).

Run: python3 filament_estimate.py   (from card_scanner/)
"""
import struct
import numpy as np
import os

STL_DIR = os.path.join(os.path.dirname(__file__), "cad", "stl")
RIG_DIR = os.path.join(STL_DIR, "rig")

PETG_DENSITY_G_CM3 = 1.27
NORMAL_INFILL_FRACTION = 0.45  # task-specified approx for 4 walls / 25% gyroid


def stl_volume_mm3(path):
    with open(path, "rb") as f:
        header = f.read(80)
        if header[:5].lower() == b"solid":
            raise ValueError(f"{path}: looks like ASCII STL, not handled")
        count = struct.unpack("<I", f.read(4))[0]
        raw = f.read(count * 50)
    if len(raw) != count * 50:
        raise ValueError(f"{path}: truncated STL ({len(raw)} vs {count*50})")
    rec = np.frombuffer(raw, dtype=np.uint8).reshape(count, 50)
    floats = rec[:, :48].copy().view("<f4").reshape(count, 12)
    v1, v2, v3 = floats[:, 3:6], floats[:, 6:9], floats[:, 9:12]
    vol = np.einsum("ij,ij->i", v1, np.cross(v2, v3)).sum() / 6.0
    return abs(vol)


# name -> (qty, infill_fraction, color)
MAIN_PARTS = {
    "hopper_base": (1, NORMAL_INFILL_FRACTION, "black"),
    "hopper_guide": (2, NORMAL_INFILL_FRACTION, "black"),
    "hopper_back": (1, NORMAL_INFILL_FRACTION, "black"),
    "hopper_front": (1, NORMAL_INFILL_FRACTION, "black"),
    "elevator_platform": (1, NORMAL_INFILL_FRACTION, "black"),
    "elev_switch_post": (1, NORMAL_INFILL_FRACTION, "black"),
    "pick_bridge": (1, NORMAL_INFILL_FRACTION, "black"),
    "pick_carriage": (1, NORMAL_INFILL_FRACTION, "black"),
    "roller_block": (10, NORMAL_INFILL_FRACTION, "black"),
    "roller_block_s": (2, NORMAL_INFILL_FRACTION, "black"),
    "roller_hub": (24, 1.0, "black"),  # 100% infill per cad README
    "track_feed": (1, NORMAL_INFILL_FRACTION, "black"),
    "track_scan_out": (1, NORMAL_INFILL_FRACTION, "black"),
    "track_xfer": (1, NORMAL_INFILL_FRACTION, "black"),
    "guide_rail_40": (4, NORMAL_INFILL_FRACTION, "black"),
    "guide_rail_18": (2, NORMAL_INFILL_FRACTION, "black"),
    "hood": (1, NORMAL_INFILL_FRACTION, "black"),
    "lower_shroud": (1, NORMAL_INFILL_FRACTION, "black"),
    "led_frame_top": (1, NORMAL_INFILL_FRACTION, "white"),
    "led_frame_bot": (1, NORMAL_INFILL_FRACTION, "white"),
    "cam_mount": (2, NORMAL_INFILL_FRACTION, "black"),
    "stop_mount": (1, NORMAL_INFILL_FRACTION, "black"),
    "stop_flag": (1, NORMAL_INFILL_FRACTION, "black"),
    "sleeve_deck": (1, NORMAL_INFILL_FRACTION, "black"),
    "platen": (1, NORMAL_INFILL_FRACTION, "black"),
    "sleeve_fence": (1, NORMAL_INFILL_FRACTION, "black"),
    "sleeve_magazine": (1, NORMAL_INFILL_FRACTION, "black"),
    "mag_sensor_mount": (1, NORMAL_INFILL_FRACTION, "black"),
    "sleeve_gate": (1, NORMAL_INFILL_FRACTION, "black"),
    "tongue_carriage": (1, NORMAL_INFILL_FRACTION, "black"),
    "tongue_keeper_lo": (1, NORMAL_INFILL_FRACTION, "black"),
    "tongue_keeper_hi": (2, NORMAL_INFILL_FRACTION, "black"),
    "tongue_rod_block": (3, NORMAL_INFILL_FRACTION, "black"),
    "tongue_rod_block_sw": (1, NORMAL_INFILL_FRACTION, "black"),
    "air_jet": (1, NORMAL_INFILL_FRACTION, "black"),
    "lift_mount": (1, NORMAL_INFILL_FRACTION, "black"),
    "lift_arm": (1, NORMAL_INFILL_FRACTION, "black"),
    "pusher_bracket": (1, NORMAL_INFILL_FRACTION, "black"),
    "pusher_slider": (1, NORMAL_INFILL_FRACTION, "black"),
    "pusher_flap": (1, NORMAL_INFILL_FRACTION, "black"),
    "pusher_crank": (1, NORMAL_INFILL_FRACTION, "black"),
    "pusher_link": (1, NORMAL_INFILL_FRACTION, "black"),
    "diverter_base": (1, NORMAL_INFILL_FRACTION, "black"),
    "diverter_tray": (1, NORMAL_INFILL_FRACTION, "black"),
    "bin": (3, NORMAL_INFILL_FRACTION, "black"),
    "feed_motor_mount": (1, NORMAL_INFILL_FRACTION, "black"),
    "corner_bracket": (12, NORMAL_INFILL_FRACTION, "black"),
    "frame_foot": (6, NORMAL_INFILL_FRACTION, "black"),
    "elec_plate_a": (1, NORMAL_INFILL_FRACTION, "black"),
    "elec_plate_b": (1, NORMAL_INFILL_FRACTION, "black"),
    "estop_panel": (1, NORMAL_INFILL_FRACTION, "black"),
    "lid_switch_mount": (1, NORMAL_INFILL_FRACTION, "black"),
}

# rig-only extras: not in MAIN_PARTS, exist only under stl/rig/
RIG_ONLY_PARTS = {
    "rig_foot": (4, NORMAL_INFILL_FRACTION, "black"),
    "rig_push_slot": (1, NORMAL_INFILL_FRACTION, "black"),
    "rig_push_stick": (1, NORMAL_INFILL_FRACTION, "black"),
}

# parts also present under stl/rig/ (phase-1 subset) -- same geometry/qty as MAIN_PARTS,
# listed here just to total up a "phase 1" filament subtotal without re-reading STLs.
RIG_SHARED_NAMES = [
    "mag_sensor_mount", "platen", "lift_mount", "tongue_rod_block", "sleeve_magazine",
    "lift_arm", "sleeve_fence", "tongue_keeper_lo", "pusher_crank", "pusher_link",
    "tongue_keeper_hi", "tongue_rod_block_sw", "pusher_slider", "pusher_flap",
    "pusher_bracket", "tongue_carriage", "sleeve_gate", "air_jet", "sleeve_deck",
]


def main():
    results = {}
    missing = []
    for name in MAIN_PARTS:
        path = os.path.join(STL_DIR, f"{name}.stl")
        if not os.path.exists(path):
            missing.append(name)
            continue
        results[name] = stl_volume_mm3(path)
    for name in RIG_ONLY_PARTS:
        path = os.path.join(RIG_DIR, f"{name}.stl")
        if not os.path.exists(path):
            missing.append(name)
            continue
        results[name] = stl_volume_mm3(path)

    if missing:
        print("MISSING STL FILES:", missing)

    def grams(name, qty, infill, vol_mm3):
        cm3 = vol_mm3 / 1000.0
        return cm3 * infill * PETG_DENSITY_G_CM3 * qty

    totals = {"black": 0.0, "white": 0.0}
    print(f"{'part':<22}{'qty':>4}{'unit_cm3':>12}{'infill':>8}{'color':>8}{'total_g':>10}")
    all_parts = dict(MAIN_PARTS)
    all_parts.update(RIG_ONLY_PARTS)
    for name, (qty, infill, color) in sorted(all_parts.items()):
        if name not in results:
            continue
        vol = results[name]
        g = grams(name, qty, infill, vol)
        totals[color] += g
        print(f"{name:<22}{qty:>4}{vol/1000.0:>12.2f}{infill:>8.2f}{color:>8}{g:>10.1f}")

    print()
    print(f"TOTAL BLACK PETG: {totals['black']:.1f} g  ({totals['black']/1000:.3f} kg)")
    print(f"TOTAL WHITE PETG: {totals['white']:.1f} g  ({totals['white']/1000:.3f} kg)")
    print(f"GRAND TOTAL:      {totals['black']+totals['white']:.1f} g  ({(totals['black']+totals['white'])/1000:.3f} kg)")

    # Phase-1 rig filament subtotal: rig-only extras + the shared parts' phase-1 share
    # (same geometry, already counted once above -- this is just a separate reporting slice)
    rig_total_g = 0.0
    for name in RIG_ONLY_PARTS:
        if name in results:
            qty, infill, color = RIG_ONLY_PARTS[name]
            rig_total_g += grams(name, qty, infill, results[name])
    for name in RIG_SHARED_NAMES:
        if name in results:
            qty, infill, color = MAIN_PARTS[name]
            rig_total_g += grams(name, qty, infill, results[name])
    print()
    print(f"PHASE-1 RIG FILAMENT (rig-only extras + shared sleeve-station parts): {rig_total_g:.1f} g ({rig_total_g/1000:.3f} kg)")


if __name__ == "__main__":
    main()
