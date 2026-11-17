"""Offline regression for same-run receipts and health evidence."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from v4.desktop_health import read_health, health_lines, COMPLETE, _reference
from v4.unified_review import digest_counts

RUN="20261117T060000Z-abc12345"
STAMP="2026-11-17T06:05:00+00:00"
COUNTS={"market":6,"contract":2,"blueprint":1}

class HealthTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.write("config/research_gmail.json",{"enabled":True})
        self.write("config/eve_game_mail_review.json",{"enabled":True,"recipients":[
            {"name":"MikeChong","id":2124493042},{"name":"Arb Hunter","id":2124830062}]})
        self.manifest={"status":"SHADOW_RECORDED","coverage_gate":COMPLETE,
                       "source_input_integrity":"ALL_PARSED","structure_health":{}}
        self.log="START "+STAMP+"\nRESULT "+json.dumps({"run_folder_name":RUN})+"\n"
    def write(self,p,obj):
        path=self.root/p
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(obj),encoding="utf8")
    def health(self,scope="COMPLETE",status="SHADOW_RECORDED"):
        return read_health(self.root,self.manifest,RUN,scope,status,self.log)
    def test_receipts_and_counts_match_exact_run(self):
        self.log+="REVIEW_MAIL "+json.dumps({"run_folder_name":RUN,"digest_counts":COUNTS})+"\n"
        self.write("mail-review/receipts/"+RUN+".json",
                   {"run":RUN,"sent_at":STAMP,"research_only":True,"formal_mail":False})
        for name,ident in (("MikeChong",2124493042),("Arb Hunter",2124830062)):
            self.write("mail-review/eve-receipts/"+RUN+"-"+str(ident)+".json",
                       {"run":RUN,"recipient":name,"recipient_id":ident,
                        "source":"EVE_OFFICIAL_MAIL_VIA_EXISTING_WORKER","sender_id":2124679425,
                        "confirmed_at":STAMP,"mail_id":1,"research_only":True,"formal_trade_alert":False})
        h=self.health()
        self.assertEqual(h["counts"],COUNTS)
        self.assertEqual(h["gmail"],"ACCEPTED")
        self.assertEqual(set(h["game"].values()),{"ACCEPTED"})
        self.assertEqual(health_lines(h)["mail"][1],"green")
    def test_old_counts_and_bad_receipts_never_green(self):
        self.log+="REVIEW_MAIL "+json.dumps({"run_folder_name":"old","digest_counts":COUNTS})+"\n"
        self.write("mail-review/receipts/"+RUN+".json",{"run":"old","sent_at":STAMP})
        h=self.health()
        self.assertIsNone(h["counts"])
        self.assertEqual(h["gmail"],"UNCONFIRMED")
        self.assertIn("不是零机会",health_lines(h)["opportunities"][0])
    def test_partial_401_suppresses_count(self):
        self.manifest["structure_health"]={"cj":{"status":"FAILED","http_status":401}}
        self.log+="REVIEW_MAIL "+json.dumps({"run_folder_name":RUN,"digest_counts":COUNTS})+"\n"
        h=self.health("INCOMPLETE_COVERAGE")
        self.assertIsNone(h["counts"])
        self.assertEqual(h["station_errors"],{"HTTP 401":1})
    def test_independent_mail_failure(self):
        self.log+="REVIEW_MAIL_FAILED RuntimeError UNCLASSIFIED\n"
        self.log+="GAME_REVIEW_MAIL "+json.dumps({"run_folder_name":RUN,"recipients":{
            "Arb Hunter":{"status":"V4_GAME_RESEARCH_MAIL_RECIPIENT_FAILED"}}})+"\n"
        h=self.health()
        self.assertEqual(h["gmail"],"FAILED")
        self.assertEqual(h["game"]["Arb Hunter"],"FAILED")
        self.assertEqual(h["game"]["MikeChong"],"UNCONFIRMED")
    def test_new_start_cannot_reuse_old_counts(self):
        self.log+="REVIEW_MAIL "+json.dumps({"run_folder_name":RUN,"digest_counts":COUNTS})+"\n"
        self.log+="START "+STAMP+"\n"
        self.assertIsNone(self.health()["counts"])
    def test_cleanup_and_live_disk_no_database_required(self):
        self.write("config/rolling72-enabled.json",{"token":"V4_ROLLING_72_VERIFIED_EXTERNAL_BACKUP_V1"})
        self.log+="ROLLING72_CLEANUP "+json.dumps({"status":"NOT_NEEDED","blocked":80,
            "old_run_count_after":80,"keep_successful_runs":72,
            "blocked_reasons":{"GAME_MAIL_UNCONFIRMED:Arb Hunter":80}})+"\n"
        with patch("v4.desktop_health.shutil.disk_usage",return_value=type("D",(),{"free":19*1024**3})()):
            h=self.health()
        self.assertEqual(h["disk"]["severity"],"STOP")
        self.assertEqual(h["rolling"]["remaining"],80)
        self.assertIn("Arb回执缺失",health_lines(h)["cleanup_reason"][0])
        self.assertFalse((self.root/"sqlite").exists())
    def test_name_dictionary_and_history_status(self):
        p=self.root/"reference"/"mail-names.json.gz"
        p.parent.mkdir()
        with gzip.open(p,"wt",encoding="utf8") as f:
            json.dump({"schema":1,"types":{str(i):"中文" for i in range(10000)},
                       "stations":{str(i):"站" for i in range(1000)}},f)
        today=datetime.now(timezone.utc).date()
        self.write("reference/forge-regional-history-latest.json",
                   {"schema":1,"region_id":10000002,"source":"EVE_REF_ARCHIVE_ESI_FORGE_REGIONAL_DAILY_TRADE_AVERAGE",
                    "quotes":{"34":{}}, "built_on":today.isoformat(),
                    "latest_archive_date":(today-timedelta(days=1)).isoformat(),"days_available":5})
        h=self.health()
        self.assertEqual(h["names"]["chinese"],10000)
        self.assertEqual(h["history"]["status"],"RECENT")
    def test_digest_counts_same_gate_and_cap(self):
        review={"coverage_gate":COMPLETE,"source_input_integrity":"ALL_PARSED",
                "market_research_leads":[{}]*12,"contract_research_leads":[{}]*2,
                "blueprint_research_leads":[{}]*1}
        self.assertEqual(digest_counts(review),{"market":10,"contract":2,"blueprint":1})
        review["coverage_gate"]="PARTIAL"
        self.assertIsNone(digest_counts(review))

if __name__=="__main__":
    unittest.main()
