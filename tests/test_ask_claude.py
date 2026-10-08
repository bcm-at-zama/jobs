"""Per-job `?` button: opens claude.ai with a prefilled fit-score prompt.

Historical bug: the handler only sent the URL and told Claude to "fetch
the description from the site". For WTJ sources (JS-rendered + auth-
walled), Claude's browser got an empty page and silently fell back to
generic searches (e.g. a greenhouse board of the same company name),
scoring the WRONG role. The fix is to inline the data we already have
locally — title, company, locations, salary, description — so Claude
never needs to fetch.

Covers:
  - render_html_section emits the DOM hooks the handler reads
    (li.job[data-locations], .desc-body, .badge.salary when a salary
    exists, button.ask-claude[data-title/data-company/data-url]).
  - the ? handler JS source reads from .desc-body and tells Claude
    "no need to fetch" — the old "fetch the description" instruction
    is gone.

Run:  python3 -m unittest tests.test_ask_claude
"""
import unittest

import jobs


class TestAskClaudeDomHooks(unittest.TestCase):
    """The rendered section must expose everything the handler reads."""

    def _render_one(self, salary=""):
        return jobs.render_html_section(
            name="Teamway",
            visible=[{
                "url": "https://www.welcometothejungle.com/fr/companies/teamway/jobs/eng",
                "title": "Senior Backend Engineer",
                "locations": ["Paris"],
                "description": "Build the backend. Python + Postgres. 5+ years.",
                "salary": salary,
                "is_new": False,
            }],
            rejected_count=0,
            board_url="https://www.welcometothejungle.com/fr/companies/teamway",
            spontaneous_url=None,
            liked=set(),
            queries=[],
            kind="wttj_company",
        )

    def test_button_carries_title_and_company(self):
        out = self._render_one()
        self.assertIn('class="ask-claude"', out)
        self.assertIn('data-title="Senior Backend Engineer"', out)
        self.assertIn('data-company="Teamway"', out)

    def test_li_carries_locations(self):
        out = self._render_one()
        self.assertIn('data-locations="Paris"', out)

    def test_desc_body_rendered(self):
        out = self._render_one()
        self.assertIn('class="desc-body"', out)
        self.assertIn("Build the backend", out)

    def test_salary_badge_rendered_when_present(self):
        out = self._render_one(salary="€60k-€80k")
        self.assertIn('class="badge salary"', out)
        self.assertIn("€60k-€80k", out)


class TestAskClaudeHandlerSource(unittest.TestCase):
    """The handler JS lives inline in jobs.py — grep the source so a
    regression that puts us back on the fetch-from-site path doesn't
    sneak in silently."""

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            self.src = f.read()

    def test_reads_description_from_local_dom(self):
        self.assertIn(".desc-body", self.src)
        # The handler must specifically read description text from the
        # local <li>, not from an API or a round-trip.
        self.assertIn("descEl", self.src)

    def test_reads_locations_and_salary(self):
        self.assertIn("dataset.locations", self.src)
        self.assertIn(".badge.salary", self.src)

    def test_prompt_tells_claude_not_to_fetch(self):
        # Both language variants must land on the "no fetch needed" path.
        self.assertIn("pas besoin de fetch", self.src)
        self.assertIn("no need to fetch", self.src)

    def test_old_fetch_instruction_removed(self):
        """Regression: the previous prompt said "Va chercher la
        description sur le site" / "Fetch the description from the
        site" — leaving that in would re-introduce the WTJ-empty-page
        bug."""
        self.assertNotIn("Va chercher la description sur le site", self.src)
        self.assertNotIn("Fetch the description from the site", self.src)


class TestBatchedScoringPromptSource(unittest.TestCase):
    """⌘I ("score every visible job") and ⌘U ("score only unscored")
    both go through _buildClaudeScoringPrompt.

    Split-prompt contract:
      • Public URLs (http/https) → URL-only. Claude fetches the page.
        This keeps the prompt small for 100+-job batches instead of
        inlining every description.
      • `private://` URLs → full inline block (title/company/locations/
        salary/description). Those URLs aren't fetchable — they are
        synthetic keys for jobs received via back-channels.

    The per-job `?` button stays all-inline (it's a single job, size
    is not a concern there, and it never had the WTJ fetch risk).
    """

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            self.src = f.read()
        self.scoring_fn = (
            self.src.split("function _buildClaudeScoringPrompt")[1]
            .split("\n}")[0]
        )

    def test_scoring_prompt_branches_on_private_scheme(self):
        """The function must distinguish private:// from public URLs —
        otherwise either every job gets inlined (prompt explodes) or no
        job does (private jobs score blind)."""
        self.assertIn("private://", self.scoring_fn)
        # Resolver + formatter still called for the private branch.
        self.assertIn("_resolveJobContext", self.scoring_fn)
        self.assertIn("_formatJobBlock", self.scoring_fn)

    def test_scoring_prompt_mentions_both_modes(self):
        """Instructions must cover BOTH the fetch (public) and the
        inline (private) path so Claude knows which to use per job."""
        # French
        self.assertIn("va chercher", self.scoring_fn.lower())
        self.assertIn("private://", self.scoring_fn)
        # English
        self.assertIn("go fetch", self.scoring_fn.lower())


