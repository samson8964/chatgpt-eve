import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

import send_v3_opportunity_mail as mail


def candidate(ident, profit=70_000_000):
    return {
        "id": ident,
        "profit": profit,
        "roi": 0.20,
        "score": 80,
        "grade": "A",
        "row": pd.Series({
            "item_name": "Test Item",
            "quantity": 1,
            "source_label": "C-J",
            "source_best_sell": 60_000_000,
            "jita_best_buy": 150_000_000,
            "stress_net_profit": 50_000_000,
        }),
    }


class EveDeliveryTests(unittest.TestCase):
    def test_empty_opportunities_do_not_generate_mail(self):
        with patch.object(mail, "recipient_names", return_value=["MikeChong", "LadyBaBa"]), \
             patch.object(mail, "resolve_character", side_effect=[1, 2]), \
             patch.object(mail, "enabled_channels", return_value=["v3-cj-to-jita"]), \
             patch.object(mail, "channel_healthy", return_value=True), \
             patch.object(mail, "build_candidates", return_value=[]), \
             patch.object(mail, "send_mail") as send:
            mail.main()
            send.assert_not_called()

    def test_all_channels_combined_once_per_recipient_and_acknowledged(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(mail, "STATE", Path(tmp)), \
             patch.object(mail, "recipient_names", return_value=["MikeChong", "LadyBaBa"]), \
             patch.object(mail, "resolve_character", side_effect=[1, 2]), \
             patch.object(mail, "enabled_channels", return_value=["v3-cj-to-jita", "v3-amarr-to-jita"]), \
             patch.object(mail, "channel_healthy", return_value=True), \
             patch.object(mail, "build_candidates", side_effect=[[candidate(10)], [candidate(11)]]), \
             patch.object(mail.time, "sleep"), \
             patch.object(mail, "send_mail") as send:
            mail.main()
            self.assertEqual(send.call_count, 2)
            for call in send.call_args_list:
                self.assertIn("C-J→Jita", call.args[2])
                self.assertIn("Amarr→Jita", call.args[2])
            for char in ("MikeChong", "LadyBaBa"):
                for channel in ("v3-cj-to-jita", "v3-amarr-to-jita"):
                    self.assertTrue(mail.state_path(channel, char).exists())

    def test_esi_520_preserves_unsent_state_and_avoids_extra_retries(self):
        err_response = requests.Response()
        err_response.status_code = 502
        err_response._content = b"EVE mail failed (520): error code: 520"
        failure = requests.exceptions.HTTPError("502", response=err_response)
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(mail, "STATE", Path(tmp)), \
             patch.object(mail, "recipient_names", return_value=["LadyBaBa"]), \
             patch.object(mail, "resolve_character", return_value=2), \
             patch.object(mail, "enabled_channels", return_value=["v3-cj-to-jita"]), \
             patch.object(mail, "channel_healthy", return_value=True), \
             patch.object(mail, "build_candidates", return_value=[candidate(10)]), \
             patch.object(mail, "send_mail", side_effect=failure) as send:
            with self.assertRaisesRegex(RuntimeError, "1 recipient"):
                mail.main()
            self.assertEqual(send.call_count, 1)
            self.assertFalse(mail.state_path("v3-cj-to-jita", "LadyBaBa").exists())

    def test_long_sections_are_deferred_not_marked_as_sent(self):
        a, b = candidate(10), candidate(11)
        included, body = mail.compose_digest(
            [("v3-cj-to-jita", [a]), ("v3-amarr-to-jita", [b])],
            "10-10 21:00",
            max_body_chars=75,
        )
        self.assertLessEqual(len(body), 75)
        self.assertEqual(len(included), 0)


if __name__ == "__main__":
    unittest.main()
