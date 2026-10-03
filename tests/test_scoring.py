"""LLM scoring response parser: tolerant to junk, repetition loops,
single-object replies, and markdown fences.

Run:  python3 -m unittest tests.test_scoring
"""
import glob
import os
import unittest

import jobs


def _batch(n):
    """Mini batch with n fake jobs, URL = u<i>."""
    return [
        {"url": f"u{i}", "title": f"job {i}", "locations": [],
         "description": "", "blob": f"job {i}"}
        for i in range(n)
    ]


class TestParseScoreResponse(unittest.TestCase):
    """Note: _parse_score_response dumps the raw response to
    debug/debug-score-response-<N>.txt when it fails to parse (as a
    production debug aid). The tearDown here cleans those up so running
    the test suite doesn't litter the debug/ dir."""

    def tearDown(self):
        for path in glob.glob("debug/debug-score-response-*.txt"):
            try:
                os.remove(path)
            except OSError:
                pass

    def test_clean_json_array(self):
        text = '[{"i":1,"salary":"$150k-$200k"},{"i":2,"salary":""}]'
        out = jobs._parse_score_response(text, _batch(2))
        self.assertEqual(out, {
            "u0": {"salary": "$150k-$200k"},
            "u1": {"salary": ""},
        })

    def test_fenced_json(self):
        text = '```json\n[{"i":1,"salary":"€80k"}]\n```'
        out = jobs._parse_score_response(text, _batch(1))
        self.assertEqual(out, {"u0": {"salary": "€80k"}})

    def test_single_object_batch_of_one(self):
        """qwen-ish models sometimes emit `{...}` instead of `[{...}]`.
        For a size-1 batch, the single object is unambiguous."""
        text = '{"i":1,"salary":"£120k"}'
        out = jobs._parse_score_response(text, _batch(1))
        self.assertEqual(out, {"u0": {"salary": "£120k"}})

    def test_scores_wrapper_key(self):
        text = '{"scores":[{"i":1,"salary":"X"}]}'
        out = jobs._parse_score_response(text, _batch(1))
        self.assertIn("u0", out)

    def test_bare_garbage_returns_empty(self):
        text = "I'm sorry Dave, I'm afraid I can't do that."
        out = jobs._parse_score_response(text, _batch(2))
        self.assertEqual(out, {})

    def test_truncated_tail_recoverable(self):
        """Ollama repetition loop: payload is a stream of duplicated objects,
        tail truncated mid-string. The extractor's _extract_first_object
        fallback must salvage the first complete `{...}`."""
        text = '[{"i":1,"salary":"$100k"},{"i":1,"salary":"$100k"},{"i":1,"sal'
        out = jobs._parse_score_response(text, _batch(2))
        # At least u0 (idx 0) salvaged
        self.assertIn("u0", out)

    def test_salary_max_length(self):
        """100-char cap so a model that pastes the full compensation
        paragraph doesn't blow out the badge."""
        long_salary = "X" * 500
        text = f'[{{"i":1,"salary":"{long_salary}"}}]'
        out = jobs._parse_score_response(text, _batch(1))
        self.assertLessEqual(len(out["u0"]["salary"]), 100)


if __name__ == "__main__":
    unittest.main()
