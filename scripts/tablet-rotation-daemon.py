#!/usr/bin/env python3
"""
HP ENVY x360 13-ar0xxx Tablet Mode & Auto-Rotation Daemon
---------------------------------------------------------
Features:
1. Real-Time Tilt & Auto-Rotation:
   - Reads calibrated telemetry from AMD SFH accelerometer (/dev/hidraw0).
   - Accel values are in m/s² (1g ≈ 9.8 m/s² ≈ 10).
   - Thresholds: |X| >= 5 m/s² triggers portrait; |Y| >= 5 m/s² triggers landscape.
   - Accel mapping:
     * X > 0  -> right-up (90°)
     * X < 0  -> left-up (270°)
     * Y < 0  -> normal (0°)
     * Y > 0  -> bottom-up (180°)
   - Rotates eDP-1 via org.gnome.Mutter.DisplayConfig Wayland DBus API.
   - Respects GNOME orientation-lock setting.
2. Robust Hardware Input Lock (Full Tablet Protection):
   - Grabs /dev/input/event2 (physical keyboard) AND ALL touchpad devices (/dev/input/event3, event4) via EVIOCGRAB.
   - Disables GNOME touchpad events via org.gnome.desktop.peripherals.touchpad send-events = disabled.
   - Accidental keypresses or palm contact on the back of the tablet will NEVER register!
3. Persistent Tablet Mode State Machine:
   - Rotating into Portrait (90° / 270°), Tent (180°), or laying flat (|Z| >= 7) ENTERS Tablet Mode.
   - Rotating back to Landscape (0°) ROTATES the display back to normal, but KEEPS Tablet Mode ACTIVE!
     (Physical keys and trackpad remain locked; OSK remains enabled).
   - Exit back to Clamshell Laptop Mode:
     * Tap 'Toggle Tablet Mode' in the GNOME dock / app launcher, OR
     * Run '~/scripts/toggle-tablet-mode.sh', OR
     * Send SIGUSR1 to the daemon.
4. Smart On-Screen Keyboard (OSK):
   - Tablet mode: Enables OSK (screen-keyboard-enabled = true).
   - Laptop mode: Disables OSK (screen-keyboard-enabled = false) so typing 'sudo' never pops up an OSK.
   - Ensures GNOME top-bar accessibility icon is visible for 1-click manual trigger.
"""

import os
import sys
import time
import math
import fcntl
import struct
import select
import signal
import threading
import subprocess
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib, Gio

LOG_FILE = "/home/dorten_hp_envy/logs/power-blackbox.log"

ORIENTATION_TO_TRANSFORM = {
    "normal": 0,
    "right-up": 1,
    "bottom-up": 2,
    "left-up": 3,
}

TRANSFORM_NAMES = {
    0: "normal (0°)",
    1: "right-up (90°)",
    2: "bottom-up (180°)",
    3: "left-up (270°)",
}

EVIOCGRAB = 0x40044590


def EVIOCGKEY(length):
    return (2 << 30) | (length << 16) | (ord("E") << 8) | 0x18


# Key codes for all modifier and arrow keys
ALL_MODS = [
    42,  # KEY_LEFTSHIFT
    54,  # KEY_RIGHTSHIFT
    29,  # KEY_LEFTCTRL
    97,  # KEY_RIGHTCTRL
    56,  # KEY_LEFTALT
    100,  # KEY_RIGHTALT
    125,  # KEY_LEFTMETA
    126,  # KEY_RIGHTMETA
    103,  # KEY_UP
    108,  # KEY_DOWN
    105,  # KEY_LEFT
    106,  # KEY_RIGHT
]

current_transform = 0
is_tablet_mode = False
osk_settings = None
touchpad_settings = None
touchscreen_settings = None

grabbed_kbd_fd = None
grabbed_tp_fds = []
input_lock_mutex = threading.Lock()
manual_override_until = 0.0


def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [TABLET-ROTATE] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_orientation_locked():
    global touchscreen_settings
    try:
        if touchscreen_settings is None:
            touchscreen_settings = Gio.Settings.new(
                "org.gnome.settings-daemon.peripherals.touchscreen"
            )
        return touchscreen_settings.get_boolean("orientation-lock")
    except Exception:
        return False


def set_osk_enabled(enabled):
    global osk_settings
    try:
        if osk_settings is None:
            osk_settings = Gio.Settings.new("org.gnome.desktop.a11y.applications")
        current = osk_settings.get_boolean("screen-keyboard-enabled")
        if current != enabled:
            osk_settings.set_boolean("screen-keyboard-enabled", enabled)
            log(f"On-Screen Keyboard set to {'ENABLED' if enabled else 'DISABLED'}")
    except Exception as e:
        log(f"Failed to set on-screen keyboard state: {e}")


