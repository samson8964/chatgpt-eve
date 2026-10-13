import json
import tempfile
import unittest
from pathlib import Path

from v4.ingest import read_proofs


class ProofIngestTests(unittest.TestCase):
    def test_all_proofs_preserved_not_just_mail_or_watch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"p.jsonl"
            rows=[
                {"status":"MAIL","instance":"contract:10001"},
                {"status":"RESEARCH","instance":"contract:10002"},
                {"status":"WATCH","instance":"contract:10003"},
                {"status":"RESEARCH","instance":None,"family":"market:12:21:34"}
            ]
            p.write_text("\n".join(json.dumps(x) for x in rows)+"\n",encoding="utf-8")
            loaded=list(read_proofs(p))
            self.assertEqual(len(loaded),4)
            self.assertEqual(loaded[3]["instance"],"market:12:21:34")

    def test_invalid_json_infinity_cannot_be_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"p.jsonl"
            p.write_text('{"instance":"contract:12345","stress":-Infinity}\n',encoding='utf-8')
            with self.assertRaises(ValueError):
                list(read_proofs(p))

    def test_invalid_instance_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"p.jsonl"
            p.write_text('{"status":"WATCH","instance":null}\n',encoding='utf-8')
            with self.assertRaises(ValueError):
                list(read_proofs(p))
