import unittest
from unittest.mock import Mock, patch

from v4.local_bridge_auth import save_bridge_key, valid_bridge_key
from v4.local_key_dialog import launch_dialog


class BridgeDialogSafetyTests(unittest.TestCase):
    def test_popup_module_imports_without_creating_a_window(self):
        self.assertTrue(callable(launch_dialog))

    def test_save_existing_valid_key_to_mocked_vault(self):
        backend = Mock()
        key = "ABCdef123" * 5 + "XYZ"
        with patch("v4.local_bridge_auth._keyring", return_value=backend):
            with patch("v4.local_bridge_auth.getpass.getuser", return_value="local-user"):
                save_bridge_key(key)
        backend.set_password.assert_called_once_with(
            "eve-v4-structure-market-bridge", "local-user", key)

    def test_rejected_value_never_overwrites_saved_credential(self):
        backend = Mock()
        with patch("v4.local_bridge_auth._keyring", return_value=backend):
            for value in ["", "abc", "A" * 48 + " ", "abc" * 10 + "\n"]:
                with self.assertRaises(ValueError):
                    save_bridge_key(value)
        backend.set_password.assert_not_called()
        self.assertTrue(valid_bridge_key("ABCdef123" * 5 + "XYZ"))


if __name__ == "__main__":
    unittest.main()