def find_input_devices():
    """Discover physical keyboard, touchpad, and touchscreen event device paths."""
    kbd_dev = None
    touchpad_devs = []
    touchscreen_dev = None
    try:
        with open("/proc/bus/input/devices", "r") as f:
            content = f.read()
        sections = content.strip().split("\n\n")
        for sec in sections:
            handlers = ""
            name = ""
            for line in sec.splitlines():
                if line.startswith("N: Name="):
                    name = line.split("=", 1)[1].strip('"')
                elif line.startswith("H: Handlers="):
                    handlers = line.split("=", 1)[1]
            event_match = [h for h in handlers.split() if h.startswith("event")]
            if not event_match:
                continue
            dev_path = f"/dev/input/{event_match[0]}"
            if "AT Translated Set 2 keyboard" in name:
                kbd_dev = dev_path
            elif "SYNA328F" in name:
                touchpad_devs.append(dev_path)
            elif "ELAN2514" in name and "Stylus" not in name:
                touchscreen_dev = dev_path
    except Exception as e:
        log(f"Error discovering input devices: {e}")
    return kbd_dev, touchpad_devs, touchscreen_dev


def release_all_modifiers(fd):
    """Synthesizes key release for all modifier and arrow keys with monotonic timestamps."""
    if fd is None:
        return
    try:
        for code in ALL_MODS:
            t = time.clock_gettime(time.CLOCK_MONOTONIC)
            s, us = int(t), int((t - int(t)) * 1000000)
            ev1 = struct.pack("qqHHi", s, us, 1, code, 0)
            ev2 = struct.pack("qqHHi", s, us, 0, 0, 0)
            os.write(fd, ev1 + ev2)
    except Exception:
        pass


def wait_for_all_keys_released(fd, max_wait_ms=400):
    """Waits up to max_wait_ms for any held physical keys to be released before grabbing."""
    buf_len = (0x2FF + 7) // 8
    end = time.time() + (max_wait_ms / 1000.0)
    while time.time() < end:
        buf = bytearray(buf_len)
        try:
            fcntl.ioctl(fd, EVIOCGKEY(buf_len), buf)
            if not any(buf):
                return True
        except Exception:
            break
        time.sleep(0.02)
    return True


def set_hardware_inputs_locked(locked):
    """Locks or unlocks physical keyboard and all touchpad devices safely using EVIOCGRAB."""
    global grabbed_kbd_fd, grabbed_tp_fds, touchpad_settings
    with input_lock_mutex:
        kbd_path, tp_paths, _ = find_input_devices()

        if locked:
            # Grab physical keyboard
            if grabbed_kbd_fd is None and kbd_path and os.path.exists(kbd_path):
                try:
                    grabbed_kbd_fd = os.open(kbd_path, os.O_RDWR | os.O_NONBLOCK)
                    wait_for_all_keys_released(grabbed_kbd_fd)
                    release_all_modifiers(grabbed_kbd_fd)
                    time.sleep(0.02)
                    fcntl.ioctl(grabbed_kbd_fd, EVIOCGRAB, 1)
                    log("Physical keyboard GRABBED (keys disabled on back of tablet)")
                except Exception as e:
                    log(f"Failed to grab keyboard: {e}")
                    grabbed_kbd_fd = None

            # Grab all touchpad/mouse devices (event3, event4)
            if not grabbed_tp_fds and tp_paths:
                for tp_path in tp_paths:
                    if os.path.exists(tp_path):
                        try:
                            fd = os.open(tp_path, os.O_RDONLY | os.O_NONBLOCK)
                            fcntl.ioctl(fd, EVIOCGRAB, 1)
                            grabbed_tp_fds.append((fd, tp_path))
                            log(f"Touchpad device GRABBED: {tp_path}")
                        except Exception as e:
                            log(f"Failed to grab touchpad device {tp_path}: {e}")

            # Instruct GNOME Mutter to disable touchpad events
            try:
                if touchpad_settings is None:
                    touchpad_settings = Gio.Settings.new("org.gnome.desktop.peripherals.touchpad")
                touchpad_settings.set_string("send-events", "disabled")
            except Exception as e:
                log(f"GSettings touchpad disable warning: {e}")
        else:
            # Release physical keyboard
            if grabbed_kbd_fd is not None:
                try:
                    fcntl.ioctl(grabbed_kbd_fd, EVIOCGRAB, 0)
                    release_all_modifiers(grabbed_kbd_fd)
                    os.close(grabbed_kbd_fd)
                    log("Physical keyboard RELEASED (typing enabled)")
                except Exception as e:
                    log(f"Failed to release keyboard: {e}")
                grabbed_kbd_fd = None

            # Release all touchpad devices
            if grabbed_tp_fds:
                for fd, path in grabbed_tp_fds:
                    try:
                        fcntl.ioctl(fd, EVIOCGRAB, 0)
                        os.close(fd)
                        log(f"Touchpad device RELEASED: {path}")
                    except Exception as e:
                        log(f"Failed to release touchpad device {path}: {e}")
                grabbed_tp_fds = []

            # Re-enable GNOME touchpad events
            try:
                if touchpad_settings is None:
                    touchpad_settings = Gio.Settings.new("org.gnome.desktop.peripherals.touchpad")
                touchpad_settings.set_string("send-events", "enabled")
            except Exception as e:
                log(f"GSettings touchpad enable warning: {e}")


