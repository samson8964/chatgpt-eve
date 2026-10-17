import tempfile
import unittest
from pathlib import Path
from v4.local_run import exclusive_lock, run


class LocalRunnerSafetyTests(unittest.TestCase):
    def test_nested_execution_lock_refuses_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            lock=Path(td)/"lockfile"
            with exclusive_lock(lock):
                with self.assertRaisesRegex(RuntimeError,"ANOTHER_V4_LOCAL_SCAN_RUNNING"):
                    with exclusive_lock(lock):
                        pass

    def test_repository_as_data_root_is_refused_without_network(self):
        repo=Path(__file__).resolve().parents[2]
        with self.assertRaisesRegex(ValueError,"DATA_ROOT_MUST_BE_OUTSIDE_REPOSITORY"):
            run(repo)


if __name__=="__main__":
    unittest.main()
