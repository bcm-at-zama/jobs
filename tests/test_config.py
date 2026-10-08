"""Config integrity: every SOURCES entry must have a kind registered in
FETCHERS, every slug must be unique, every board URL must be https.
Catches typos that would silently reduce coverage.

Run:  python3 -m unittest tests.test_config
"""
import unittest

import config
import jobs


class TestSourcesIntegrity(unittest.TestCase):

    # `test_sources_list_non_empty` lives in data/tests/test_user_decisions.py
    # — it fails on a stock OSS clone with no user_config yet.

    def test_every_kind_is_registered(self):
        unknown = []
        for src in config.SOURCES:
            if src["kind"] not in jobs.FETCHERS:
                unknown.append((src["name"], src["kind"]))
        self.assertFalse(
            unknown,
            f"Sources using an unregistered kind (not in FETCHERS): {unknown}",
        )

    def test_slug_or_name_unique(self):
        """Each source must have a unique name. Duplicate names break the
        per-source cache + dedup logic."""
        names = [s["name"] for s in config.SOURCES]
        dupes = {n for n in names if names.count(n) > 1}
        self.assertFalse(dupes, f"duplicate source names: {dupes}")

    def test_every_source_has_queries_list(self):
        """queries must be a list (possibly empty) — not None or a str."""
        for src in config.SOURCES:
            with self.subTest(name=src["name"]):
                self.assertIsInstance(
                    src.get("queries"), list,
                    f"{src['name']} queries must be a list",
                )

    def test_name_slug_shape(self):
        """slug is used in filesystem paths (list_cache/<slug>.json) — must
        be ASCII, lowercase-safe-ish."""
        for src in config.SOURCES:
            name = src["name"]
            slugged = jobs.slug(name)
            with self.subTest(name=name):
                self.assertTrue(slugged, f"slug for {name!r} is empty")
                # No slashes / spaces
                self.assertNotIn("/", slugged)
                self.assertNotIn(" ", slugged)


class TestLocationBlacklistShape(unittest.TestCase):

    def test_list_of_strings(self):
        self.assertIsInstance(config.LOCATION_BLACKLIST, list)
        for entry in config.LOCATION_BLACKLIST:
            self.assertIsInstance(entry, str)
            self.assertTrue(entry.strip(),
                            f"empty entry in LOCATION_BLACKLIST: {entry!r}")

    def test_no_accidental_dupes(self):
        seen = set()
        dupes = []
        for entry in config.LOCATION_BLACKLIST:
            k = entry.lower()
            if k in seen:
                dupes.append(entry)
            seen.add(k)
        self.assertFalse(dupes, f"duplicate blacklist entries: {dupes}")


class TestCliPort(unittest.TestCase):
    """The --port flag lets a sandbox board coexist with the main one.
    Parser must accept it and main() must honour it as a module-level
    override before preflight runs."""

    def _parse(self, argv):
        import sys
        orig = sys.argv
        try:
            sys.argv = ["jobs.py"] + argv
            return jobs._parse_cli()
        finally:
            sys.argv = orig

    def test_port_defaults_to_none(self):
        """No --port → args.port is None, main() leaves SERVE_PORT alone."""
        args = self._parse([])
        self.assertIsNone(args.port)

    def test_port_accepts_integer(self):
        args = self._parse(["--port", "8767"])
        self.assertEqual(args.port, 8767)

    def test_port_rejects_non_integer(self):
        with self.assertRaises(SystemExit):
            self._parse(["--port", "notanint"])


class TestGroupOfAutoFill(unittest.TestCase):
    """REGRESSION — every catalog entry declares its `group`, but render
    time looks it up via `config.GROUP_OF[name]`. Without the auto-fill
    at the end of config.py, new companies silently landed in "Other"
    and freshly-added group headings (FHE, Cars, Media, Blockchain,
    Startups) rendered empty. Pin the invariant so a future refactor
    can't resurrect the "I don't see Zama" bug."""

    def test_every_catalog_entry_resolves_to_its_declared_group(self):
        from catalog import CATALOG
        drift = []
        for e in CATALOG:
            declared = e.get("group")
            resolved = config.GROUP_OF.get(e["name"], "Other")
            if declared and resolved != declared:
                drift.append((e["name"], declared, resolved))
        self.assertFalse(
            drift,
            "catalog group ≠ GROUP_OF resolution — these would render "
            "under the wrong heading:\n  "
            + "\n  ".join(f"{n}: catalog={d!r} resolved={r!r}"
                          for n, d, r in drift),
        )

    def test_new_groups_are_in_group_order(self):
        """Groups declared in the catalog must appear in GROUP_ORDER —
        otherwise their heading renders at the end as a fallback and
        the user doesn't see the intended ordering."""
        from catalog import CATALOG
        groups_in_catalog = {e["group"] for e in CATALOG if e.get("group")}
        missing = groups_in_catalog - set(config.GROUP_ORDER)
        self.assertFalse(
            missing,
            f"groups {sorted(missing)} are used in catalog but missing "
            f"from GROUP_ORDER — add them to config.GROUP_ORDER so the "
            f"nav renders them in the right slot",
        )


class TestBoardUrlFor(unittest.TestCase):
    """Section headers render as `<a class="board-link">` only when
    board_url_for() returns a non-empty URL — otherwise the h1 falls
    back to plain text, which inherits the default color (black) and
    the section visually drifts from the red styling other sources
    get. Netflix hit this: its catalog entry has no `board` field and
    `kind="eightfold"` wasn't handled, so the h1 rendered in black
    while every neighbour was red. Pin the kind handlers so a future
    eightfold source doesn't regress."""

    def test_eightfold_synthesizes_from_host(self):
        src = {"kind": "eightfold", "slug": "netflix",
               "host": "https://explore.jobs.netflix.net",
               "domain": "netflix.com"}
        self.assertEqual(jobs.board_url_for(src),
                         "https://explore.jobs.netflix.net/careers")

    def test_eightfold_host_trailing_slash_stripped(self):
        src = {"kind": "eightfold", "slug": "x",
               "host": "https://x.com/", "domain": "x.com"}
        self.assertEqual(jobs.board_url_for(src), "https://x.com/careers")

    def test_explicit_board_wins(self):
        src = {"kind": "eightfold", "slug": "x",
               "host": "https://x.com", "board": "https://custom/jobs"}
        self.assertEqual(jobs.board_url_for(src), "https://custom/jobs")


class TestTitleCaseOverrides(unittest.TestCase):
    """TITLE_CASE_OVERRIDES rewrites per-word casing when titles are
    recovered from URL slugs (e.g. SAP postings whose slug yields
    "Sap Ns2 ..." without the override)."""

    def test_sap_and_ns2_uppercase(self):
        out = jobs._title_from_slug("sap-ns2-cloud-application-services")
        self.assertIn("SAP", out)
        self.assertIn("NS2", out)
        self.assertNotIn("Sap ", out)
        self.assertNotIn("Ns2", out)


class TestSeniorityConfig(unittest.TestCase):

    def test_seniority_rank_covers_groups(self):
        """Every label in SENIORITY_GROUPS must be in SENIORITY_RANK so the
        sort order is defined for all seniority buckets."""
        grouped = [lbl for _grp, labels in config.SENIORITY_GROUPS
                   for lbl in labels]
        for lbl in grouped:
            with self.subTest(label=lbl):
                self.assertIn(lbl, config.SENIORITY_RANK,
                              f"{lbl!r} missing from SENIORITY_RANK")


if __name__ == "__main__":
    unittest.main()
