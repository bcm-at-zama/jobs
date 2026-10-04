"""Primary-tabs rendering.

render_html_tabs() emits the 7 tab buttons (All / Liked / To Apply /
Pipeline / Top fit / Spontaneous / New) that drive the per-view presets
on the client side. The JS reads the data-tab attribute to look up its
preset in TAB_PRESETS, so the IDs must stay stable.

Run:  python3 -m unittest tests.test_tabs
"""
import unittest

import jobs


class TestRenderHtmlTabs(unittest.TestCase):

    EXPECTED_IDS = ["all", "liked", "toapply", "pipeline",
                    "topfit", "ranked", "spontaneous", "new"]

    def test_all_tab_ids_present(self):
        out = jobs.render_html_tabs()
        for tid in self.EXPECTED_IDS:
            with self.subTest(tab=tid):
                self.assertIn(f'data-tab="{tid}"', out,
                              f"tab button data-tab={tid!r} missing")

    def test_wrapped_in_tabs_nav(self):
        out = jobs.render_html_tabs()
        self.assertIn('<nav class="tabs"', out)
        self.assertIn('id="tabs"', out)

    def test_tab_order_matches_js_preset_order(self):
        # Order controls visual order of the tab bar — must match the
        # TAB_PRESETS keys in the JS so hover/focus feel consistent.
        out = jobs.render_html_tabs()
        positions = [(tid, out.find(f'data-tab="{tid}"')) for tid in self.EXPECTED_IDS]
        for tid, pos in positions:
            self.assertGreater(pos, -1, f"{tid} not rendered")
        sorted_by_pos = sorted(positions, key=lambda kv: kv[1])
        self.assertEqual([tid for tid, _ in sorted_by_pos], self.EXPECTED_IDS)


class TestFiltersStripped(unittest.TestCase):
    """The Show-X checkboxes and Show All / Unshow All buttons were
    removed when the primary tabs became the per-state view selector.
    Keep render_html_filters free of those IDs so a future refactor
    doesn't accidentally re-add them."""

    REMOVED_IDS = [
        "show-liked-toggle", "show-toapply-toggle", "show-applied-toggle",
        "show-app-rejected-toggle", "show-others-toggle",
        "show-all-states", "unshow-all-states",
    ]

    def test_show_toggles_removed(self):
        out = jobs.render_html_filters([])
        for tid in self.REMOVED_IDS:
            with self.subTest(id=tid):
                self.assertNotIn(tid, out,
                                 f"{tid!r} should have been removed from the filters section")

    def test_core_filters_still_present(self):
        # These are kept — they're the ALL-tab-only filtering tools.
        out = jobs.render_html_filters([])
        for keep in ("loc-filter", "title-filter", "text-filter",
                     "highlight-toggle", "hide-empty-toggle", "hide-spontaneous-toggle"):
            with self.subTest(id=keep):
                self.assertIn(keep, out)


if __name__ == "__main__":
    unittest.main()
