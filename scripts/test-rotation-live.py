#!/usr/bin/env python3
"""
HP ENVY x360 13-ar0xxx Live Sensor & Display Auto-Rotation Monitor
Monitors accelerometer telemetry from /dev/hidraw0 used for display auto-rotation
and checks current Tablet Mode / On-Screen Keyboard status.
"""

import os
import sys
import time
import struct
import select
from gi.repository import Gio


def classify_screen_orientation(x, y, z):
    abs_x = abs(x)
    abs_y = abs(y)

    if abs_x >= 4.5 and abs_x > abs_y:
        return "PORTRAIT (Right-Up 90°)" if x > 0 else "PORTRAIT (Left-Up 270°)"

    if y >= 4.0 and y > abs_x:
        return "INVERTED (Tent 180°)"

    if y <= -4.0 and abs_y > abs_x:
        return "LANDSCAPE (Normal 0°)"

    return "NEUTRAL / FLAT"


def main():
    print("=" * 80)
    print(" HP ENVY x360 Live Sensor & Display Auto-Rotation Monitor")
    print("=" * 80)

    # 1. Check sensor_mask
    mask_path = "/sys/module/amd_sfh/parameters/sensor_mask"
    if os.path.exists(mask_path):
        with open(mask_path, "r") as f:
            mask = f.read().strip()
        print(f"[*] Kernel amd_sfh sensor_mask: {mask} (target: 1)")
    else:
        print("[!] amd_sfh module not loaded!")

    # 2. Check GSettings OSK and Touchpad status
    try:
        osk_settings = Gio.Settings.new("org.gnome.desktop.a11y.applications")
        osk_state = osk_settings.get_boolean("screen-keyboard-enabled")
        tp_settings = Gio.Settings.new("org.gnome.desktop.peripherals.touchpad")
        tp_state = tp_settings.get_string("send-events")
        mode_str = "TABLET MODE (Keys & Touchpad Locked, OSK On)" if osk_state else "LAPTOP MODE (Keys & Touchpad Active, OSK Off)"
        print(f"[*] Current Input State: {mode_str}")
        print(f"    - On-Screen Keyboard: {'ENABLED' if osk_state else 'DISABLED'}")
        print(f"    - Touchpad Events: {tp_state}")
        print(f"    - Toggle Shortcut: Press Super+F12 or tap 'Toggle Tablet Mode' icon")
    except Exception as e:
        print(f"[!] Could not query GSettings: {e}")

    # 3. Check /dev/hidraw0 live streaming
    if not os.path.exists("/dev/hidraw0"):
        print("[!] /dev/hidraw0 not found!")
        return

    try:
        fd = os.open("/dev/hidraw0", os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        print("[!] Permission denied accessing /dev/hidraw0. Run: sudo chmod 666 /dev/hidraw*")
        return

    print("\n[*] Streaming live accelerometer data from /dev/hidraw0 (Press Ctrl+C to stop)...")
    print("    Turn the screen into portrait or tent to see display auto-rotation trigger!\n")
    print(f"{'TIME':<10} {'X (Lateral)':<15} {'Y (Vertical)':<15} {'Z (Perp)':<15} {'G-SENSOR ROTATION':<25}")
    print("-" * 80)

    try:
        last_x, last_y, last_z = None, None, None
        while True:
            r, _, _ = select.select([fd], [], [], 0.5)
            if not r:
                continue
            data = os.read(fd, 64)
            if len(data) >= 15 and data[0] == 1:
                x, y, z = struct.unpack_from("<iii", data, 3)

                orient = classify_screen_orientation(x, y, z)

                # Only print when values change
                if (x, y, z) != (last_x, last_y, last_z):
                    ts = time.strftime("%H:%M:%S")
                    print(f"{ts:<10} {x:<15} {y:<15} {z:<15} {orient:<25}")
                    last_x, last_y, last_z = x, y, z
            time.sleep(0.08)
    except KeyboardInterrupt:
        print("\n[✓] Monitor stopped.")
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
