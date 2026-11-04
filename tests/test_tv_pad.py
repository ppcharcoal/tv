"""Tests for tv-pad. Run: python3 -m unittest discover -s tests"""

import importlib.machinery
import importlib.util
import os
import sys
import time
import unittest

from evdev import ecodes as e

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("tvpad", os.path.join(HERE, "..", "tv-pad"))
_spec = importlib.util.spec_from_loader("tvpad", _loader)
tv = importlib.util.module_from_spec(_spec)
_loader.exec_module(tv)


class FakeOut:
    def __init__(self):
        self.events = []  # ("key", code, down) | ("rel", code, value) | ("syn",) | ("osk",) | ("run", cmd)

    def key(self, code, down):
        self.events.append(("key", code, down))

    def rel(self, code, value):
        self.events.append(("rel", code, value))

    def syn(self):
        self.events.append(("syn",))

    def osk_toggle(self):
        self.events.append(("osk",))

    def run(self, cmd):
        self.events.append(("run", cmd))

    def notify(self, text):
        pass

    def keys(self):
        return [ev[1:] for ev in self.events if ev[0] == "key"]

    def rel_sum(self, code):
        return sum(ev[2] for ev in self.events if ev[0] == "rel" and ev[1] == code)


def make(cfg_changes=None):
    cfg = tv.merge_config(cfg_changes or {})
    out = FakeOut()
    return tv.Mapper(cfg, e, out), out, cfg


class ActionTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(tv.parse_action("key:LEFTMETA+R", e), tv.Action("key", [e.KEY_LEFTMETA, e.KEY_R]))
        self.assertEqual(tv.parse_action("mouse:left", e), tv.Action("mouse", [e.BTN_LEFT]))
        self.assertEqual(tv.parse_action("osk", e).kind, "osk")
        self.assertEqual(tv.parse_action("cmd: notify-send hi", e).command, "notify-send hi")
        self.assertEqual(tv.parse_action("none", e).kind, "none")
        with self.assertRaises(ValueError):
            tv.parse_action("key:NOPE", e)
        with self.assertRaises(ValueError):
            tv.parse_action("mouse:FOURTH", e)

    def test_default_config_parses(self):
        m, _, _ = make()
        self.assertEqual(m.buttons["A"], tv.Action("key", [e.KEY_ENTER]))
        self.assertEqual(m.combos[("Start", "B")], tv.Action("key", [e.KEY_LEFTMETA, e.KEY_C]))


class ButtonTests(unittest.TestCase):
    def test_a_is_enter(self):
        m, out, _ = make()
        m.control("A", True)
        m.control("A", False)
        self.assertEqual(out.keys(), [(e.KEY_ENTER, True), (e.KEY_ENTER, False)])

    def test_b_alone_is_escape_and_start_b_is_super_c(self):
        m, out, _ = make()
        m.control("B", True)
        m.control("B", False)
        self.assertEqual(out.keys(), [(e.KEY_ESC, True), (e.KEY_ESC, False)])
        out.events.clear()
        m.control("Start", True)
        m.control("B", True)
        m.control("B", False)
        m.control("Start", False)
        self.assertEqual(out.keys(), [(e.KEY_LEFTMETA, True), (e.KEY_C, True), (e.KEY_C, False), (e.KEY_LEFTMETA, False)])

    def test_start_tap_does_its_own_action(self):
        m, out, _ = make({"buttons": {"Start": "key:LEFTMETA"}})
        m.control("Start", True)
        self.assertEqual(out.keys(), [])  # waits: might become a combo
        m.control("Start", False)
        self.assertEqual(out.keys(), [(e.KEY_LEFTMETA, True), (e.KEY_LEFTMETA, False)])

    def test_shared_key_released_only_when_last_user_lets_go(self):
        m, out, _ = make()  # LB = Alt+Left, RB = Alt+Right
        m.control("LB", True)
        m.control("RB", True)
        m.control("LB", False)
        self.assertNotIn((e.KEY_LEFTALT, False), out.keys())
        m.control("RB", False)
        self.assertEqual(out.keys().count((e.KEY_LEFTALT, True)), 1)
        self.assertEqual(out.keys()[-1], (e.KEY_LEFTALT, False))

    def test_osk_and_cmd(self):
        m, out, _ = make({"buttons": {"R3": "cmd:echo hi"}})
        m.control("X", True)
        m.control("R3", True)
        self.assertIn(("osk",), out.events)
        self.assertIn(("run", "echo hi"), out.events)

    def test_release_all(self):
        m, out, _ = make()
        m.control("RT", True)
        m.control("View", True)
        out.events.clear()
        m.release_all()
        released = {code for code, down in out.keys() if not down}
        self.assertEqual(released, {e.BTN_LEFT, e.KEY_LEFTALT, e.KEY_TAB})
        self.assertEqual(m.held, {})

    def test_pause_hold(self):
        m, _, _ = make()
        m.control("Xbox", True)
        start = m.pause_since
        self.assertFalse(m.pause_requested(start + 0.5))
        self.assertTrue(m.pause_requested(start + 1.01))
        self.assertFalse(m.pause_requested(start + 2.0))  # only once per hold


