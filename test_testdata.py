"""Unit tests for qafill testdata module.

The keyboard library installs a low-level Windows hook on import, which
interferes with tests and can mess with modifier key state. We mock it
(and ctypes) before importing testdata to avoid side effects.
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, mock_open


# Mock modules that cause side effects on import:
# - keyboard: installs a global Windows keyboard hook
# - ctypes: SetCurrentProcessExplicitAppUserModelID requires Windows shell
_keyboard_mock = MagicMock()
_keyboard_mock.KEY_DOWN = "down"
sys.modules.setdefault("keyboard", _keyboard_mock)

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
        # Restore original environment
        os.environ.clear()
        os.environ.update(self._original_env)

    def test_parses_simple_key_value(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".env", delete=False, dir=os.path.dirname(__file__)
        ) as f:
            f.write("TEST_QAFILL_KEY=test_value\n")
            env_path = f.name

        try:
            os.environ.pop("TEST_QAFILL_KEY", None)
            with patch("testdata.os.path.abspath", return_value=env_path):
                with patch("testdata.os.path.exists", return_value=True):
                    with patch("builtins.open", mock_open(read_data="TEST_QAFILL_KEY=test_value\n")):
                        testdata._load_dotenv()
            assert os.environ.get("TEST_QAFILL_KEY") == "test_value"
        finally:
            os.unlink(env_path)
            os.environ.pop("TEST_QAFILL_KEY", None)

    def test_skips_comments(self):
        env_content = "# this is a comment\nTEST_QAFILL_REAL=yes\n"
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

        os.environ.pop("TEST_QAFILL_REAL", None)
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=env_content)):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_REAL") == "yes"
        os.environ.pop("TEST_QAFILL_REAL", None)

    def test_skips_blank_lines(self):
        env_content = "\n\n  \nTEST_QAFILL_VAR=val\n"
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=env_content)):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_VAR") == "val"
        os.environ.pop("TEST_QAFILL_VAR", None)

    def test_strips_quotes(self):
        env_content = 'TEST_QAFILL_Q="quoted_value"\n'
        os.environ.pop("TEST_QAFILL_Q", None)
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=env_content)):
                testdata._load_dotenv()
        assert os.environ.get("TEST_QAFILL_Q") == "quoted_value"
        os.environ.pop("TEST_QAFILL_Q", None)

    def test_does_not_overwrite_existing(self):
        os.environ["TEST_QAFILL_EXIST"] = "original"
        env_content = "TEST_QAFILL_EXIST=new_value\n"
        with patch("testdata.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=env_content)):
                testdata._load_dotenv()
        assert os.environ["TEST_QAFILL_EXIST"] == "original"
        os.environ.pop("TEST_QAFILL_EXIST", None)

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
        # Sample center pixel - should be the fill color (blue)
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
        assert pixel == (30, 180, 30, 255), f"Armed (green) should override active (orange), got {pixel}"

    def test_corner_is_transparent(self):
        img = testdata.make_icon_image()
        pixel = img.getpixel((0, 0))
        assert pixel[3] == 0, f"Corner should be transparent, got alpha={pixel[3]}"


class TestLog(unittest.TestCase):
    """Tests for log() - file logging."""

    def test_writes_to_log_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmp_log = f.name

        original_log_path = testdata.LOG_PATH
        try:
            testdata.LOG_PATH = tmp_log
            testdata.log("test message")
            with open(tmp_log) as f:
                content = f.read()
            assert "test message" in content
        finally:
            testdata.LOG_PATH = original_log_path
            os.unlink(tmp_log)

    def test_log_format_has_timestamp(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmp_log = f.name

        original_log_path = testdata.LOG_PATH
        try:
            testdata.LOG_PATH = tmp_log
            testdata.log("format check")
            with open(tmp_log) as f:
                line = f.read().strip()
            # Format: "YYYY-MM-DD HH:MM:SS message"
            parts = line.split(" ", 2)
            assert len(parts) == 3
            assert len(parts[0]) == 10  # date
            assert len(parts[1]) == 8   # time
            assert parts[2] == "format check"
        finally:
            testdata.LOG_PATH = original_log_path
            os.unlink(tmp_log)

    def test_appends_multiple_entries(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            tmp_log = f.name

        original_log_path = testdata.LOG_PATH
        try:
            testdata.LOG_PATH = tmp_log
            testdata.log("first")
            testdata.log("second")
            with open(tmp_log) as f:
                lines = f.read().strip().split("\n")
            assert len(lines) == 2
            assert "first" in lines[0]
            assert "second" in lines[1]
        finally:
            testdata.LOG_PATH = original_log_path
            os.unlink(tmp_log)


class TestCopy(unittest.TestCase):
    """Tests for copy() - clipboard + paste behavior."""

    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_copies_to_clipboard(self, mock_time, mock_pyperclip, mock_keyboard):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        testdata.copy("Test", "test_value")
        mock_pyperclip.copy.assert_called_once_with("test_value")

    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_sends_ctrl_v(self, mock_time, mock_pyperclip, mock_keyboard):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        testdata.copy("Test", "test_value")
        mock_keyboard.send.assert_called_once_with("ctrl+v")

    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_updates_last_values(self, mock_time, mock_pyperclip, mock_keyboard):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        testdata.copy("MyLabel", "MyValue")
        assert testdata.last_label == "MyLabel"
        assert testdata.last_value == "MyValue"

    @patch("testdata.notification")
    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_notifies_when_enabled(self, mock_time, mock_pyperclip, mock_keyboard, mock_notif):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = True
        testdata.copy("Label", "Value")
        mock_notif.notify.assert_called_once()
        testdata.notifications_enabled = False

    @patch("testdata.notification")
    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_no_notification_when_disabled(self, mock_time, mock_pyperclip, mock_keyboard, mock_notif):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        testdata.copy("Label", "Value")
        mock_notif.notify.assert_not_called()

    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_releases_modifiers_before_paste(self, mock_time, mock_pyperclip, mock_keyboard):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
        testdata.copy("Test", "val")
        calls = [str(c) for c in mock_keyboard.release.call_args_list]
        assert any("ctrl" in c for c in calls)
        assert any("shift" in c for c in calls)


class TestRepeatLast(unittest.TestCase):
    """Tests for repeat_last() - replay previous value."""

    @patch("testdata.keyboard")
    @patch("testdata.pyperclip")
    @patch("testdata.time")
    def test_repeats_last_value(self, mock_time, mock_pyperclip, mock_keyboard):
        testdata.LOG_PATH = os.devnull
        testdata.notifications_enabled = False
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

    @patch("testdata.keyboard")
    def test_sets_armed_false(self, mock_keyboard):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._armed_hotkeys = []
        testdata._key_hook = None
        testdata.disarm_mode()
        assert testdata._armed is False

    @patch("testdata.keyboard")
    def test_cancels_timer(self, mock_keyboard):
        timer = MagicMock()
        testdata._armed = True
        testdata._arm_timer = timer
        testdata._armed_hotkeys = []
        testdata._key_hook = None
        testdata.disarm_mode()
        timer.cancel.assert_called_once()
        assert testdata._arm_timer is None

    @patch("testdata.keyboard")
    def test_removes_hotkeys(self, mock_keyboard):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._armed_hotkeys = ["hk1", "hk2"]
        testdata._key_hook = None
        testdata.disarm_mode()
        assert mock_keyboard.remove_hotkey.call_count == 2
        assert testdata._armed_hotkeys == []

    @patch("testdata.keyboard")
    def test_unhooks_key_hook(self, mock_keyboard):
        testdata._armed = True
        testdata._arm_timer = None
        testdata._armed_hotkeys = []
        testdata._key_hook = "some_hook"
        testdata.disarm_mode()
        mock_keyboard.unhook.assert_called_once_with("some_hook")
        assert testdata._key_hook is None

    @patch("testdata.keyboard")
    def test_idempotent_when_not_armed(self, mock_keyboard):
        testdata._armed = False
        testdata._arm_timer = None
        testdata._armed_hotkeys = []
        testdata._key_hook = None
        testdata.disarm_mode()  # should not raise
        mock_keyboard.remove_hotkey.assert_not_called()
        mock_keyboard.unhook.assert_not_called()

    @patch("testdata.keyboard")
    def test_survives_remove_hotkey_error(self, mock_keyboard):
        mock_keyboard.remove_hotkey.side_effect = Exception("already removed")
        testdata._armed = True
        testdata._arm_timer = None
        testdata._armed_hotkeys = ["hk1"]
        testdata._key_hook = None
        testdata.disarm_mode()  # should not raise
        assert testdata._armed is False

    @patch("testdata.keyboard")
    def test_survives_unhook_error(self, mock_keyboard):
        mock_keyboard.unhook.side_effect = Exception("already unhooked")
        testdata._armed = True
        testdata._arm_timer = None
        testdata._armed_hotkeys = []
        testdata._key_hook = "stale_hook"
        testdata.disarm_mode()  # should not raise
        assert testdata._key_hook is None


class TestArmMode(unittest.TestCase):
    """Tests for arm_mode() - arming state and chord registration."""

    def setUp(self):
        testdata.icon = MagicMock()
        testdata.LOG_PATH = os.devnull
        testdata._armed = False
        testdata._arm_timer = None
        testdata._armed_hotkeys = []
        testdata._key_hook = None
        testdata._arm_last_time = 0.0

    @patch("testdata.keyboard")
    def test_sets_armed_true(self, mock_keyboard):
        testdata.arm_mode()
        assert testdata._armed is True

    @patch("testdata.keyboard")
    def test_toggle_disarms_when_armed(self, mock_keyboard):
        testdata._armed = True
        testdata._arm_timer = None
        testdata.arm_mode()
        assert testdata._armed is False

    @patch("testdata.keyboard")
    def test_debounce_prevents_rapid_rearm(self, mock_keyboard):
        testdata._arm_last_time = testdata.time.time()
        testdata.arm_mode()
        assert testdata._armed is False  # should be debounced

    @patch("testdata.keyboard")
    def test_registers_chord_hotkeys(self, mock_keyboard):
        mock_keyboard.add_hotkey.return_value = "mock_hk"
        testdata.arm_mode()
        # Should register hotkeys for: n,f,l,e,p,a,z,c,r,t + 4 test cards + custom strings
        expected_count = 10 + len(testdata.TEST_CARDS) + len(testdata.CUSTOM_STRINGS)
        assert mock_keyboard.add_hotkey.call_count == expected_count

    @patch("testdata.keyboard")
    def test_updates_icon_to_armed(self, mock_keyboard):
        testdata.arm_mode()
        assert testdata.icon.icon is not None


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
            assert number.isdigit(), f"{label} card number contains non-digits: {number}"

    def test_expiry_format(self):
        for label, _, exp, _ in testdata.TEST_CARDS:
            parts = exp.split("/")
            assert len(parts) == 2, f"{label} expiry format wrong: {exp}"
            month, year = parts
            assert 1 <= int(month) <= 12, f"{label} invalid month: {month}"
            assert int(year) >= 2026, f"{label} year too old: {year}"

    def test_cards_not_expired(self):
        from datetime import datetime
        now = datetime.now()
        for label, _, exp, _ in testdata.TEST_CARDS:
            month, year = exp.split("/")
            # Card is valid through the end of the expiry month
            assert int(year) > now.year or (
                int(year) == now.year and int(month) >= now.month
            ), f"{label} test card is expired: {exp}"

    def test_cvv_length(self):
        for label, _, _, cvv in testdata.TEST_CARDS:
            assert cvv.isdigit(), f"{label} CVV contains non-digits"
            assert len(cvv) in (3, 4), f"{label} CVV unexpected length: {len(cvv)}"


class TestHotkeyReference(unittest.TestCase):
    """Tests for HOTKEY_REFERENCE structure."""

    def test_all_entries_are_tuples(self):
        for entry in testdata.HOTKEY_REFERENCE:
            assert isinstance(entry, tuple), f"Expected tuple, got {type(entry)}"
            assert len(entry) == 2, f"Expected 2 elements, got {len(entry)}"

    def test_all_entries_are_strings(self):
        for hotkey, desc in testdata.HOTKEY_REFERENCE:
            assert isinstance(hotkey, str), f"Hotkey not a string: {hotkey}"
            assert isinstance(desc, str), f"Description not a string: {desc}"

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
    """Tests for MODIFIER_KEYS set."""

    def test_contains_standard_modifiers(self):
        for mod in ['ctrl', 'shift', 'alt']:
            assert mod in testdata.MODIFIER_KEYS

    def test_contains_left_right_variants(self):
        for mod in ['left ctrl', 'right ctrl', 'left shift', 'right shift']:
            assert mod in testdata.MODIFIER_KEYS

    def test_regular_keys_not_included(self):
        for key in ['a', 'n', 'space', 'enter', '1', 'f1']:
            assert key not in testdata.MODIFIER_KEYS


class TestPhoneFormat(unittest.TestCase):
    """Tests for phone number generation format consistency."""

    def test_phone_format_consistent_length(self):
        import re
        pattern = re.compile(r'^\d{3}-\d{3}-\d{4}$')
        for _ in range(20):
            phone = testdata.fake.numerify('###-###-####')
            assert pattern.match(phone), f"Phone format mismatch: {phone}"
            assert len(phone) == 12, f"Phone length should be 12, got {len(phone)}"


if __name__ == "__main__":
    unittest.main()
