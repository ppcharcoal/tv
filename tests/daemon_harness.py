"""Runs the real tv-pad daemon loop against a fake pad and fake uinput devices.
Used by test_daemon.py (in a subprocess, so the fake `evdev` module stays contained)."""

import importlib.machinery
import importlib.util
import json
import os
import signal
import sys
import tempfile
import threading
import time
import types

import evdev as real_evdev

e = real_evdev.ecodes
LOG = []           # what the desktop received
GRABS = []         # grab / ungrab calls
FOCUS = [""]


class Ev:
    def __init__(self, type_, code, value):
        self.type, self.code, self.value = type_, code, value


class AbsInfo:
    def __init__(self, lo, hi):
        self.min, self.max = lo, hi


class FakePad:
    path = "/dev/input/event99"
    name = "Xbox Wireless Controller"

    def __init__(self):
        self.r, self.w = os.pipe()
        self.queue = []
        self.lock = threading.Lock()

    def fileno(self):
        return self.r

    def capabilities(self, absinfo=True):
        axes = [(e.ABS_X, AbsInfo(-32768, 32767)), (e.ABS_Y, AbsInfo(-32768, 32767)),
                (e.ABS_RX, AbsInfo(-32768, 32767)), (e.ABS_RY, AbsInfo(-32768, 32767)),
                (e.ABS_Z, AbsInfo(0, 1023)), (e.ABS_RZ, AbsInfo(0, 1023)),
                (e.ABS_HAT0X, AbsInfo(-1, 1)), (e.ABS_HAT0Y, AbsInfo(-1, 1))]
        keys = [e.BTN_SOUTH, e.BTN_EAST, e.BTN_X, e.BTN_Y, e.BTN_TL, e.BTN_TR,
                e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR]
        return {e.EV_KEY: keys, e.EV_ABS: axes if absinfo else [c for c, _ in axes]}

    def push(self, type_, code, value):
        with self.lock:
            self.queue.append(Ev(type_, code, value))
        os.write(self.w, b"x")

    def read(self):
        os.read(self.r, 4096)
        with self.lock:
            items, self.queue = self.queue, []
        return items

    def grab(self):
        GRABS.append("grab")

    def ungrab(self):
        GRABS.append("ungrab")

    def close(self):
        pass


PAD = FakePad()


class FakeUInput:
    def __init__(self, events, name):
        self.name = name

    def write(self, type_, code, value):
        LOG.append((self.name, type_, code, value))

    def syn(self):
        pass

    def close(self):
        pass


fake = types.ModuleType("evdev")
fake.ecodes = e
fake.InputDevice = lambda path: PAD
fake.list_devices = lambda: [PAD.path]
fake.UInput = FakeUInput
sys.modules["evdev"] = fake

here = os.path.dirname(os.path.abspath(__file__))
loader = importlib.machinery.SourceFileLoader("tvpad", os.path.join(here, "..", "tv-pad"))
spec = importlib.util.spec_from_loader("tvpad", loader)
tv = importlib.util.module_from_spec(spec)
loader.exec_module(tv)

tmp = tempfile.mkdtemp()
tv.ACTIVE_FLAG = os.path.join(tmp, "active")
tv.SUNSHINE_LOG = os.path.join(tmp, "sunshine.log")


def sunshine_log(line):
    with open(tv.SUNSHINE_LOG, "a", encoding="utf-8") as f:
        f.write(f"[2026-11-04 15:00:00.000]: Info: {line}\n")
tv.sunshine_running = lambda: True
tv.focused_window_class = lambda: FOCUS[0]
NOTES = []
tv.notify = lambda text, enabled=True: NOTES.append(text)
tv.load_config = lambda: tv.merge_config({"osk_command": []})
SESSION_CALLS = []
tv.Session.__init__.__defaults__ = (lambda cmd: SESSION_CALLS.append(cmd) or True,
                                    lambda cfg: SESSION_CALLS.append("api-close") or True, False,
                                    lambda cmd: "VCP 10 C 55 100")
tv.BRIGHTNESS_FILE = os.path.join(tmp, "brightness")

marks = {}


def mark(name):
    marks[name] = (len(LOG), len(GRABS))


def scenario():
    time.sleep(0.8)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    time.sleep(0.3)
    mark("before_stream")
    open(tv.ACTIVE_FLAG, "w").close()           # Sunshine: tv-pad on
    sunshine_log("CLIENT CONNECTED")
    time.sleep(1.2)
    mark("stream_on")
    PAD.push(e.EV_ABS, e.ABS_X, 32767)           # left stick right
    time.sleep(0.4)
    PAD.push(e.EV_ABS, e.ABS_X, 0)
    time.sleep(0.1)
    mark("moved")
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)          # A
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    PAD.push(e.EV_ABS, e.ABS_RZ, 1023)          # RT
    PAD.push(e.EV_ABS, e.ABS_RZ, 0)
    PAD.push(e.EV_KEY, e.BTN_START, 1)          # Start + B
    PAD.push(e.EV_KEY, e.BTN_EAST, 1)
    PAD.push(e.EV_KEY, e.BTN_EAST, 0)
    PAD.push(e.EV_KEY, e.BTN_START, 0)
    time.sleep(0.3)
    mark("buttons")
    FOCUS[0] = "xbox-play"                       # a game takes focus
    time.sleep(1.2)
    mark("focus_game")
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    time.sleep(0.3)
    mark("pressed_in_game")
    FOCUS[0] = "firefox"
    time.sleep(1.2)
    PAD.push(e.EV_KEY, e.BTN_MODE, 1)           # hold Xbox 1.2 s -> pause
    time.sleep(1.3)
    PAD.push(e.EV_KEY, e.BTN_MODE, 0)
    time.sleep(0.3)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    time.sleep(0.3)
    mark("user_paused")
    sunshine_log("CLIENT DISCONNECTED")         # TV turned off: stream paused
    time.sleep(1.2)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    time.sleep(0.3)
    mark("stream_paused")
    sunshine_log("CLIENT CONNECTED")            # stream resumed
    time.sleep(1.2)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    time.sleep(0.3)
    mark("stream_resumed")
    PAD.push(e.EV_KEY, e.BTN_SELECT, 1)         # View + Left: end the stream from the pad
    PAD.push(e.EV_ABS, e.ABS_HAT0X, -1)
    PAD.push(e.EV_ABS, e.ABS_HAT0X, 0)
    PAD.push(e.EV_KEY, e.BTN_SELECT, 0)
    time.sleep(1.2)
    mark("ended_by_pad")
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 1)
    PAD.push(e.EV_KEY, e.BTN_SOUTH, 0)
    time.sleep(0.3)
    try:
        os.remove(tv.ACTIVE_FLAG)               # Sunshine: tv-pad off (already gone)
    except FileNotFoundError:
        pass
    time.sleep(1.2)
    mark("stream_off")
    os.kill(os.getpid(), signal.SIGTERM)


threading.Thread(target=scenario, daemon=True).start()
tv.run_daemon()
print(json.dumps({"log": LOG, "grabs": GRABS, "marks": marks, "notes": NOTES, "session": SESSION_CALLS,
                  "flag_after_end": os.path.exists(tv.ACTIVE_FLAG)}))