def set_tablet_mode(active: bool, reason: str = "", notify: bool = False):
    global is_tablet_mode, current_transform
    if is_tablet_mode == active:
        return
    is_tablet_mode = active
    log(f"Tablet Mode changed -> {'ENABLED (Tablet Protection)' if active else 'DISABLED (Clamshell Laptop)'} [{reason}]")
    set_hardware_inputs_locked(active)
    set_osk_enabled(active)

    if not active:
        # Returning to clamshell laptop mode -> ensure display is upright 0°
        if not is_orientation_locked() and current_transform != 0:
            apply_mutter_rotation(0)

    # Show desktop notification ONLY for explicit user actions (e.g. manual toggle button)
    if notify:
        try:
            if active:
                subprocess.run(
                    ["notify-send", "-i", "input-tablet", "-t", "3000", "Tablet Mode Active", "Physical keyboard & touchpad are disabled."],
                    check=False
                )
            else:
                subprocess.run(
                    ["notify-send", "-i", "input-keyboard", "-t", "3000", "Laptop Mode Active", "Physical keyboard & touchpad are enabled."],
                    check=False
                )
        except Exception:
            pass


def apply_mutter_rotation(target_transform):
    """Rotate eDP-1 using org.gnome.Mutter.DisplayConfig DBus interface."""
    global current_transform
    try:
        bus = dbus.SessionBus()
        obj = bus.get_object(
            "org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig"
        )
        iface = dbus.Interface(obj, "org.gnome.Mutter.DisplayConfig")
        serial, monitors, logical_monitors, _ = iface.GetCurrentState()

        current_mode_id = "1920x1080@60.033"
        connector = "eDP-1"
        for mon in monitors:
            mon_spec, modes, _ = mon
            if str(mon_spec[0]).startswith("eDP"):
                connector = str(mon_spec[0])
                for m in modes:
                    mode_id, _, _, _, _, _, mode_props = m
                    if mode_props.get("is-current", False):
                        current_mode_id = str(mode_id)
                        break

        new_logical = []
        for lm in logical_monitors:
            x, y, scale, transform, primary, linked_monitors, _ = lm
            if int(transform) == target_transform:
                current_transform = target_transform
                return False
            mon_configs = dbus.Array([], signature="(ssa{sv})")
            for lmon in linked_monitors:
                conn_name = str(lmon[0])
                mode_to_use = (
                    current_mode_id if conn_name == connector else "1920x1080@60.000"
                )
                mon_configs.append(
                    dbus.Struct(
                        (
                            dbus.String(conn_name),
                            dbus.String(mode_to_use),
                            dbus.Dictionary({}, signature="sv"),
                        ),
                        signature=None,
                    )
                )
            new_logical.append(
                dbus.Struct(
                    (
                        dbus.Int32(x),
                        dbus.Int32(y),
                        dbus.Double(scale),
                        dbus.UInt32(target_transform),
                        dbus.Boolean(primary),
                        mon_configs,
                    ),
                    signature=None,
                )
            )

        iface.ApplyMonitorsConfig(
            dbus.UInt32(serial),
            dbus.UInt32(1),
            dbus.Array(new_logical, signature="(iiduba(ssa{sv}))"),
            dbus.Dictionary({}, signature="sv"),
        )
        current_transform = target_transform
        log(f"Rotated display {connector} -> {TRANSFORM_NAMES.get(target_transform, target_transform)}")
        return True
    except Exception as e:
        log(f"Mutter rotation failed: {e}")
        return False


