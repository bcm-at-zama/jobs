"""Per-section × — bulk-reject every untouched job in a company section.

The button sits in the section <h1> next to the counter. Clicking it
confirms, then POSTs /reject for each untouched row (reusing the
per-row endpoint so each one lands on the Cmd+Z undo stack).

Run:  python3 -m unittest tests.test_reject_section
"""
import unittest

import jobs


class TestRejectSectionButtonRendered(unittest.TestCase):

    def _render(self, name="Apple", **kw):
        defaults = dict(
            visible=[], rejected_count=0,
            board_url="https://example.com", spontaneous_url=None,
            liked=set(), queries=[], kind="greenhouse",
        )
        defaults.update(kw)
        return jobs.render_html_section(name=name, **defaults)

    def test_button_present_in_header(self):
        out = self._render(name="Anthropic")
        self.assertIn('class="reject-section"', out)
        self.assertIn('data-sid="anthropic"', out)
        self.assertIn('data-name="Anthropic"', out)

    def test_button_sits_inside_h1(self):
        """Position matters — the client-side CSS that hides the button
        when the section is empty keys off the .company-section ancestor,
        but the button itself must render in the <h1> next to the counter
        so it's visually associated with the company header."""
        out = self._render(name="Anthropic")
        h1_start = out.find("<h1 ")
        h1_end = out.find("</h1>", h1_start)
        self.assertGreater(h1_start, -1)
        btn_pos = out.find('class="reject-section"', h1_start)
        self.assertGreater(btn_pos, -1)
        self.assertLess(btn_pos, h1_end)

    def test_display_name_in_data_name(self):
        """Spontaneous-only companies render with a display override, and
        the confirm() dialog shows data-name — so it must track display."""
        out = self._render(name="OpenAI", display_name="OpenAI (ATS)")
        self.assertIn('data-name="OpenAI (ATS)"', out)

    def test_html_escapes_name(self):
        out = self._render(name="A&B", display_name='A&B "co"')
        # The quote-escaped form must appear; the raw " must not.
        self.assertIn('data-name="A&amp;B &quot;co&quot;"', out)


class TestRejectSectionAssets(unittest.TestCase):
    """The CSS rule + JS handler live in jobs.py's inline template; grep
    the file once to prove both halves survive refactors."""

    def test_css_rule_present(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertIn(".reject-section {", src,
                      "CSS block for .reject-section was removed")

    def test_js_handler_present(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertIn("document.querySelectorAll('.reject-section')", src,
                      "JS click handler for .reject-section was removed")

    def test_js_skips_touched_rows(self):
        """The handler must select only untouched rows — the whole safety
        story depends on this selector staying in sync with the per-row
        reject-visibility CSS."""
        with open(jobs.__file__, encoding="utf-8") as f:
            src = f.read()
        self.assertIn(
            "li.job:not(.liked):not(.toapply):not(.applied):not(.app-rejected)",
            src,
        )


if __name__ == "__main__":
    unittest.main()