class PadStateTests(unittest.TestCase):
    def setUp(self):
        self.m, self.out, _ = make()
        info = {e.ABS_X: (-32768, 32767), e.ABS_Y: (-32768, 32767), e.ABS_Z: (0, 1023), e.ABS_RZ: (0, 1023)}
        self.pad = tv.PadState(info, e)

    def test_trigger_hysteresis(self):
        self.pad.axis(e.ABS_RZ, 600, self.m)   # 0.59 -> press
        self.pad.axis(e.ABS_RZ, 450, self.m)   # 0.44 -> still pressed
        self.assertEqual(self.out.keys(), [(e.BTN_LEFT, True)])
        self.pad.axis(e.ABS_RZ, 100, self.m)   # 0.1 -> release
        self.assertEqual(self.out.keys(), [(e.BTN_LEFT, True), (e.BTN_LEFT, False)])
        self.pad.axis(e.ABS_Z, 1023, self.m)
        self.assertEqual(self.out.keys()[-1], (e.BTN_RIGHT, True))

    def test_hat_dpad(self):
        self.pad.axis(e.ABS_HAT0Y, -1, self.m)
        self.pad.axis(e.ABS_HAT0Y, 1, self.m)
        self.pad.axis(e.ABS_HAT0Y, 0, self.m)
        self.assertEqual(self.out.keys(), [(e.KEY_UP, True), (e.KEY_UP, False), (e.KEY_DOWN, True), (e.KEY_DOWN, False)])

    def test_stick_normalised(self):
        self.pad.axis(e.ABS_X, 32767, self.m)
        self.pad.axis(e.ABS_Y, -32768, self.m)
        self.assertAlmostEqual(self.m.lx, 1.0, places=3)
        self.assertAlmostEqual(self.m.ly, -1.0, places=3)

    def test_swap_xy(self):
        self.assertEqual(tv.pad_event_to_controls(e.EV_KEY, e.BTN_X, 1, e, False)[0], [("X", True)])
        self.assertEqual(tv.pad_event_to_controls(e.EV_KEY, e.BTN_X, 1, e, True)[0], [("Y", True)])
        self.assertEqual(tv.pad_event_to_controls(e.EV_KEY, e.BTN_SOUTH, 2, e, False)[0], [])  # autorepeat ignored


class StickTests(unittest.TestCase):
    def run_for(self, m, seconds, dt=1 / 250):
        for _ in range(int(seconds / dt)):
            m.tick(dt)

    def test_deadzone(self):
        m, out, _ = make()
        m.lx, m.ly = 0.1, -0.1
        self.run_for(m, 0.5)
        self.assertEqual(out.events, [])

    def test_full_tilt_speed_and_boost(self):
        m, out, cfg = make()
        m.lx = 1.0
        self.run_for(m, 0.3)
        first = out.rel_sum(e.REL_X)
        self.assertAlmostEqual(first, cfg["mouse_speed"] * 0.3, delta=10)  # no boost yet
        out.events.clear()
        self.run_for(m, 1.0)
        self.assertGreater(out.rel_sum(e.REL_X), cfg["mouse_speed"] * 1.5)   # boost kicks in
        self.assertEqual(out.rel_sum(e.REL_Y), 0)

    def test_fine_control_near_centre(self):
        m, out, cfg = make()
        m.lx = 0.4
        self.run_for(m, 1.0)
        self.assertLess(out.rel_sum(e.REL_X), cfg["mouse_speed"] * 0.2)
        self.assertGreater(out.rel_sum(e.REL_X), 0)

    def test_scroll(self):
        m, out, cfg = make()
        m.ry = -1.0  # stick up
        self.run_for(m, 1.0)
        wheel = out.rel_sum(e.REL_WHEEL)
        hires = out.rel_sum(e.REL_WHEEL_HI_RES)
        self.assertAlmostEqual(wheel, cfg["scroll_speed"], delta=1)
        self.assertGreater(wheel, 0)  # up = positive
        self.assertAlmostEqual(hires / 120, wheel, delta=1)


class SunshineConfTests(unittest.TestCase):
    def test_add_to_empty(self):
        out = tv.add_prep_cmd("")
        self.assertEqual(out, 'global_prep_cmd = [{"do": "/usr/bin/tv-pad on", "undo": "/usr/bin/tv-pad off"}]\n')

    def test_add_to_existing_settings(self):
        out = tv.add_prep_cmd("capture = wlr\noutput_name = HDMI-A-1\n")
        self.assertTrue(out.startswith("capture = wlr\noutput_name = HDMI-A-1\nglobal_prep_cmd = "))

    def test_append_to_existing_prep_cmd_and_idempotent(self):
        text = 'global_prep_cmd = [{"do":"x","undo":"y"}]\n'
        out = tv.add_prep_cmd(text)
        self.assertIn('"do": "x"', out)
        self.assertIn("/usr/bin/tv-pad on", out)
        self.assertEqual(tv.add_prep_cmd(out), out)

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            tv.add_prep_cmd("global_prep_cmd = [oops\n")


class ConfigTests(unittest.TestCase):
    def test_merge(self):
        cfg = tv.merge_config({"mouse_speed": 900, "swap_xy": 1, "buttons": {"A": "key:SPACE", "B": 5},
                               "unknown": 1, "deadzone": "x"})
        self.assertEqual(cfg["mouse_speed"], 900)
        self.assertIs(cfg["swap_xy"], True)
        self.assertEqual(cfg["buttons"]["A"], "key:SPACE")
        self.assertEqual(cfg["buttons"]["B"], "key:ESC")
        self.assertNotIn("unknown", cfg)
        self.assertEqual(cfg["deadzone"], tv.DEFAULT_CONFIG["deadzone"])


if __name__ == "__main__":
    unittest.main()
