import hashlib
import importlib.util
import runpy
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "omnireach_comment_results", ROOT / "scripts" / "omnireach_comment_results.py"
)
comment_results = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comment_results)
check_evidence = runpy.run_path(str(ROOT / "scripts" / "check-evidence"))


class CommentResultTests(unittest.TestCase):
    url = "https://www.xiaohongshu.com/explore/note123"

    def test_no_response_is_blocked_not_empty_success(self):
        result = comment_results.aggregate([], self.url, idle_stopped=True)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["complete"])
        self.assertEqual(result["stop_reason"], "no_comment_response")
        self.assertIsNone(result["has_more"])

    def test_request_failure_is_blocked(self):
        result = comment_results.aggregate([], self.url, failures=[{"type": "http_error", "status": 401}])
        self.assertEqual(result["status"], "access_blocked")

    def test_valid_empty_terminal_page_is_success(self):
        result = comment_results.aggregate([{"comments": [], "has_more": False}], self.url)
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["complete"])
        self.assertEqual(result["comment_count"], 0)

    def test_has_more_then_idle_is_partial(self):
        result = comment_results.aggregate([{"comments": [], "has_more": True, "cursor": "next"}], self.url,
                                           idle_stopped=True)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["stop_reason"], "no_new_page_after_has_more")

    def test_page_limit_is_partial(self):
        result = comment_results.aggregate([{"comments": [], "has_more": True, "cursor": "next"}], self.url,
                                           page_limit_reached=True)
        self.assertEqual(result["stop_reason"], "page_limit")
        self.assertFalse(result["complete"])

    def test_missing_schema_is_not_a_valid_empty_result(self):
        result = comment_results.aggregate([{"code": -100, "msg": "login"}], self.url)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["complete"])
        self.assertEqual(result["comment_count"], 0)
        self.assertTrue(result["errors"])


class EvidenceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "sources").mkdir()
        body = "The documented limit is 50 items per request."
        (self.root / "sources" / "S1.txt").write_text(body, encoding="utf-8")
        self.bundle = {
            "run_id": "run-1",
            "generated_at": "2026-11-06T00:00:00Z",
            "sources": [{"id": "S1", "url": "https://example.test", "retrieved_at": "2026-11-06T00:00:00Z",
                         "published_at": None, "source_type": "official", "read_scope": "paragraph 3",
                         "body_path": "S1.txt", "body_sha256": hashlib.sha256(body.encode()).hexdigest()}],
            "claims": [{"id": "C1", "text": "The limit is 50 items.", "status": "supported",
                        "evidence": [{"source_id": "S1", "quote": "limit is 50 items per request.",
                                      "locator": "paragraph 3"}]}],
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_bundle(self):
        self.assertEqual(check_evidence["validate"](self.bundle, self.root / "sources"), [])

    def test_missing_source_reference_fails(self):
        self.bundle["claims"][0]["evidence"][0]["source_id"] = "missing"
        self.assertTrue(any("unknown source" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))

    def test_quote_absent_from_body_fails(self):
        self.bundle["claims"][0]["evidence"][0]["quote"] = "The limit is 500 items."
        self.assertTrue(any("does not occur" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))

    def test_changed_source_body_fails_hash(self):
        (self.root / "sources" / "S1.txt").write_text("Changed source", encoding="utf-8")
        self.assertTrue(any("does not match" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))

    def test_unverified_claim_requires_reason(self):
        self.bundle["claims"][0] = {"id": "C1", "text": "Unknown", "status": "unverified", "evidence": []}
        self.assertTrue(any("notes must explain" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))

    def test_malformed_status_type_returns_validation_error(self):
        self.bundle["claims"][0]["status"] = []
        self.assertTrue(any("status must be one of" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))

    def test_malformed_source_id_type_returns_validation_error(self):
        self.bundle["claims"][0]["evidence"][0]["source_id"] = []
        self.assertTrue(any("unknown source" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))

    def test_signed_source_url_is_rejected(self):
        self.bundle["sources"][0]["url"] = "https://example.test/?xsec_token=private"
        self.assertTrue(any("signed query parameters" in error for error in check_evidence["validate"](
            self.bundle, self.root / "sources")))


if __name__ == "__main__":
    unittest.main()
