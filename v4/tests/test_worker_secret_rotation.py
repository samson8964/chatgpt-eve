import unittest
from pathlib import Path


class RotationWorkflowSafetyTests(unittest.TestCase):
    def test_worker_deploy_syncs_secret_before_authenticated_probes(self):
        path = Path(__file__).resolve().parents[2]/".github"/"workflows"/"deploy-cloudflare-worker.yml"
        raw=path.read_text("utf-8")
        sync=raw.index("Sync EVE API key to the existing Cloudflare Worker")
        verify=raw.index("Verify deployed Worker health")
        self.assertLess(sync,verify)
        segment=raw[sync:verify]
        self.assertIn("secret put MAIL_API_KEY",segment)
        self.assertIn('printf \'%s\' "$EVE_MAIL_API_KEY"',segment)
        self.assertNotIn("::set-output",segment)
        self.assertIn("workflow_dispatch:",raw)


if __name__=="__main__":
    unittest.main()
