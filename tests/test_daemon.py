"""End-to-end test of the daemon loop with a fake pad (see daemon_harness.py)."""

import json
import os
import subprocess
import sys
import unittest

from evdev import ecodes as e

HERE = os.path.dirname(os.path.abspath(__file__))


class DaemonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run([sys.executable, os.path.join(HERE, "daemon_harness.py")],
                             capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(out.stderr)
        cls.r = json.loads(out.stdout.strip().splitlines()[-1])
        cls.log = cls.r["log"]
        cls.marks = cls.r["marks"]

    def between(self, a, b):
        return self.log[self.marks[a][0]:self.marks[b][0]]

    def keys(self, events):
        return [(code, value) for _, t, code, value in events if t == e.EV_KEY]

    def test_idle_without_stream(self):
        self.assertEqual(self.marks["before_stream"][0], 0, "nothing may be sent before the stream starts")
        self.assertEqual(self.marks["before_stream"][1], 0, "pad must not be grabbed before the stream")

    def test_grabs_pad_when_stream_starts(self):
        self.assertEqual(self.r["grabs"][0], "grab")
        self.assertTrue(any("pulpitem" in n for n in self.r["notes"]))

    def test_stick_moves_mouse(self):
        moves = [v for name, t, code, v in self.between("stream_on", "moved") if t == e.EV_REL and code == e.REL_X]
        self.assertGreater(sum(moves), 300)
        self.assertTrue(all(name == "tv-pad mouse" for name, t, *_ in self.between("stream_on", "moved")))

    def test_buttons(self):
        keys = self.keys(self.between("moved", "buttons"))
        self.assertEqual(keys, [
            (e.BTN_LEFT, 1), (e.BTN_LEFT, 0),
            (e.KEY_ENTER, 1), (e.KEY_ENTER, 0),
            (e.KEY_LEFTMETA, 1), (e.KEY_C, 1), (e.KEY_C, 0), (e.KEY_LEFTMETA, 0),
        ])

    def test_pauses_for_game_window(self):
        self.assertEqual(self.keys(self.between("focus_game", "pressed_in_game")), [])
        grabs_before, grabs_after = self.marks["buttons"][1], self.marks["focus_game"][1]
        self.assertIn("ungrab", self.r["grabs"][grabs_before:grabs_after])

    def test_user_pause_with_xbox_hold(self):
        self.assertTrue(any("pauza" in n for n in self.r["notes"]))
        events = self.log[self.marks["pressed_in_game"][0]:self.marks["user_paused"][0]]
        self.assertNotIn((e.BTN_LEFT, 1), self.keys(events))

    def test_stream_start_blanks_the_monitor(self):
        calls = self.r["session"][:self.r["session_marks"]["stream_on"]]
        self.assertIn(["ddcutil", "--noverify", "setvcp", "10", "0"], calls)
        self.assertIn(["ddcutil", "--noverify", "setvcp", "12", "0"], calls)
        self.assertTrue(any("Monitor wygaszony" in n for n in self.r["notes"]))

    def test_key_on_physical_keyboard_wakes_the_monitor(self):
        m = self.r["session_marks"]
        self.assertEqual(self.r["session"][m["before_key"]:m["after_key"]],
                         [["ddcutil", "--noverify", "setvcp", "12", "40"],
                          ["ddcutil", "--noverify", "setvcp", "10", "55"]])
        self.assertIn("Monitor włączony", self.r["notes"])
        self.assertNotIn("grab-keyboard", self.r["grabs"])  # the keyboard is only listened to

    def test_keyboard_is_read_only_while_the_monitor_is_black(self):
        # opened when the stream starts, closed after waking; reopened only when the
        # stream starts again (resume after pause, Steam stream), never in between
        self.assertGreaterEqual(self.r["kbd_state"]["opens_after_wake"], 1)
        self.assertLessEqual(self.r["kbd_opens"], 4)

    def test_brightness_left_from_a_crash_is_restored_at_start(self):
        self.assertEqual(self.r["session"][0], ["ddcutil", "--noverify", "setvcp", "10", "33"])

    def test_paused_stream_releases_pad(self):
        self.assertEqual(self.keys(self.between("user_paused", "stream_paused")), [])
        grabs = self.r["grabs"][self.marks["user_paused"][1]:self.marks["stream_paused"][1]]
        self.assertNotIn("grab", grabs)

    def test_resumed_stream_takes_pad_again(self):
        self.assertEqual(self.keys(self.between("stream_paused", "stream_resumed")),
                         [(e.BTN_LEFT, 1), (e.BTN_LEFT, 0)])
        grabs = self.r["grabs"][self.marks["stream_paused"][1]:self.marks["stream_resumed"][1]]
        self.assertEqual(grabs, ["grab"])

    def test_view_left_ends_stream(self):
        self.assertIn("api-close", self.r["session"])
        self.assertFalse(self.r["flag_after_end"])
        self.assertTrue(any("Kończę stream" in n for n in self.r["notes"]))
        # neither the arrow key nor Alt+Tab went to the desktop, and the pad was let go
        self.assertEqual(self.keys(self.between("game_closed", "ended_by_pad")), [])
        grabs = self.r["grabs"][self.marks["game_closed"][1]:self.marks["ended_by_pad"][1]]
        self.assertEqual(grabs, ["ungrab"])

    def test_game_gets_the_pad_until_it_closes(self):
        self.assertEqual(self.keys(self.between("stream_resumed", "game_running")), [])
        self.assertIn("ungrab", self.r["grabs"][self.marks["stream_resumed"][1]:self.marks["game_running"][1]])
        self.assertTrue(any(n.startswith("Gra:") for n in self.r["notes"]))
        self.assertEqual(self.keys(self.between("game_running", "game_closed")), [(e.BTN_LEFT, 1), (e.BTN_LEFT, 0)])
        self.assertIn("grab", self.r["grabs"][self.marks["game_running"][1]:self.marks["game_closed"][1]])

    def test_stream_end(self):
        self.assertEqual(self.keys(self.between("ended_by_pad", "before_steam")), [])
        self.assertEqual(self.r["grabs"][-1], "ungrab")

    def test_steam_stream_leaves_pad_to_the_game(self):
        steam = self.log[self.marks["before_steam"][0]:self.marks["steam_done"][0]]
        self.assertEqual(steam, [], "no keys and no mouse movement on the desktop during a Steam stream")
        grabs = self.r["grabs"][self.marks["before_steam"][1]:self.marks["steam_done"][1]]
        self.assertNotIn("grab", grabs)
        self.assertGreaterEqual(sum(n.startswith("Gra:") for n in self.r["notes"]), 2)  # game + Steam stream

    def test_steam_stream_ends_with_view_left(self):
        self.assertEqual(self.r["session"].count("api-close"), 2)
        self.assertFalse(self.r["flag_after_steam"])


if __name__ == "__main__":
    unittest.main()
