"""Keyboard-shortcut contract — ⌘I rates all visible jobs, ⌘U rates only
the ones that don't yet carry a .badge.claude-fit.

The wiring lives in jobs.py's inline JS, and the user-visible listing
lives in settings.html. Both are the kind of thing a drive-by refactor
can silently break (JS gets reshuffled, settings section gets renamed),
so this suite greps the raw sources to pin:

  - the ⌘U branch in the keydown handler;
  - the _collectUnscoredJobUrls helper and its .badge.claude-fit filter;
  - the AI-button tooltip mentions both ⌘I and ⌘U;
  - the /settings page has a Keyboard-shortcuts section listing both
    shortcuts plus the rest of the Cmd+<letter> bindings.

Run:  python3 -m unittest tests.test_shortcuts
"""
import unittest

import jobs


class TestJobsPageCmdUWiring(unittest.TestCase):
    """The main board's inline JS must wire ⌘U to Claude scoring with
    the unscored-only filter."""

    @classmethod
    def setUpClass(cls):
        with open(jobs.__file__, encoding="utf-8") as f:
            cls.src = f.read()

    def test_unscored_collector_defined(self):
        self.assertIn("function _collectUnscoredJobUrls()", self.src)

    def test_unscored_collector_filters_on_claude_fit_badge(self):
        """The 'unscored' definition is 'has no .badge.claude-fit' — if
        this selector drifts, ⌘U would re-score everything."""
        self.assertIn(".badge.claude-fit", self.src)
        self.assertIn("_collectUnscoredJobUrls", self.src)

    def test_cmd_u_branch_present(self):
        """The keydown handler must call _runClaudeScoring with the
        unscored collector when ⌘U fires."""
        self.assertIn("_runClaudeScoring(_collectUnscoredJobUrls()", self.src)

    def test_ai_button_tooltip_mentions_both_shortcuts(self):
        """The AI button's title= must advertise ⌘I AND ⌘U so a user
        who hovers the button learns the pair."""
        # One title string carries both — if a refactor splits the
        # tooltip across lines or drops ⌘U, this guard catches it.
        self.assertRegex(self.src, r"⌘I[^\"']*⌘U")

    def test_shortcut_comment_block_lists_cmd_u(self):
        """The in-source doc comment above the keydown handler must
        list ⌘U so future readers of the code match what settings
        says."""
        self.assertIn("Cmd+U", self.src)


class TestSettingsPageListsShortcuts(unittest.TestCase):
    """The /settings page is the user-facing surface for the whole
    shortcut list. Keep it in sync with jobs.py's bindings."""

    @classmethod
    def setUpClass(cls):
        cls.text = jobs._render_settings_html().decode("utf-8")

    def test_section_heading_present(self):
        self.assertIn(">Keyboard shortcuts<", self.text)

    def test_lists_cmd_i_and_cmd_u(self):
        self.assertIn("<kbd>I</kbd>", self.text)
        self.assertIn("<kbd>U</kbd>", self.text)

    def test_lists_cmd_r_e_z_comma(self):
        """The other Cmd+<letter> bindings also live here — a drive-by
        rename of the section must not silently drop them."""
        for key in ("R", "E", "Z", ","):
            self.assertIn(f"<kbd>{key}</kbd>", self.text,
                          f"settings page no longer lists ⌘{key}")

    def test_lists_tab_digit_shortcuts(self):
        """1..9 tab-switch shortcuts are also user-facing — the listing
        covers them."""
        self.assertIn("<kbd>1</kbd>", self.text)
        self.assertIn("<kbd>9</kbd>", self.text)


if __name__ == "__main__":
    unittest.main()
