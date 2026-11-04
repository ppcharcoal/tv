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

    def screen_toggle(self):
        self.events.append(("screen",))

    def end_stream(self):
        self.events.append(("end-stream",))

    def run(self, cmd):
        self.events.append(("run", cmd))

    def hypr(self, cmd):
        self.events.append(("hypr", cmd))

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
        self.assertEqual(m.buttons["A"], tv.Action("mouse", [e.BTN_LEFT]))
        self.assertEqual(m.buttons["RT"], tv.Action("key", [e.KEY_ENTER]))
        self.assertEqual(m.combos[("Down", "RB")], tv.Action("hypr", command="workspace +1"))
        self.assertEqual(m.combos[("Start", "B")], tv.Action("key", [e.KEY_LEFTMETA, e.KEY_C]))


class ButtonTests(unittest.TestCase):
    def test_a_is_left_click_and_rt_is_enter(self):
        m, out, _ = make()
        m.control("A", True)
        m.control("A", False)
        m.control("RT", True)
        m.control("RT", False)
        self.assertEqual(out.keys(), [(e.BTN_LEFT, True), (e.BTN_LEFT, False), (e.KEY_ENTER, True), (e.KEY_ENTER, False)])

    def test_workspace_combos(self):
        m, out, _ = make()
        for mod, btn, expected in [("Down", "LB", "workspace -1"), ("Down", "RB", "workspace +1"),
                                   ("Right", "LB", "movetoworkspace -1"), ("Right", "RB", "movetoworkspace +1")]:
            out.events.clear()
            m.control(mod, True)
            m.control(btn, True)
            m.control(btn, False)
            m.control(mod, False)
            self.assertEqual(out.events, [("hypr", expected)], (mod, btn))

    def test_down_and_right_alone_are_still_arrows(self):
        m, out, _ = make()
        m.control("Down", True)
        m.control("Down", False)
        m.control("Right", True)
        m.control("Right", False)
        self.assertEqual(out.keys(), [(e.KEY_DOWN, True), (e.KEY_DOWN, False), (e.KEY_RIGHT, True), (e.KEY_RIGHT, False)])

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

    def test_view_tap_is_alt_tab_and_view_combos(self):
        m, out, _ = make()
        m.control("View", True)
        self.assertEqual(out.keys(), [])          # might become View+Up / View+Left
        m.control("View", False)
        self.assertEqual(out.keys(), [(e.KEY_LEFTALT, True), (e.KEY_TAB, True), (e.KEY_TAB, False), (e.KEY_LEFTALT, False)])
        out.events.clear()
        m.control("View", True)
        m.control("Up", True)
        m.control("Up", False)
        m.control("View", False)
        self.assertEqual(out.events, [("screen",)])  # no arrow key, no Alt+Tab
        out.events.clear()
        m.control("View", True)
        m.control("Left", True)
        m.control("Left", False)
        m.control("View", False)
        self.assertEqual(out.events, [("end-stream",)])
        out.events.clear()
        m.control("Up", True)                     # Up alone is still the arrow key
        self.assertEqual(out.keys(), [(e.KEY_UP, True)])

    def test_osk_and_cmd(self):
        m, out, _ = make({"buttons": {"R3": "cmd:echo hi"}})
        m.control("X", True)
        m.control("R3", True)
        self.assertIn(("osk",), out.events)
        self.assertIn(("run", "echo hi"), out.events)

    def test_release_all(self):
        m, out, _ = make()
        m.control("RT", True)
        m.control("LB", True)
        out.events.clear()
        m.release_all()
        released = {code for code, down in out.keys() if not down}
        self.assertEqual(released, {e.KEY_ENTER, e.KEY_LEFTALT, e.KEY_LEFT})
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
        self.assertEqual(self.out.keys(), [(e.KEY_ENTER, True)])
        self.pad.axis(e.ABS_RZ, 100, self.m)   # 0.1 -> release
        self.assertEqual(self.out.keys(), [(e.KEY_ENTER, True), (e.KEY_ENTER, False)])
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


class SunshineLogTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sunshine.log")
        self.w = tv.SunshineLog(self.path)

    def write(self, text, mode="a"):
        with open(self.path, mode, encoding="utf-8") as f:
            f.write(text)

    def test_no_file_and_no_entries(self):
        self.assertIsNone(self.w.poll())
        self.write("[2026-11-04 15:00:00.000]: Info: Sunshine version: 2025\n")
        self.assertIsNone(self.w.poll())

    def test_pause_and_resume(self):
        self.write("[x]: Info: CLIENT CONNECTED\n")
        self.assertIs(self.w.poll(), True)
        self.write("[x]: Info: CLIENT DISCONNECTED\n")
        self.assertIs(self.w.poll(), False)
        self.write("[x]: Info: Client connected\n")  # any case
        self.assertIs(self.w.poll(), True)

    def test_last_entry_wins_and_partial_line(self):
        self.write("CLIENT CONNECTED\nCLIENT DISCONNECTED\nCLIENT CONN")
        self.assertIs(self.w.poll(), False)  # unfinished line is not read yet
        self.write("ECTED\n")
        self.assertIs(self.w.poll(), True)

    def test_sunshine_restart_truncates_log(self):
        self.write("CLIENT CONNECTED\n" * 50)
        self.assertIs(self.w.poll(), True)
        self.write("[x]: Info: starting\n", mode="w")
        self.assertIsNone(self.w.poll())


class SessionTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.calls = []
        self.flag = os.path.join(d, "active")
        open(self.flag, "w").close()
        self.old = (tv.ACTIVE_FLAG, tv.BRIGHTNESS_FILE, tv.STATE_DIR)
        tv.ACTIVE_FLAG, tv.BRIGHTNESS_FILE, tv.STATE_DIR = self.flag, os.path.join(d, "brightness"), d
        self.notes = []

    def tearDown(self):
        tv.ACTIVE_FLAG, tv.BRIGHTNESS_FILE, tv.STATE_DIR = self.old

    def session(self, api_ok=True, cfg=None, brightness="VCP 10 C 55 100\n"):
        return tv.Session(tv.merge_config(cfg or {}),
                          run=lambda cmd: self.calls.append(cmd) or True,
                          close_app=lambda c: self.calls.append("api-close") or api_ok,
                          background=False, query=lambda cmd: brightness)

    def test_parse_brightness(self):
        self.assertEqual(tv.parse_brightness("VCP 10 C 55 100"), 55)
        self.assertIsNone(tv.parse_brightness("Display not found"))
        self.assertIsNone(tv.parse_brightness(None))

    def test_dims_and_restores_remembered_brightness(self):
        s = self.session()
        s.screen_toggle(self.notes.append)
        self.assertEqual(self.calls, [["ddcutil", "--noverify", "setvcp", "10", "0"]])
        self.assertTrue(os.path.exists(tv.BRIGHTNESS_FILE))
        s.screen_toggle(self.notes.append)
        self.assertEqual(self.calls[-1], ["ddcutil", "--noverify", "setvcp", "10", "55"])
        self.assertFalse(os.path.exists(tv.BRIGHTNESS_FILE))
        s.screen_on()  # already on: nothing to do
        self.assertEqual(len(self.calls), 2)

    def test_never_uses_power_mode_by_default(self):
        s = self.session()
        s.screen_toggle(self.notes.append)
        s.screen_toggle(self.notes.append)
        self.assertFalse(any("D6" in c for c in self.calls if isinstance(c, list)))

    def test_unknown_brightness_falls_back_to_full(self):
        s = self.session(brightness=None)
        s.screen_toggle(self.notes.append)
        s.screen_toggle(self.notes.append)
        self.assertEqual(self.calls[-1], ["ddcutil", "--noverify", "setvcp", "10", "100"])

    def test_brightness_is_kept_outside_the_runtime_dir(self):
        # /run/user is wiped on reboot; the level must survive a power cut while dimmed
        self.assertFalse(self.old[1].startswith(tv.RUNTIME_DIR))
        self.assertTrue(self.old[1].startswith(tv.PERSIST_DIR))

    def test_left_dimmed_by_previous_run_is_restored(self):
        with open(tv.BRIGHTNESS_FILE, "w") as f:
            f.write("42")
        self.session()
        self.assertEqual(self.calls, [["ddcutil", "--noverify", "setvcp", "10", "42"]])

    def test_commands_mode(self):
        s = self.session(cfg={"screen_mode": "commands", "screen_off_command": ["off"], "screen_on_command": ["on"]})
        s.screen_toggle(self.notes.append)
        s.screen_toggle(self.notes.append)
        self.assertEqual(self.calls, [["off"], ["on"]])

    def test_end_stream_turns_screen_on_and_closes_app(self):
        s = self.session()
        s.screen_toggle(self.notes.append)
        self.calls.clear()
        s.end_stream(self.notes.append)
        self.assertEqual(self.calls, [["ddcutil", "--noverify", "setvcp", "10", "55"], "api-close"])
        self.assertFalse(os.path.exists(self.flag))

    def test_end_stream_falls_back_to_restarting_sunshine(self):
        s = self.session(api_ok=False)
        s.end_stream(self.notes.append)
        self.assertEqual(self.calls, ["api-close",
                                      ["systemctl", "--user", "restart", "app-dev.lizardbyte.app.Sunshine.service"]])

    def test_background_jobs_run_in_order(self):
        import time as _t
        s = tv.Session(tv.merge_config({}), run=lambda cmd: (_t.sleep(0.05), self.calls.append(cmd)),
                       close_app=lambda c: True, background=True, query=lambda cmd: "VCP 10 C 55 100")
        s.screen_toggle(self.notes.append)   # dim (slow query+run)
        s.screen_toggle(self.notes.append)   # restore, queued right behind it
        s.worker.join(timeout=5)
        self.assertEqual(self.calls, [["ddcutil", "--noverify", "setvcp", "10", "0"],
                                      ["ddcutil", "--noverify", "setvcp", "10", "55"]])

    def test_api_needs_login(self):
        self.assertFalse(tv.sunshine_close_app(tv.merge_config({})))


