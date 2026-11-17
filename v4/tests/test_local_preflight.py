import unittest

from v4.local_preflight import assess


class LocalPreflightTests(unittest.TestCase):
    def test_windows_311_ready_for_shadow_but_never_mail(self):
        result = assess((3, 11, 9), "Windows", 45 * 1024**3,
                        {"pandas": True, "numpy": True, "requests": True})
        self.assertTrue(result["ready_to_attempt_shadow"])
        self.assertFalse(result["safe_to_activate_mail"])
        self.assertTrue(result["disk_capacity_not_yet_sized"])

    def test_missing_dependency_blocks_shadow(self):
        result = assess((3, 11, 9), "Windows", 50 * 1024**3,
                        {"pandas": False, "numpy": True, "requests": True})
        self.assertEqual(result["missing_dependencies"], ["pandas"])
        self.assertFalse(result["ready_to_attempt_shadow"])

    def test_python_too_old_blocks_shadow(self):
        result = assess((3, 10, 10), "Windows", 200 * 1024**3,
                        {"pandas": True, "numpy": True, "requests": True})
        self.assertFalse(result["ready_to_attempt_shadow"])


if __name__ == "__main__":
    unittest.main()
