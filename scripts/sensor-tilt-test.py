#!/usr/bin/env python3
"""
HP ENVY x360 13-ar0xxx - guided accelerometer / tablet-switch recording.
Records raw AMD SFH accelerometer (/dev/hidraw0), gyro (/dev/hidraw1) and the
hp-wmi tablet switch (/sys/devices/platform/hp-wmi/tablet) in 6 physical
positions. Timed steps (no key presses needed, keyboard is off in tablet mode).
Results: ~/logs/sensor-tilt-test.log
"""
import os
import select
import struct
import time

OUT = "/home/dorten_hp_envy/logs/sensor-tilt-test.log"
STEP_SECONDS = 10      # time to get into position
SAMPLE_SECONDS = 3     # sampling at the end of each step

POSITIONS = [
    ("laptop_normal", "LAPTOP mode, screen open normally, sitting in front of you"),
    ("tablet_landscape", "Fold into TABLET mode, hold it upright LANDSCAPE (like a normal screen)"),
    ("tablet_portrait_left", "Still tablet: rotate 90 deg so the LEFT edge points DOWN (portrait)"),
    ("tablet_portrait_right", "Still tablet: rotate so the RIGHT edge points DOWN (portrait)"),
    ("tablet_upside_down", "Still tablet: landscape UPSIDE DOWN"),
    ("tablet_flat", "Still tablet: lay it FLAT on the table, screen facing up"),
]


def read_tablet():
    try:
        with open("/sys/devices/platform/hp-wmi/tablet") as f:
            return f.read().strip()
    except Exception as e:
        return f"err:{e}"


def sample(fd_acc, fd_gyr, seconds):
    acc, gyr = [], []
    end = time.time() + seconds
    while time.time() < end:
        r, _, _ = select.select([fd_acc, fd_gyr], [], [], 0.3)
        for fd in r:
            data = os.read(fd, 64)
            if len(data) >= 15:
                xyz = struct.unpack_from("<iii", data, 3)
                (acc if fd == fd_acc else gyr).append(xyz)
    return acc, gyr


def avg(vals):
    if not vals:
        return None
    return tuple(round(sum(v[i] for v in vals) / len(vals), 2) for i in range(3))


def main():
    fd_acc = os.open("/dev/hidraw0", os.O_RDONLY)
    fd_gyr = os.open("/dev/hidraw1", os.O_RDONLY)
    lines = [f"=== sensor tilt test {time.strftime('%Y-%m-%d %H:%M:%S')} ==="]
    print("\nFollow the instructions on screen. Each step is timed, no keys needed.\n")
    for key, text in POSITIONS:
        print("\n" + "=" * 60)
        print(f"  NEXT: {text}")
        print("=" * 60)
        for s in range(STEP_SECONDS, 0, -1):
            print(f"  get into position... {s:2d}s ", end="\r", flush=True)
            time.sleep(1)
        print("  HOLD STILL - recording...        ", flush=True)
        acc, gyr = sample(fd_acc, fd_gyr, SAMPLE_SECONDS)
        tab = read_tablet()
        line = (f"{key:24s} accel_avg={avg(acc)} accel_n={len(acc)} "
                f"accel_min={min(acc) if acc else None} accel_max={max(acc) if acc else None} "
                f"gyro_avg={avg(gyr)} hp_wmi_tablet={tab}")
        lines.append(line)
        print("  recorded:", line)
    os.close(fd_acc)
    os.close(fd_gyr)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nDONE - results saved to {OUT}. You can unfold back to laptop mode.\n")


if __name__ == "__main__":
    main()
