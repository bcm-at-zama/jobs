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
        # into li.job would duplicate real buttons. Allow any amount of
        # code (opening brace, assignments, text swaps) between the
        # guard and the inject call so the test survives light refactors.
        self.assertRegex(
            self.js,
            r"spontaneous-row[\s\S]{0,400}_injectRankedSpacers",
            "spacers should only be injected for .spontaneous-row rows",
        )

    def test_restore_calls_remove(self):
        self.assertIn("_removeRankedSpacers(row)", self.js,
                      "_restoreRankedView must strip spacers so the row returns clean")

    def test_three_spacer_slots_front_and_tail(self):
        # 2 at the front (review + reject) + 1 at the tail (keep).
        # The ▶ marker column is handled by a CSS padding-left on the
        # prefix, NOT a 4th flex sibling — adding one would offset the
        # flex gap math and misalign the title column again.
        self.assertIn("row.prepend(frontReject)", self.js)
        self.assertIn("row.prepend(frontReview)", self.js)
        self.assertIn("anchor.before(tailKeep)", self.js)
        self.assertNotIn("tailMarker", self.js,
                         "marker spacer should be a CSS padding, not a flex sibling")

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

    def test_ranked_spont_gap_matches_li(self):
        # .spontaneous-row's base rule uses gap: 0.5rem but li uses 0.6rem.
        # Across the 7-item button chain that accumulates to a visible
        # ~8px horizontal misalignment, so Ranked must force gap: 0.6rem
        # on spont rows to match li.
        self.assertRegex(
            self.css,
            r"body\.tab-ranked\s+#ranked-list\s+\.spontaneous-row\s*\{[^}]*gap:\s*0\.6rem",
            "Ranked spont rows must use gap:0.6rem to match li",
        )

    def test_ranked_spont_align_matches_li(self):
        # li uses align-items: baseline; .spontaneous-row base uses
        # align-items: center. Mismatch causes the ▸ marker and prefix
        # to sit at a different vertical baseline from li.job titles.
        self.assertRegex(
            self.css,
            r"body\.tab-ranked\s+#ranked-list\s+\.spontaneous-row\s*\{[^}]*align-items:\s*baseline",
            "Ranked spont rows must use align-items:baseline to match li",
        )

    def test_unstyled_rows_get_padding_in_ranked(self):
        # Rows without a state class don't get the stateful padding +
        # border-left (0.4rem + 3px = ~8px) that liked/toapply/applied
        # rows get. In Ranked view that leaves unliked spont rows (and
        # unstyled li.job) ~8px LEFT of stateful rows. The compensating
        # rule must stay — otherwise the +1 column misaligns per row.
        self.assertRegex(
            self.css,
            r"body\.tab-ranked[^{]*:not\(\.liked\):not\(\.toapply\):not\(\.applied\):not\(\.app-rejected\)[^{]*\{[^}]*border-left:\s*3px\s+solid\s+transparent",
            "unstyled rows in Ranked must get a transparent 3px border-left + "
            "stateful padding so every +1 column lines up regardless of state",
        )

    def test_marker_pseudo_element_present(self):
        # The ▶ details marker that li.job gets natively is simulated on
        # spontaneous rows via a ::before pseudo-element with a ▸
        # character. Both the visual (triangle in every row) and the
        # alignment (real character width) depend on this rule.
        self.assertRegex(
            self.css,
            r"\.spontaneous-row\s+\.company-prefix::before\s*\{[^}]*content:\s*'\u25B6'",
            "spont prefix needs a ::before { content: '\u25B6' } marker in Ranked view",
        )


if __name__ == "__main__":
    unittest.main()