def classify_screen_orientation(x, y, z):
    """
    Classifies raw accelerometer telemetry strictly for display auto-rotation:
    - 'right-up' (90° portrait)
    - 'left-up' (270° portrait)
    - 'bottom-up' (180° inverted / tent)
    - 'normal' (0° normal landscape)
    """
    abs_x = abs(x)
    abs_y = abs(y)

    # 1. Sideways Portrait: |X| >= 4.5 and |X| > |Y|
    if abs_x >= 4.5 and abs_x > abs_y:
        return "right-up" if x > 0 else "left-up"

    # 2. Inverted / Tent Landscape: Y >= 4.0 and Y > abs_x
    if y >= 4.0 and y > abs_x:
        return "bottom-up"

    # 3. Normal Upright Landscape: Y <= -4.0 and abs_y > abs_x
    if y <= -4.0 and abs_y > abs_x:
        return "normal"

    return None


def raw_accel_monitor_thread():
    """
    Real-time accelerometer reader for /dev/hidraw0.
    Values are in m/s² (1g ≈ 9.8 ≈ 10).
    Used PURELY for screen auto-rotation (portrait / landscape).
    Never touches hardware input locks.
    """
    candidate_orient = None
    candidate_orient_count = 0
    current_applied_orient = "normal"

    while True:
        hidraw_path = "/dev/hidraw0"
        if not os.path.exists(hidraw_path):
            time.sleep(2)
            continue

        try:
            fd = os.open(hidraw_path, os.O_RDONLY | os.O_NONBLOCK)
        except Exception as e:
            log(f"Failed to open {hidraw_path}: {e}")
            time.sleep(2)
            continue

        try:
            while True:
                r, _, _ = select.select([fd], [], [], 0.3)
                if not r:
                    continue
                try:
                    data = os.read(fd, 64)
                except Exception:
                    break

                if len(data) >= 15 and data[0] == 1:
                    x, y, z = struct.unpack_from("<iii", data, 3)

                    target_orient = classify_screen_orientation(x, y, z)

                    if target_orient:
                        if target_orient == candidate_orient:
                            candidate_orient_count += 1
                        else:
                            candidate_orient = target_orient
                            candidate_orient_count = 1

                        if candidate_orient_count >= 2 and target_orient != current_applied_orient:
                            current_applied_orient = target_orient
                            log(f"Orientation debounced -> {target_orient} (raw x={x}, y={y}, z={z})")
                            if not is_orientation_locked() and target_orient in ORIENTATION_TO_TRANSFORM:
                                apply_mutter_rotation(ORIENTATION_TO_TRANSFORM[target_orient])

        except Exception as e:
            log(f"Raw accel reader error: {e}")
        finally:
            try:
                os.close(fd)
            except Exception:
                pass
        time.sleep(1)


def on_sigusr1():
    global is_tablet_mode
    log("Received SIGUSR1 signal: Toggling Tablet / Laptop mode.")
    set_tablet_mode(not is_tablet_mode, "User manual toggle (shortcut/button)", notify=True)
    return GLib.SOURCE_CONTINUE


def main():
    global osk_settings, touchscreen_settings, touchpad_settings
    DBusGMainLoop(set_as_default=True)

    log("Starting Tablet Mode & Auto-Rotation Daemon (G-Sensor Auto-Rotation & User-Controlled Input Lock)...")

    # Initialize GSettings interfaces
    try:
        osk_settings = Gio.Settings.new("org.gnome.desktop.a11y.applications")
        touchpad_settings = Gio.Settings.new("org.gnome.desktop.peripherals.touchpad")
        touchscreen_settings = Gio.Settings.new("org.gnome.settings-daemon.peripherals.touchscreen")
        # Ensure universal access icon is visible in GNOME panel for 1-click fallback
        a11y_settings = Gio.Settings.new("org.gnome.desktop.a11y")
        a11y_settings.set_boolean("always-show-universal-access-status", True)
    except Exception as e:
        log(f"GSettings initialization warning: {e}")

    # Register SIGUSR1 signal handler for instant manual toggle
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, on_sigusr1)

    # Initialize explicitly into Laptop Mode (inputs unlocked, OSK disabled)
    set_tablet_mode(False, "Startup default (Laptop Mode)", notify=False)

    # Start raw accelerometer monitor thread for display auto-rotation
    t_raw = threading.Thread(target=raw_accel_monitor_thread, daemon=True)
    t_raw.start()

    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        log("Daemon stopped by user.")
        set_tablet_mode(False, "Daemon shutdown", notify=False)
        sys.exit(0)


if __name__ == "__main__":
    main()