class SunshineApiTests(unittest.TestCase):
    """sunshine_close_app against a local HTTPS server that checks the request."""

    def test_close_request(self):
        import http.server
        import ssl
        import subprocess
        import tempfile
        import threading
        d = tempfile.mkdtemp()
        cert, key = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", cert,
                        "-days", "1", "-subj", "/CN=localhost"], check=True, capture_output=True)
        seen = {}

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                seen["path"] = self.path
                seen["auth"] = self.headers.get("Authorization")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":true}')

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        threading.Thread(target=srv.handle_request, daemon=True).start()
        cfg = tv.merge_config({"sunshine_url": f"https://127.0.0.1:{srv.server_address[1]}",
                               "sunshine_user": "pipes", "sunshine_password": "tajne"})
        self.assertTrue(tv.sunshine_close_app(cfg))
        self.assertEqual(seen["path"], "/api/apps/close")
        self.assertEqual(seen["auth"], "Basic cGlwZXM6dGFqbmU=")  # base64("pipes:tajne")
        srv.server_close()


class SteamModeTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.old = (tv.ACTIVE_FLAG, tv.STATE_DIR)
        tv.ACTIVE_FLAG, tv.STATE_DIR = os.path.join(d, "active"), d

    def tearDown(self):
        tv.ACTIVE_FLAG, tv.STATE_DIR = self.old
        os.environ.pop("SUNSHINE_APP_NAME", None)

    def test_flag_keeps_the_sunshine_app_name(self):
        os.environ["SUNSHINE_APP_NAME"] = "Steam Big Picture"
        tv.cmd_on()
        self.assertEqual(tv.read_stream_app(), "Steam Big Picture")

    def test_old_flag_format_and_missing_name(self):
        with open(tv.ACTIVE_FLAG, "w") as f:
            f.write("1730730000.5")
        self.assertEqual(tv.read_stream_app(), "")
        tv.cmd_on()  # no SUNSHINE_APP_NAME
        self.assertEqual(tv.read_stream_app(), "")

    def test_watch_only_mapper_ignores_everything_but_view_left(self):
        out = FakeOut()
        m = tv.Mapper(tv.watch_only_config(tv.merge_config({})), e, out)
        for name in ["A", "B", "X", "Y", "RT", "LT", "Up", "Left"]:
            m.control(name, True)
            m.control(name, False)
        m.control("View", True)
        m.control("View", False)               # View alone: nothing (no Alt+Tab)
        self.assertEqual(out.events, [])
        m.control("View", True)
        m.control("Left", True)
        m.control("Left", False)
        m.control("View", False)
        self.assertEqual(out.events, [("end-stream",)])


class HyprTests(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(tv.hypr_dispatch_forms("workspace +1"), [
            ["hyprctl", "dispatch", "workspace", "+1"],
            ["hyprctl", "dispatch", 'hl.dsp.focus({ workspace = "+1" })'],
        ])
        self.assertEqual(tv.hypr_dispatch_forms("movetoworkspace -1")[1],
                         ["hyprctl", "dispatch", 'hl.dsp.window.move({ workspace = "-1", follow = true })'])
        self.assertEqual(tv.hypr_dispatch_forms("killactive")[1], ["hyprctl", "dispatch", "hl.dsp.window.close()"])
        self.assertEqual(tv.hypr_dispatch_forms("exec foo"), [["hyprctl", "dispatch", "exec", "foo"]])
        self.assertEqual(tv.hypr_dispatch_forms('lua:hl.dsp.focus({ workspace = "e+1" })'),
                         [["hyprctl", "dispatch", 'hl.dsp.focus({ workspace = "e+1" })']])

    def test_parse_lua_action(self):
        a = tv.parse_action('hypr:lua:hl.dsp.focus({ workspace = "e+1" })', e)
        self.assertEqual(a, tv.Action("hypr", command='lua:hl.dsp.focus({ workspace = "e+1" })'))

    def test_finds_working_syntax_and_remembers_it(self):
        tried = []

        def query(cmd):
            tried.append(cmd[2:])
            # a Lua-config Hyprland: only hl.dsp... says "ok"
            return "ok\n" if cmd[2].startswith("hl.dsp.") else "error: 3 ..."

        h = tv.Hypr(query)
        self.assertTrue(h.dispatch("workspace +1"))
        self.assertEqual(len(tried), 2)
        tried.clear()
        self.assertTrue(h.dispatch("movetoworkspace -1"))
        self.assertEqual(tried, [['hl.dsp.window.move({ workspace = "-1", follow = true })']])

    def test_remembered_form_missing_for_other_dispatcher(self):
        h = tv.Hypr(lambda cmd: "ok" if cmd[2].startswith("hl.dsp.") or cmd[2] == "exec" else "error")
        self.assertTrue(h.dispatch("workspace +1"))   # remembers the Lua form (index 1)
        self.assertTrue(h.dispatch("exec foo"))       # has only the classic form

    def test_nothing_works(self):
        self.assertFalse(tv.Hypr(lambda cmd: None).dispatch("workspace +1"))


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