class TestUrlsPromptSource(unittest.TestCase):
    """⇧-click on the per-state Open buttons goes through
    buildClaudePromptForUrls (both single + batch). Same URL-only bug
    before, same inline-context fix now."""

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            self.src = f.read()

    def test_urls_prompt_uses_resolver(self):
        self.assertIn("function buildClaudePromptForUrls", self.src)
        fn = self.src.split("function buildClaudePromptForUrls")[1].split("\n}")[0]
        self.assertIn("_resolveJobContext", fn)
        self.assertIn("_formatJobBlock", fn)


class TestJobContextResolver(unittest.TestCase):
    """The shared _resolveJobContext helper is what makes all three
    prompt builders (single `?`, batched ⌘I/⌘U, ⇧-click) immune to
    the empty-WTJ-page failure mode. It must read every field from
    the local DOM — the fields the rendered section exposes."""

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            self.src = f.read()

    def test_resolver_defined(self):
        self.assertIn("function _resolveJobContext", self.src)
        self.assertIn("function _formatJobBlock", self.src)

    def test_resolver_reads_expected_fields(self):
        fn = self.src.split("function _resolveJobContext")[1].split("\nfunction ")[0]
        for hook in (".desc-body", ".badge.salary",
                     "dataset.locations", "dataset.title", "dataset.company"):
            with self.subTest(hook=hook):
                self.assertIn(hook, fn)


class TestPasteBarErrorState(unittest.TestCase):
    """When _parseClaudeFits returns 0 scores, the paste bar must flip
    into a visible error state (red border + red status). Previously the
    "no scores parsed" status blended into the normal label color and
    the user missed it."""

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            self.src = f.read()

    def test_error_class_toggled_on_parse_failure(self):
        self.assertIn("bar.classList.add('error')", self.src)
        self.assertIn("bar.classList.remove('error')", self.src)

    def test_error_css_uses_danger_color(self):
        # The red must come from the shared --danger token so dark/light
        # themes stay in sync — not a hardcoded hex.
        self.assertIn("#claude-paste-bar.error", self.src)
        self.assertRegex(
            self.src,
            r"#claude-paste-bar\.error\s+#claude-paste-status\s*\{[^}]*var\(--danger\)",
        )


class TestClaudeFitBareFallback(unittest.TestCase):
    """Single-URL `?` button: Claude often drops the leading "1." index
    on single-job replies and sends "9/10 — reason" directly. The parser
    must accept that shape when urls.length === 1 — otherwise the paste
    bar reports "no scores parsed" and the user's score is dropped.

    Reproduced against a real Claude reply pasted by the user on
    2026-10-08 (Ledger Donjon Director role, 9/10)."""

    REAL_REPLY = (
        "9/10 — Correspondance quasi parfaite : diriger le Donjon "
        "(red team hardware wallets, side-channel/fautes, reverse, "
        "crypto embarquée) prolonge directement ton parcours.\n"
        "SAL 1: 200k€ + 30% variable (~260k€ OTE) + equity"
    )

    def setUp(self):
        with open(jobs.__file__, encoding="utf-8") as f:
            self.src = f.read()

    def test_bare_regex_defined(self):
        self.assertIn("_CLAUDE_FIT_BARE_RE", self.src)

    def test_fallback_scoped_to_single_url(self):
        """The fallback must only engage when urls.length === 1 — a
        stray "7/10" inside a reason for job 3 shouldn't be mis-assigned
        in a batch paste."""
        self.assertRegex(
            self.src,
            r"Object\.keys\(out\)\.length === 0 && urls\.length === 1",
        )

    def test_bare_regex_matches_real_reply(self):
        """Mirror the JS regex in Python and run it against the actual
        reply the user pasted. If this breaks, the paste bar breaks."""
        import re
        bare = re.compile(
            r"^[*\s>-]*(\d+)\s*/\s*10\s*[\u2014\-\u2013:]+\s*(.*)$",
            re.MULTILINE,
        )
        matches = list(bare.finditer(self.REAL_REPLY))
        self.assertTrue(matches, "bare regex should match '9/10 — ...'")
        self.assertEqual(matches[0].group(1), "9")
        self.assertTrue(matches[0].group(2).startswith("Correspondance"))


if __name__ == "__main__":
    unittest.main()
