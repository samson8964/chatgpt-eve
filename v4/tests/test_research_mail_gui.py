"""Read-only tests for the local Windows Gmail password dialog.

No GUI window opens in CI and no password is sent or stored in these tests.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from v4 import research_mail
from v4.research_mail_gui import normalized_length, saved_addresses


class GmailGuiSettingsTests(unittest.TestCase):
    def test_grouped_sixteen_character_app_password_is_counted(self):
        self.assertEqual(normalized_length("abcd efgh ijkl mnop"), 16)
        self.assertEqual(normalized_length("abcdefghijklmnop"), 16)
        self.assertEqual(normalized_length(" abc def "), 6)

    def test_prefill_nonsecret_addresses_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "config" / "research_gmail.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "schema": 1,
                "mode": "V4_CONTRACT_RESEARCH_ONLY",
                "sender": "someone@gmail.com",
                "recipient": "recipient@gmail.com",
                "enabled": True,
            }), encoding="utf-8")
            self.assertEqual(saved_addresses(root),
                             ("someone@gmail.com", "recipient@gmail.com"))
            self.assertEqual(normalized_length("xxxx xxxx xxxx xxxx"), 16)

    def test_bad_or_absent_settings_never_prefill_untrusted_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(saved_addresses(root), ("", ""))
            path = root / "config" / "research_gmail.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"schema":1,"mode":"NOT_OUR_APP","sender":"other@gmail.com"}')
            self.assertEqual(saved_addresses(root), ("", ""))
            path.write_text("{invalid")
            self.assertEqual(saved_addresses(root), ("", ""))

    def test_gui_flag_routes_to_dialog_no_console_password_prompt_or_send(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("sys.argv", ["v4.research_mail", "--gui", "--data-root", directory]), \\
                 patch("v4.research_mail_gui.launch_dialog", return_value=True) as open_gui, \\
                 patch("v4.research_mail.send_review") as send, \\
                 patch("v4.research_mail.getpass.getpass") as hidden:
                output = io.StringIO()
                with redirect_stdout(output):
                    research_mail.main()
            info = json.loads(output.getvalue())
            self.assertTrue(info["gui_saved"])
            self.assertFalse(info["secret_printed"])
            self.assertFalse(info["sent"])
            open_gui.assert_called_once_with(Path(directory))
            send.assert_not_called()
            hidden.assert_not_called()

    def test_no_desktop_or_network_dependency_for_import(self):
        from v4 import research_mail_gui
        src = Path(research_mail_gui.__file__).read_text(encoding="utf-8")
        self.assertIn('show="*"', src)
        self.assertIn("ttk.Checkbutton", src)
        self.assertIn("save_func(data_root, sender, recipient, secret)", src)
        self.assertNotIn("send_review(", src)
        self.assertNotIn("SMTP_SSL", src)
        self.assertNotIn("requests.post", src)


if __name__ == "__main__":
    unittest.main()
