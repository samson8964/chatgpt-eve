"""Regressions for mid-stream EVE Ref disconnections that previously killed V4.

Offline-only; fake HTTP response contexts are streamed like requests responses.
"""
from __future__ import annotations

import bz2
import http.client
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from requests.exceptions import ChunkedEncodingError
    from v4.sources import SourceError, download_fresh
except ImportError:
    # Lightweight reliability CI intentionally omits pandas/requests. The
    # full Windows/Ubuntu V4 suite installs both and runs the stream tests.
    ChunkedEncodingError = None
    SourceError = None
    download_fresh = None


class FakeResponse:
    def __init__(self, body, *, stop_after=None, exc=None, claimed_length=None):
        self.body=body
        self.stop_after=stop_after
        self.exc=exc
        self.headers={}
        if claimed_length is not None:
            self.headers["Content-Length"]=str(claimed_length)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        return False

    def iter_content(self,chunk_size):
        if self.stop_after is None:
            for pos in range(0,len(self.body),chunk_size):
                yield self.body[pos:pos+chunk_size]
        else:
            yield self.body[:self.stop_after]
            raise self.exc or ChunkedEncodingError("Connection broken")


@unittest.skipUnless(download_fresh is not None, "requires pandas and requests full V4 runtime")
class StreamRetryTests(unittest.TestCase):
    def setUp(self):
        # Deliberately incompressible to exceed the 1024-byte minimum.
        self.raw=os.urandom(12_000)
        self.valid=bz2.compress(self.raw)
        self.assertGreater(len(self.valid),1024)
        self.source={"url":"https://data.everef.net/dummy.csv.bz2",
                     "last_modified":"2026-10-17T01:15:00Z"}

    def test_broken_connection_first_try_recovers_from_clean_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"market_orders.csv.bz2"
            responses=[
                FakeResponse(self.valid,stop_after=1800,
                             exc=ChunkedEncodingError("IncompleteRead")),
                FakeResponse(self.valid,claimed_length=len(self.valid)),
            ]
            with patch("v4.sources._get",side_effect=responses) as getter, \
                 patch("v4.sources.time.sleep") as sleep:
                result=download_fresh(self.source,output)
            self.assertEqual(result["download_attempts"],2)
            self.assertEqual(result["download_retries"],1)
            self.assertTrue(result["bz2_crc_and_eof_verified"])
            self.assertEqual(output.read_bytes(),self.valid)
            self.assertFalse(output.with_suffix(".bz2.part").exists())
            self.assertEqual(getter.call_count,2)
            sleep.assert_called_once()

    def test_incomplete_read_retried(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"public_contracts.tar.bz2"
            responses=[
                FakeResponse(self.valid,stop_after=1300,
                             exc=http.client.IncompleteRead(b"partial",500)),
                FakeResponse(self.valid,claimed_length=len(self.valid)),
            ]
            with patch("v4.sources._get",side_effect=responses), \
                 patch("v4.sources.time.sleep"):
                result=download_fresh(self.source,output)
            self.assertEqual(result["download_attempts"],2)
            self.assertEqual(output.read_bytes(),self.valid)

    def test_silent_http_content_length_truncation_retried(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"market_orders.csv.bz2"
            responses=[
                FakeResponse(self.valid[:2000],claimed_length=len(self.valid)),
                FakeResponse(self.valid,claimed_length=len(self.valid)),
            ]
            with patch("v4.sources._get",side_effect=responses), \
                 patch("v4.sources.time.sleep"):
                report=download_fresh(self.source,output)
            self.assertEqual(report["download_retries"],1)
            self.assertEqual(bz2.decompress(output.read_bytes()),self.raw)

    def test_equal_http_length_but_invalid_bzip2_crc_retried(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"market_orders.csv.bz2"
            broken=self.valid[:-10]
            responses=[
                FakeResponse(broken,claimed_length=len(broken)),
                FakeResponse(self.valid,claimed_length=len(self.valid)),
            ]
            with patch("v4.sources._get",side_effect=responses), \
                 patch("v4.sources.time.sleep"):
                result=download_fresh(self.source,output)
            self.assertEqual(result["download_attempts"],2)
            self.assertEqual(output.read_bytes(),self.valid)

    def test_four_errors_never_replace_previous_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            output=Path(td)/"market_orders.csv.bz2"
            output.write_bytes(self.valid)
            responses=[FakeResponse(self.valid,stop_after=1600,
                                    exc=ChunkedEncodingError("IncompleteRead"))
                       for _ in range(4)]
            with patch("v4.sources._get",side_effect=responses) as getter, \
                 patch("v4.sources.time.sleep") as sleep:
                with self.assertRaisesRegex(SourceError,
                                            "SOURCE_STREAM_RETRY_EXHAUSTED"):
                    download_fresh(self.source,output)
            self.assertEqual(getter.call_count,4)
            self.assertEqual(sleep.call_count,3)
            self.assertEqual(output.read_bytes(),self.valid)
            self.assertFalse(output.with_suffix(".bz2.part").exists())

    def test_bad_attempt_count_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,"INVALID_DOWNLOAD_ATTEMPTS"):
                download_fresh(self.source,Path(td)/"bad",attempts=0)


if __name__=="__main__":
    unittest.main()
