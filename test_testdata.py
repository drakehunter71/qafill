"""Unit tests for qafill testdata module.

pynput is safe to import (no hooks installed until Listener.start()),
so we import testdata directly. The __main__ guard prevents side effects.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open
from pynput.keyboard import Key, KeyCode

import testdata


class TestResolve(unittest.TestCase):
    """Tests for resolve() - callable vs literal handling."""

    def test_literal_string(self):
        assert testdata.resolve("hello") == "hello"

    def test_callable(self):
        assert testdata.resolve(lambda: "from_lambda") == "from_lambda"

    def test_callable_with_args_default(self):
        fn = lambda x="default": x
        assert testdata.resolve(fn) == "default"

    def test_error_returns_error_string(self):
        def bad():
            raise ValueError("boom")
        result = testdata.resolve(bad)
        assert "[error:" in result
        assert "boom" in result

    def test_none_literal(self):
        assert testdata.resolve(None) is None

    def test_integer_literal(self):
        assert testdata.resolve(42) == 42

    def test_empty_string(self):
        assert testdata.resolve("") == ""


class TestLoadDotenv(unittest.TestCase):
    """Tests for _load_dotenv() - .env file parsing."""

    def setUp(self):
        self._original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._original_env)

    def test_parses_simple_key_value(self):
        os.environ.pop("TEST_QAFILL_KEY", None)
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="TEST_QAFILL_KEY=test_value\n")):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_KEY") == "test_value"

    def test_skips_comments(self):
        os.environ.pop("TEST_QAFILL_REAL", None)
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="# comment\nTEST_QAFILL_REAL=yes\n")):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_REAL") == "yes"

    def test_skips_blank_lines(self):
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="\n\n  \nTEST_QAFILL_VAR=val\n")):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_VAR") == "val"

    def test_strips_quotes(self):
        os.environ.pop("TEST_QAFILL_Q", None)
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data='TEST_QAFILL_Q="quoted_value"\n')):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_Q") == "quoted_value"

    def test_does_not_overwrite_existing(self):
        os.environ["TEST_QAFILL_EXIST"] = "original"
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="TEST_QAFILL_EXIST=new_value\n")):
                testdata._load_dotenv()
        assert os.environ["TEST_QAFILL_EXIST"] == "original"

    def test_no_env_file(self):
        with patch("testdata.os.path.exists", return_value=False):
            testdata._load_dotenv()  # should not raise


class TestMakeIconImage(unittest.TestCase):
    """Tests for make_icon_image() - tray icon generation."""

    def test_returns_rgba_image(self):
        img = testdata.make_icon_image()
        assert img.mode == "RGBA"

    def test_size_32x32(self):
        img = testdata.make_icon_image()
        assert img.size == (32, 32)

    def test_idle_is_blue(self):
        img = testdata.make_icon_image(active=False, armed=False)
        pixel = img.getpixel((16, 16))
        assert pixel == (30, 120, 220, 255), f"Expected blue, got {pixel}"

    def test_armed_is_green(self):
        img = testdata.make_icon_image(armed=True)
        pixel = img.getpixel((16, 16))
        assert pixel == (30, 180, 30, 255), f"Expected green, got {pixel}"

    def test_active_is_orange(self):
        img = testdata.make_icon_image(active=True)
        pixel = img.getpixel((16, 16))
        assert pixel == (220, 120, 30, 255), f"Expected orange, got {pixel}"

    def test_armed_takes_priority_over_active(self):
        img = testdata.make_icon_image(active=True, armed=True)
        pixel = img.getpixel((16, 16))
        assert pixel == (30, 180, 30, 255), f"Armed should override active, got {pixel}"

    def test_corner_is_transparent(self):
        img = testdata.make_icon_image()
        pixel = img.getpixel((0, 0))
        assert pixel[3] == 0, f"Corner should be transparent, got alpha={pixel[3]}"


class TestLog(unittest.TestCase):
    """Tests for log() - file logging."""

    def test_writes_to_log_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmp_log = f.name
        original = testdata.LOG_PATH
        try:
            testdata.LOG_PATH = tmp_log
            testdata.log("test message")
            with open(tmp_log) as f:
                assert "test message" in f.read()
        finally:
            testdata.LOG_PATH = original
            os.unlink(tmp_log)

    def test_log_format_has_timestamp(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmp_log = f.name
        original = testdata.LOG_PATH
        try:
            testdata.LOG_PATH = tmp_log
            testdata.log("format check")
            with open(tmp_log) as f:
                line = f.read().strip()
            parts = line.split(" ", 2)
            assert len(parts) == 3
            assert len(parts[0]) == 10  # YYYY-MM-DD
            assert len(parts[1]) == 8   # HH:MM:SS
            assert parts[2] == "format check"
        finally:
            testdata.LOG_PATH = original
            os.unlink(tmp_log)

    def test_appends_multiple_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmp_log = f.name
        original = testdata.LOG_PATH
        try:
            testdata.LOG_PATH = tmp_log
            testdata.log("first")
            testdata.log("second")
            with open(tmp_log) as f:
                lines = f.read().strip().split("\n")
            assert len(lines) == 2
        finally:
            testdata.LOG_PATH = original
            os.unlink(tmp_log)


class TestCopy(unittest.TestCase):
    """Tests for copy() - clipboard + paste behavior."""

    def setUp(self):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        self._orig_controller = testdata._controller
        testdata._controller = MagicMock()

    def tearDown(self):
        testdata._controller = self._orig_controller

    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_copies_to_clipboard(self, mock_time, mock_pyperclip):
        testdata.copy("Test", "test_value")
        mock_pyperclip.copy.assert_called_once_with("test_value")

    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_sends_ctrl_v_via_controller(self, mock_time, mock_pyperclip):
        testdata.copy("Test", "test_value")
        # Controller should press ctrl then v, then release both
        press_calls = [c.args[0] for c in testdata._controller.press.call_args_list]
        release_calls = [c.args[0] for c in testdata._controller.release.call_args_list]
        assert Key.ctrl_l in press_calls
        assert 'v' in press_calls
        assert 'v' in release_calls
        assert Key.ctrl_l in release_calls

    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_updates_last_values(self, mock_time, mock_pyperclip):
        testdata.copy("MyLabel", "MyValue")
        assert testdata.last_label == "MyLabel"
        assert testdata.last_value == "MyValue"

    @patch("testdata.notification")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_notifies_when_enabled(self, mock_time, mock_pyperclip, mock_notif):
        testdata.notifications_enabled = True
        testdata.copy("Label", "Value")
        mock_notif.notify.assert_called_once()
        testdata.notifications_enabled = False

    @patch("testdata.notification")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_no_notification_when_disabled(self, mock_time, mock_pyperclip, mock_notif):
        testdata.copy("Label", "Value")
        mock_notif.notify.assert_not_called()

    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_releases_modifiers_before_paste(self, mock_time, mock_pyperclip):
        testdata.copy("Test", "val")
        release_calls = [c.args[0] for c in testdata._controller.release.call_args_list]
        # Should release both ctrl and shift variants before the paste
        assert Key.ctrl_l in release_calls
        assert Key.ctrl_r in release_calls
        assert Key.shift_l in release_calls
        assert Key.shift_r in release_calls


class TestRepeatLast(unittest.TestCase):
    """Tests for repeat_last() - replay previous value."""

    def setUp(self):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        self._orig_controller = testdata._controller
        testdata._controller = MagicMock()

    def tearDown(self):
        testdata._controller = self._orig_controller

    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_repeats_last_value(self, mock_time, mock_pyperclip):
        testdata.last_label = "Name"
        testdata.last_value = "John"
        testdata.repeat_last()
        mock_pyperclip.copy.assert_called_with("John")

    def test_does_nothing_when_no_last(self):
        testdata.last_value = None
        testdata.repeat_last()  # should not raise


class TestToggleNotifications(unittest.TestCase):
    """Tests for toggle_notifications() - state toggle."""

    @patch("testdata.notification")
    def test_toggles_on(self, mock_notif):
        testdata.notifications_enabled = False
        testdata.icon = MagicMock()
        testdata._armed = False
        testdata.toggle_notifications()
        assert testdata.notifications_enabled is True

    @patch("testdata.notification")
    def test_toggles_off(self, mock_notif):
        testdata.notifications_enabled = True
        testdata.icon = MagicMock()
        testdata._armed = False
        testdata.toggle_notifications()
        assert testdata.notifications_enabled is False

    @patch("testdata.notification")
    def test_updates_icon(self, mock_notif):
        testdata.notifications_enabled = False
        testdata.icon = MagicMock()
        testdata._armed = False
        testdata.toggle_notifications()
        assert testdata.icon.icon is not None


class TestDisarmMode(unittest.TestCase):
    """Tests for disarm_mode() - state cleanup."""

    def setUp(self):
        testdata.icon = MagicMock()
        testdata.LOG_PATH = os.devnull

    def test_sets_armed_false(self):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._chord_map = {"n": lambda: None}
        testdata.disarm_mode()
        assert testdata._armed is False

    def test_clears_chord_map(self):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._chord_map = {"n": lambda: None, "f": lambda: None}
        testdata.disarm_mode()
        assert testdata._chord_map == {}

    def test_cancels_timer(self):
        timer = MagicMock()
        testdata._armed = True
        testdata._arm_timer = timer
        testdata._chord_map = {}
        testdata.disarm_mode()
        timer.cancel.assert_called_once()
        assert testdata._arm_timer is None

    def test_idempotent_when_not_armed(self):
        testdata._armed = False
        testdata._chord_map = {}
        testdata.disarm_mode()  # should not raise or change state
        assert testdata._armed is False

    def test_updates_icon(self):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._chord_map = {}
        testdata.disarm_mode()
        assert testdata.icon.icon is not None


class TestArmMode(unittest.TestCase):
    """Tests for arm_mode() - arming state and chord map."""

    def setUp(self):
        testdata.icon = MagicMock()
        testdata.LOG_PATH = os.devnull
        testdata._armed = False
        testdata._arm_timer = None
        testdata._arm_last_time = 0.0
        testdata._chord_map = {}

    def test_sets_armed_true(self):
        testdata.arm_mode()
        assert testdata._armed is True

    def test_builds_chord_map(self):
        testdata.arm_mode()
        # Core keys + test cards + custom strings
        for key in ["n", "f", "l", "e", "p", "a", "z", "c", "r", "t"]:
            assert key in testdata._chord_map, f"Missing chord key: {key}"
        for i in range(1, len(testdata.TEST_CARDS) + 1):
            assert str(i) in testdata._chord_map, f"Missing card key: {i}"

    def test_toggle_disarms_when_armed(self):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._chord_map = {"n": lambda: None}
        testdata.arm_mode()
        assert testdata._armed is False

    def test_debounce_prevents_rapid_rearm(self):
        testdata._arm_last_time = testdata.time.time()
        testdata.arm_mode()
        assert testdata._armed is False

    def test_updates_icon_to_armed(self):
        testdata.arm_mode()
        assert testdata.icon.icon is not None

    def test_starts_auto_disarm_timer(self):
        testdata.arm_mode()
        assert testdata._arm_timer is not None
        testdata._arm_timer.cancel()  # clean up


class TestOnPress(unittest.TestCase):
    """Tests for _on_press() - key event handler."""

    def setUp(self):
        testdata.icon = MagicMock()
        testdata.LOG_PATH = os.devnull
        testdata._armed = False
        testdata._arm_timer = None
        testdata._arm_last_time = 0.0
        testdata._chord_map = {}
        testdata._current_modifiers = set()

    def tearDown(self):
        # Clean up any timers left by arm_mode
        if testdata._arm_timer:
            testdata._arm_timer.cancel()
            testdata._arm_timer = None
        testdata._armed = False
        testdata._chord_map = {}
        testdata._current_modifiers = set()

    def test_arm_combo_ctrl_shift_space(self):
        testdata._on_press(Key.ctrl_l)
        testdata._on_press(Key.shift_l)
        testdata._on_press(Key.space)
        assert testdata._armed is True

    def test_arm_combo_requires_all_three(self):
        testdata._on_press(Key.ctrl_l)
        testdata._on_press(Key.space)  # no shift
        assert testdata._armed is False

    def test_modifier_keys_tracked(self):
        testdata._on_press(Key.ctrl_l)
        assert Key.ctrl_l in testdata._current_modifiers
        testdata._on_press(Key.shift_r)
        assert Key.shift_r in testdata._current_modifiers

    def test_non_chord_key_disarms(self):
        testdata._armed = True
        testdata._chord_map = {"n": lambda: None}
        testdata._on_press(KeyCode.from_char('x'))  # not in chord map
        assert testdata._armed is False

    def test_modifier_does_not_disarm(self):
        testdata._armed = True
        testdata._chord_map = {"n": lambda: None}
        testdata._on_press(Key.ctrl_l)
        assert testdata._armed is True


class TestOnRelease(unittest.TestCase):
    """Tests for _on_release() - modifier tracking cleanup."""

    def test_removes_modifier(self):
        testdata._current_modifiers = {Key.ctrl_l, Key.shift_l}
        testdata._on_release(Key.ctrl_l)
        assert Key.ctrl_l not in testdata._current_modifiers
        assert Key.shift_l in testdata._current_modifiers

    def test_ignores_unknown_key(self):
        testdata._current_modifiers = set()
        testdata._on_release(Key.ctrl_l)  # not in set - should not raise


class TestKeyChar(unittest.TestCase):
    """Tests for _key_char() - key to string conversion."""

    def test_regular_character(self):
        assert testdata._key_char(KeyCode.from_char('n')) == 'n'

    def test_uppercase_lowered(self):
        assert testdata._key_char(KeyCode.from_char('N')) == 'n'

    def test_number_key(self):
        assert testdata._key_char(KeyCode.from_char('5')) == '5'

    def test_special_key_returns_none(self):
        assert testdata._key_char(Key.space) is None

    def test_modifier_returns_none(self):
        assert testdata._key_char(Key.ctrl_l) is None


class TestIsArmCombo(unittest.TestCase):
    """Tests for _is_arm_combo() - ARM key detection."""

    def setUp(self):
        testdata._current_modifiers = set()

    def test_space_with_ctrl_shift(self):
        testdata._current_modifiers = {Key.ctrl_l, Key.shift_l}
        assert testdata._is_arm_combo(Key.space) is True

    def test_space_without_shift(self):
        testdata._current_modifiers = {Key.ctrl_l}
        assert testdata._is_arm_combo(Key.space) is False

    def test_space_without_ctrl(self):
        testdata._current_modifiers = {Key.shift_l}
        assert testdata._is_arm_combo(Key.space) is False

    def test_non_space_key(self):
        testdata._current_modifiers = {Key.ctrl_l, Key.shift_l}
        assert testdata._is_arm_combo(KeyCode.from_char('n')) is False

    def test_right_modifier_variants(self):
        testdata._current_modifiers = {Key.ctrl_r, Key.shift_r}
        assert testdata._is_arm_combo(Key.space) is True


class TestCtrlShiftHelpers(unittest.TestCase):
    """Tests for _ctrl_held() and _shift_held() helpers."""

    def setUp(self):
        testdata._current_modifiers = set()

    def test_ctrl_held_left(self):
        testdata._current_modifiers.add(Key.ctrl_l)
        assert testdata._ctrl_held() is True

    def test_ctrl_held_right(self):
        testdata._current_modifiers.add(Key.ctrl_r)
        assert testdata._ctrl_held() is True

    def test_ctrl_not_held(self):
        assert testdata._ctrl_held() is False

    def test_shift_held_left(self):
        testdata._current_modifiers.add(Key.shift_l)
        assert testdata._shift_held() is True

    def test_shift_not_held(self):
        assert testdata._shift_held() is False


class TestTestCards(unittest.TestCase):
    """Tests for TEST_CARDS data integrity."""

    def test_four_cards(self):
        assert len(testdata.TEST_CARDS) == 4

    def test_card_tuple_structure(self):
        for card in testdata.TEST_CARDS:
            assert len(card) == 4, f"Card should have 4 fields: {card}"
            label, number, exp, cvv = card
            assert isinstance(label, str)
            assert isinstance(number, str)
            assert isinstance(exp, str)
            assert isinstance(cvv, str)

    def test_card_numbers_are_digits(self):
        for label, number, _, _ in testdata.TEST_CARDS:
            assert number.isdigit(), f"{label} card number has non-digits: {number}"

    def test_expiry_format(self):
        for label, _, exp, _ in testdata.TEST_CARDS:
            month, year = exp.split("/")
            assert 1 <= int(month) <= 12, f"{label} invalid month: {month}"
            assert int(year) >= 2026, f"{label} year too old: {year}"

    def test_cards_not_expired(self):
        from datetime import datetime
        now = datetime.now()
        for label, _, exp, _ in testdata.TEST_CARDS:
            month, year = exp.split("/")
            assert int(year) > now.year or (
                int(year) == now.year and int(month) >= now.month
            ), f"{label} test card is expired: {exp}"

    def test_cvv_length(self):
        for label, _, _, cvv in testdata.TEST_CARDS:
            assert cvv.isdigit(), f"{label} CVV has non-digits"
            assert len(cvv) in (3, 4), f"{label} CVV unexpected length: {len(cvv)}"


class TestHotkeyReference(unittest.TestCase):
    """Tests for HOTKEY_REFERENCE structure."""

    def test_all_entries_are_tuples(self):
        for entry in testdata.HOTKEY_REFERENCE:
            assert isinstance(entry, tuple)
            assert len(entry) == 2

    def test_all_entries_are_strings(self):
        for hotkey, desc in testdata.HOTKEY_REFERENCE:
            assert isinstance(hotkey, str)
            assert isinstance(desc, str)

    def test_contains_arm_key(self):
        keys = [h for h, _ in testdata.HOTKEY_REFERENCE]
        assert any("Ctrl" in k and "Shift" in k and "Space" in k for k in keys)

    def test_contains_core_hotkeys(self):
        keys = [h for h, _ in testdata.HOTKEY_REFERENCE]
        for expected in ["N", "F", "L", "E", "P", "A", "Z", "C", "R", "T"]:
            assert expected in keys, f"Missing hotkey: {expected}"

    def test_contains_test_card_entries(self):
        descs = [d for _, d in testdata.HOTKEY_REFERENCE]
        for card_label, _, _, _ in testdata.TEST_CARDS:
            assert any(card_label in d for d in descs), f"Missing card: {card_label}"


class TestModifierKeys(unittest.TestCase):
    """Tests for _MODIFIER_KEYS set."""

    def test_contains_ctrl_variants(self):
        assert Key.ctrl_l in testdata._MODIFIER_KEYS
        assert Key.ctrl_r in testdata._MODIFIER_KEYS

    def test_contains_shift_variants(self):
        assert Key.shift_l in testdata._MODIFIER_KEYS
        assert Key.shift_r in testdata._MODIFIER_KEYS

    def test_contains_alt_variants(self):
        assert Key.alt_l in testdata._MODIFIER_KEYS
        assert Key.alt_r in testdata._MODIFIER_KEYS

    def test_contains_lock_keys(self):
        assert Key.caps_lock in testdata._MODIFIER_KEYS
        assert Key.num_lock in testdata._MODIFIER_KEYS

    def test_space_not_included(self):
        assert Key.space not in testdata._MODIFIER_KEYS


class TestPhoneFormat(unittest.TestCase):
    """Tests for phone number generation format consistency."""

    def test_phone_format_consistent_length(self):
        import re
        pattern = re.compile(r'^\d{3}-\d{3}-\d{4}$')
        for _ in range(20):
            phone = testdata.fake.numerify('###-###-####')
            assert pattern.match(phone), f"Phone format mismatch: {phone}"
            assert len(phone) == 12


if __name__ == "__main__":
    unittest.main()
