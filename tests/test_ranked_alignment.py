"""Ranked-view alignment smoke tests.

li.job rows have 7 state buttons + a details marker before the title:
  Review (R) · Reject (×) · Like (+1) · ToApply (TA) · Applied (✓) ·
  AppRejected (R) · Keep (K) · <details> ▶ Title

Spontaneous (✉) rows only have 4 state buttons before their link:
  Like (+1) · ToApply (TA) · Applied (✓) · AppRejected (R) · ✉ Spontaneous

In Ranked view both row types are flattened into #ranked-list and sorted
by Claude fit DESC. For the titles to vertically line up we inject four
`visibility: hidden` placeholder spacers into every spontaneous row so
the flex layout gives the +1 button and the title column identical
horizontal offsets in both row types.

These tests pin the invariants that would silently misalign the UI if
removed. They are string-level checks on the generated HTML template —
the actual alignment is a flexbox property, not something unittest can
measure, but the structural pieces that make it work can be guarded.

Run:  python3 -m unittest tests.test_ranked_alignment
"""
import re
import unittest

import jobs


def _inline_script():
    m = re.search(r"<script>(.*?)</script>", jobs.HTML_TEMPLATE, re.DOTALL)
    assert m, "no <script> block found in HTML_TEMPLATE"
    return m.group(1)


class TestRankedAlignmentHooks(unittest.TestCase):

    def setUp(self):
        self.js = _inline_script()
        self.css = jobs.HTML_TEMPLATE  # also contains the <style> block

    def test_inject_spacers_defined(self):
        self.assertIn("function _injectRankedSpacers(row)", self.js,
                      "spacer-injection function missing — spont rows will misalign")

    def test_remove_spacers_defined(self):
        self.assertIn("function _removeRankedSpacers(row)", self.js,
                      "spacer-removal missing — spacers would leak when leaving Ranked")

    def test_build_calls_inject_for_spontaneous(self):
        # The guard must specifically target spontaneous rows — injecting
        # into li.job would duplicate real buttons.
        self.assertRegex(
            self.js,
            r"spontaneous-row.*?\)\s*_injectRankedSpacers",
            "spacers should only be injected for .spontaneous-row rows",
        )

    def test_restore_calls_remove(self):
        self.assertIn("_removeRankedSpacers(row)", self.js,
                      "_restoreRankedView must strip spacers so the row returns clean")

    def test_four_spacer_slots_front_and_tail(self):
        # 2 at the front (review + reject), 2 at the tail (keep + marker).
        # Any fewer and the +1 or title column slips.
        self.assertIn("row.prepend(frontReject)", self.js)
        self.assertIn("row.prepend(frontReview)", self.js)
        self.assertIn("anchor.before(tailKeep)", self.js)
        self.assertIn("anchor.before(tailMarker)", self.js)

    def test_spacer_css_hides_pixels_only(self):
        # visibility:hidden preserves the layout box — display:none would
        # collapse it and break alignment. Guard against the regression.
        self.assertRegex(
            self.css,
            r"\.ranked-spacer\s*\{[^}]*visibility:\s*hidden",
            "ranked-spacer must use visibility:hidden (NOT display:none) "
            "or the spont row collapses and misaligns again",
        )
        # pointer-events:none prevents accidental clicks on the invisible
        # Review / Reject / Keep buttons.
        self.assertRegex(
            self.css,
            r"\.ranked-spacer\s*\{[^}]*pointer-events:\s*none",
        )

    def test_old_margin_hack_removed(self):
        # Previous iteration shipped a `margin-left: 14rem` hack on the
        # spont company-prefix. That approach was fragile (hard-coded px)
        # and must not come back now that spacers do the job properly.
        self.assertNotIn("margin-left: 14rem", self.css)
        self.assertNotIn("margin-left: 5.5rem", self.css)


if __name__ == "__main__":
    unittest.main()
