"""YC discovery module — ATS-detection regex regression guards.

These tests don't hit the network. They freeze the detection logic
against the shapes we care about:

  - the Ashby regex rejects protocol-relative URLs that don't end in
    .ashbyhq.com (previous bug: `//ajax.googleapis.com/...` matched as
    `ashby:ajax`, producing 22 false positives).
  - greenhouse / lever / ashby / workable slugs are captured correctly
    from realistic careers-page snippets.
  - Workday's two-group capture joins into a `tenant.pod|site` composite
    that catalog_slug_for() reduces back to a bare tenant.
  - DEFAULT_YC_FILTERS is a non-empty list (catches an accidental wipe).

Run:  python3 -m unittest tests.test_yc_discovery
"""
import unittest

import yc_discovery


class TestAshbyFalsePositiveRegression(unittest.TestCase):
    """Previous probe revision captured `//ajax.googleapis.com/...` as
    ashby:ajax. The fix: both Ashby regexes require ".ashbyhq.com" as
    a mandatory anchor. These snippets exercise both."""

    def test_ajax_cdn_not_detected_as_ashby(self):
        html = '<script src="//ajax.googleapis.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>'
        hits = yc_discovery._detect_from_html(html)
        for kind, _ in hits:
            self.assertNotEqual(kind, "ashby", f"false positive: {hits}")

    def test_real_ashby_subdomain_detected(self):
        html = '<a href="https://deepgram.ashbyhq.com/careers">Jobs</a>'
        hits = yc_discovery._detect_from_html(html)
        self.assertIn(("ashby", "deepgram"), hits)

    def test_real_ashby_path_detected(self):
        html = '<a href="https://jobs.ashbyhq.com/taktile">Jobs</a>'
        hits = yc_discovery._detect_from_html(html)
        self.assertIn(("ashby", "taktile"), hits)


class TestATSPatterns(unittest.TestCase):

    def test_greenhouse(self):
        html = '<iframe src="https://boards.greenhouse.io/akidolabs"></iframe>'
        hits = yc_discovery._detect_from_html(html)
        self.assertIn(("greenhouse", "akidolabs"), hits)

    def test_greenhouse_job_boards_variant(self):
        html = '<a href="https://job-boards.greenhouse.io/podium81">Careers</a>'
        hits = yc_discovery._detect_from_html(html)
        self.assertIn(("greenhouse", "podium81"), hits)

    def test_lever(self):
        html = '<a href="https://jobs.lever.co/mashgin">Open roles</a>'
        hits = yc_discovery._detect_from_html(html)
        self.assertIn(("lever", "mashgin"), hits)

    def test_workable(self):
        html = '<a href="https://apply.workable.com/example-co/">Apply</a>'
        hits = yc_discovery._detect_from_html(html)
        self.assertIn(("workable", "example-co"), hits)

    def test_workday_captures_tenant_pod_and_site(self):
        html = 'window.workdayUrl = "https://sonos.wd1.myworkdayjobs.com/en-US/Sonos";'
        hits = yc_discovery._detect_from_html(html)
        # Expect kind=workday, slug="sonos.wd1|Sonos" (the "en-US" prefix
        # is routed over by the regex's non-capturing group).
        # tenant.pod is lowercased, `site` keeps its original case
        # (Workday sites are case-sensitive: "External" ≠ "external").
        self.assertEqual(hits, [("workday", "sonos.wd1|Sonos")])


class TestCatalogSlugFor(unittest.TestCase):

    def test_passthrough_for_simple_ats(self):
        for kind in ("greenhouse", "lever", "ashby", "workable"):
            self.assertEqual(
                yc_discovery.catalog_slug_for(kind, "deepgram"),
                "deepgram",
            )

    def test_workday_reduces_to_bare_tenant(self):
        self.assertEqual(
            yc_discovery.catalog_slug_for("workday", "sonos.wd1|Sonos"),
            "sonos",
        )


class TestBoardUrl(unittest.TestCase):

    def test_greenhouse(self):
        self.assertEqual(
            yc_discovery._board_url("greenhouse", "podium81"),
            "https://job-boards.greenhouse.io/podium81",
        )

    def test_workday_rebuilds_full_url(self):
        self.assertEqual(
            yc_discovery._board_url("workday", "sonos.wd1|Sonos"),
            "https://sonos.wd1.myworkdayjobs.com/Sonos",
        )


class TestDefaultFilters(unittest.TestCase):

    def test_filters_non_empty_and_shaped(self):
        self.assertIsInstance(yc_discovery.DEFAULT_YC_FILTERS, list)
        self.assertGreater(len(yc_discovery.DEFAULT_YC_FILTERS), 0)
        for f in yc_discovery.DEFAULT_YC_FILTERS:
            self.assertIn("=", f, f"filter missing param=value: {f!r}")


class TestApplyQualityFilter(unittest.TestCase):
    """OR filter: company passes if established (teamSize >= floor) OR
    in a recent batch. Both knobs are configurable; defaults keep YC's
    long tail of 1-3 person pre-seeds out of the catalog."""

    def test_passes_on_team_size(self):
        cs = [{"name": "Big", "teamSize": 50, "batch": "S20"}]
        out = yc_discovery.apply_quality_filter(cs, min_team_size=20,
                                                recent_batches=["F26"])
        self.assertEqual([c["name"] for c in out], ["Big"])

    def test_passes_on_recent_batch(self):
        cs = [{"name": "Tiny", "teamSize": 3, "batch": "F26"}]
        out = yc_discovery.apply_quality_filter(cs, min_team_size=20,
                                                recent_batches=["F26"])
        self.assertEqual([c["name"] for c in out], ["Tiny"])

    def test_filters_out_old_pre_seed(self):
        cs = [{"name": "OldSmall", "teamSize": 3, "batch": "W20"}]
        out = yc_discovery.apply_quality_filter(cs, min_team_size=20,
                                                recent_batches=["F26"])
        self.assertEqual(out, [])

    def test_missing_fields_treated_as_zero_and_empty(self):
        cs = [{"name": "Mystery"}]
        out = yc_discovery.apply_quality_filter(cs, min_team_size=20,
                                                recent_batches=["F26"])
        self.assertEqual(out, [])

    def test_disabled_by_passing_zero_and_empty_list(self):
        cs = [
            {"name": "Tiny", "teamSize": 1, "batch": "W15"},
            {"name": "Mid", "teamSize": 20, "batch": "W15"},
        ]
        out = yc_discovery.apply_quality_filter(cs, min_team_size=0,
                                                recent_batches=[])
        self.assertEqual([c["name"] for c in out], ["Tiny", "Mid"])


if __name__ == "__main__":
    unittest.main()
