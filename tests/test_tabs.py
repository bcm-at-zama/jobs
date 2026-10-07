"""Primary-tabs rendering.

render_html_tabs() emits the 8 tab buttons (All / New / Untouched /
Ranked / Spontaneous / Liked / To Apply / Pipeline) that drive the
per-view presets on the client side. The JS reads the data-tab
attribute to look up its preset in TAB_PRESETS, so the IDs must stay
stable.

Run:  python3 -m unittest tests.test_tabs
"""
import unittest

import jobs


class TestRenderHtmlTabs(unittest.TestCase):

    EXPECTED_IDS = ["all", "new", "untouched", "ranked", "spontaneous",
                    "liked", "toapply", "pipeline"]

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


class TestTabShortcutDiscoverability(unittest.TestCase):
    """Each tab title must surface its positional digit shortcut
    (1..8), and each action button must mention its ⌘ shortcut — so a
    user discovers them by hovering."""

    def test_each_tab_tooltip_includes_digit(self):
        out = jobs.render_html_tabs()
        for i, (tid, label) in enumerate(jobs.TABS):
            with self.subTest(tab=tid):
                self.assertIn(
                    f'data-tab="{tid}" title="{label} ({i + 1})"', out,
                    f"tab {tid!r} should carry a positional-digit tooltip",
                )

    def test_action_buttons_mention_cmd_shortcut(self):
        out = jobs.render_html_tabs()
        # Shortcut suffix must survive in each action button tooltip —
        # must match the keydown map (R/I/E/,).
        for suffix in ("(⌘R)", "(⌘I)", "(⌘E)", "(⌘,)"):
            with self.subTest(shortcut=suffix):
                self.assertIn(suffix, out)


class TestQueryRequiredIndicator(unittest.TestCase):
    """Query-required sources (Apple/Microsoft/Meta/Phenom) iterate
    `for q in queries` with no empty-string fallback — so queries=[]
    fetches literally zero jobs, silently. The red "⚠ keyword required"
    chip is driven by a `data-query-required="1"` attribute on the
    `.queries` wrapper + a CSS `::before` keyed off `:not(:has(.query-pill))`.
    Tests pin the server-side half; CSS presence is checked by grepping
    the full HTML the renderer emits."""

    def test_apple_gets_required_attr(self):
        out = jobs.render_html_section(
            name="Apple", visible=[], rejected_count=0,
            board_url="https://jobs.apple.com", spontaneous_url=None,
            liked=set(), queries=[], kind="apple",
        )
        self.assertIn('data-query-required="1"', out)

    def test_microsoft_meta_phenom_get_required_attr(self):
        for kind in ("microsoft", "meta", "phenom"):
            out = jobs.render_html_section(
                name=kind.title(), visible=[], rejected_count=0,
                board_url="https://example.com", spontaneous_url=None,
                liked=set(), queries=[], kind=kind,
            )
            with self.subTest(kind=kind):
                self.assertIn('data-query-required="1"', out)

    def test_greenhouse_does_not_get_required_attr(self):
        """Fetch-everything-and-filter sources work fine with empty queries."""
        for kind in ("greenhouse", "ashby", "workable", "workday"):
            out = jobs.render_html_section(
                name=kind.title(), visible=[], rejected_count=0,
                board_url="https://example.com", spontaneous_url=None,
                liked=set(), queries=[], kind=kind,
            )
            with self.subTest(kind=kind):
                self.assertNotIn("data-query-required", out)

    def test_attr_stays_on_non_empty_queries_too(self):
        """The chip is CSS-driven (:not(:has(.query-pill))), so the attr
        stays regardless of pill count — removing the last pill in the
        browser re-shows the warning without a page reload."""
        out = jobs.render_html_section(
            name="Apple", visible=[], rejected_count=0,
            board_url="https://jobs.apple.com", spontaneous_url=None,
            liked=set(), queries=["security"], kind="apple",
        )
        self.assertIn('data-query-required="1"', out)

    def test_warning_css_present(self):
        """The CSS block that renders the chip must survive — it's the
        other half of the feature."""
        # jobs.py embeds the stylesheet inline in the big HTML template;
        # it ships as a module-level string accessible via render helpers.
        # Easier to just grep the file source once.
        with open(jobs.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertIn(
            '.queries[data-query-required="1"]:not(:has(.query-pill))::before',
            src,
            "runaway-warning CSS rule removed — chip won't render",
        )


class TestUntouchedTab(unittest.TestCase):
    """Untouched = jobs with none of liked/toapply/applied/app-rejected.
    Sits between New and Ranked. Must be wired through the three parallel
    structures: TABS (Python), TAB_PRESETS + CSS + counter (JS). We only
    inspect the rendered HTML blob here — the JS side has no node runtime
    in our test env — but the per-tab CSS and the TAB_PRESETS/selectors/
    counter strings all live in jobs.py's HTML template, so grepping the
    full output catches regressions in any of them."""

    def test_untouched_tab_sits_after_new(self):
        out = jobs.render_html_tabs()
        pos_new = out.find('data-tab="new"')
        pos_unt = out.find('data-tab="untouched"')
        pos_ranked = out.find('data-tab="ranked"')
        self.assertGreater(pos_new, -1)
        self.assertGreater(pos_unt, pos_new,
                           "Untouched must come after New")
        self.assertGreater(pos_ranked, pos_unt,
                           "Ranked must come after Untouched")


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
        # highlight-toggle used to be in the filters section but was
        # moved to the always-visible top bar so it works across tabs.
        out = jobs.render_html_filters([])
        for keep in ("loc-filter", "title-filter", "text-filter",
                     "hide-empty-toggle", "hide-spontaneous-toggle"):
            with self.subTest(id=keep):
                self.assertIn(keep, out)
        # Highlight toggle moved out of the filters section
        self.assertNotIn("highlight-toggle", out,
                         "Highlight toggle should live in the top bar, not in filters.")


if __name__ == "__main__":
    unittest.main()
