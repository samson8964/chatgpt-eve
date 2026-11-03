import unittest
from types import SimpleNamespace

from v4.local_key_sync import sync_github, deploy_worker, REPO, DEPLOY_REF


class LocalKeySyncTests(unittest.TestCase):
    def test_key_is_sent_on_stdin_never_in_process_arguments(self):
        commands=[]
        def runner(argv, **kwargs):
            commands.append((argv,kwargs))
            return SimpleNamespace(returncode=0)
        result=sync_github(get_key=lambda:"x"*48,runner=runner)
        self.assertTrue(result["github_secret_updated"])
        self.assertEqual(len(commands),2)
        self.assertIn("secret",commands[1][0])
        self.assertEqual(commands[1][1]["input"],"x"*48)
        self.assertNotIn("x"*48," ".join(commands[1][0]))
        self.assertNotIn("x"*48,str(result))
        self.assertFalse(result["cloudflare_updated"])

    def test_missing_or_short_key_fails_without_network(self):
        for value in [None,"x"*8,""]:
            with self.subTest(value=value):
                def forbidden(*args,**kwargs):
                    raise AssertionError("should not run")
                with self.assertRaisesRegex(RuntimeError,"VAULT_KEY_MISSING_OR_WEAK"):
                    sync_github(get_key=lambda:value,runner=forbidden)

    def test_deploy_uses_isolated_ref_and_proves_only_queued(self):
        called=[]
        def runner(argv,**kwargs):
            called.append(argv)
            return SimpleNamespace(returncode=0)
        result=deploy_worker(runner=runner)
        self.assertEqual(called[-1][-1],DEPLOY_REF)
        self.assertIn(REPO,called[-1])
        self.assertFalse(result["verified_access"])
        self.assertFalse(result["email_sent"])

    def test_errors_do_not_expose_stdout_or_stderr(self):
        def failing(argv,**kwargs):
            return SimpleNamespace(returncode=1,stderr="sensitive",stdout="sensitive")
        with self.assertRaisesRegex(RuntimeError,"GITHUB_CLI_EXIT_NONZERO") as ctx:
            deploy_worker(runner=failing)
        self.assertNotIn("sensitive",str(ctx.exception))


if __name__=="__main__":
    unittest.main()
