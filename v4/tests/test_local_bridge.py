import unittest
import sys
from v4.local_bridge_probe import probe
from v4.local_bridge_auth import valid_bridge_key

class BridgeProbeTests(unittest.TestCase):
    def test_credential_validator_matches_safe_vault_input(self):
        self.assertTrue(valid_bridge_key("A1" * 24))
        for value in (None, "", "x" * 31, "x" * 257,
                      " " + "A1" * 24, "A1" * 24 + "\\n", "密钥" * 24):
            with self.subTest(kind=type(value).__name__):
                self.assertFalse(valid_bridge_key(value))

    @unittest.skipUnless(sys.platform == "win32", "Windows vault check")
    def test_backend_is_windows_native_vault(self):
        from v4.local_bridge_auth import _keyring
        backend = _keyring().get_keyring()
        self.assertTrue(type(backend).__module__.startswith("keyring.backends.Windows"))

    def test_missing_credential_does_not_make_network_call(self):
        def fail(*args,**kwargs):
            raise AssertionError("No network allowed")
        check=probe(fetch=fail,env={})
        self.assertEqual(check["probe_result"],"MISSING_KEY")
        self.assertEqual(set(check["structures"]),{"four_h","cj","o4t"})
        self.assertFalse(check["mail_enabled"])

if __name__=="__main__":
    unittest.main()
