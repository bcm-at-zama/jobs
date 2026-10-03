"""Seniority detection: titles → canonical seniority labels, IC-level codes,
and the SENIORITY_XP / IC_LEVEL_XP → years-of-experience mapping used for
the "🎓 ~Ny" badge.

Run:  python3 -m unittest tests.test_seniority
"""
import unittest

import config
import jobs


class TestDetectSeniority(unittest.TestCase):
    """detect_seniority(title) → one of the SENIORITY labels, or None."""

    CASES = [
        # Management ladder — note: "Senior Director" is NOT a distinct
        # label; it collapses to "Director" because the SENIORITY list
        # doesn't include a Senior-Director entry (by design).
        ("VP of Engineering",                       "VP"),
        ("Vice President, Security",                "VP"),
        ("Senior Director, Software Engineering",   "Director"),
        ("Director of Product",                     "Director"),
        ("Senior Manager, Infrastructure",          "Senior Manager"),
        ("Manager, Platform Team",                  "Manager"),
        ("Head of Engineering",                     "Head"),
        ("Team Lead, Backend",                      "Lead"),

        # IC ladder
        ("Senior Staff Software Engineer",          "Senior Staff"),
        ("Staff Software Engineer",                 "Staff"),
        ("Principal Engineer",                      "Principal"),
        ("Senior Software Engineer",                "Senior"),
        ("Distinguished Engineer",                  "Distinguished"),

        # Sr. abbreviations (CrowdStrike regression)
        ("Sr Engineer",                             "Senior"),
        ("Sr. Director, Product",                   "Director"),

        # Fresher roles — no seniority match
        ("Software Engineer",                       None),
        ("Software Engineer II",                    None),
        ("Associate Engineer",                      "Associate"),
        ("Junior Developer",                        "Junior"),
        ("Intern, Platform",                        "Intern"),
    ]

    def test_all(self):
        for title, expected in self.CASES:
            with self.subTest(title=title):
                self.assertEqual(jobs.detect_seniority(title), expected)


class TestDetectICLevel(unittest.TestCase):
    """detect_ic_level(title) → L5/L6/E5/IC7/etc., or None."""

    CASES = [
        # Netflix / Google (L-levels in parentheses or standalone)
        ("Security Engineer (L5) - Cloud",      "L5"),
        ("Senior Software Engineer L6",         "L6"),
        ("Staff Software Engineer, L7",         "L7"),

        # Meta (E-levels)
        ("Software Engineer E5",                "E5"),
        ("Research Scientist (E6)",             "E6"),

        # LinkedIn (IC-levels)
        ("Principal Software Engineer, IC6",    "IC6"),
        ("Senior Software Engineer IC5",        "IC5"),

        # No code present
        ("Senior Engineer",                     None),
        ("Director, Engineering",               None),
    ]

    def test_all(self):
        for title, expected in self.CASES:
            with self.subTest(title=title):
                self.assertEqual(jobs.detect_ic_level(title), expected)


class TestSeniorityXP(unittest.TestCase):
    """SENIORITY_XP[company][label] → "~Ny (…)" string. The badge is built
    with (specific company) first, then (IC-level fallback), then
    (SENIORITY_XP_DEFAULT fallback). Check at least one entry per
    big-company table and the default-fallback invariants."""

    BIG_COMPANIES = ["Google", "Meta", "Microsoft", "Apple", "NVIDIA"]

    def test_big_company_tables_exist(self):
        for name in self.BIG_COMPANIES:
            with self.subTest(company=name):
                self.assertIn(name, config.SENIORITY_XP,
                              f"SENIORITY_XP missing entry for {name}")
                self.assertTrue(config.SENIORITY_XP[name],
                                f"SENIORITY_XP[{name}] is empty")

    def test_values_are_non_empty_strings(self):
        """Every XP string in SENIORITY_XP must be a non-empty str. Catches
        accidental None / int entries that would break badge rendering."""
        for company, table in config.SENIORITY_XP.items():
            for label, xp in table.items():
                with self.subTest(company=company, label=label):
                    self.assertIsInstance(xp, str, f"{company}.{label} not str")
                    self.assertTrue(xp.strip(), f"{company}.{label} empty")


class TestICLevelXP(unittest.TestCase):
    """IC_LEVEL_XP[company][code] → "~Ny (name)" string. Covers L/E/IC codes."""

    def test_netflix_l_levels(self):
        self.assertIn("Netflix", config.IC_LEVEL_XP)
        netflix = config.IC_LEVEL_XP["Netflix"]
        for code in ("L4", "L5", "L6", "L7"):
            with self.subTest(code=code):
                self.assertIn(code, netflix, f"Netflix {code} missing")

    def test_google_l_levels(self):
        self.assertIn("Google", config.IC_LEVEL_XP)
        for code in ("L5", "L6", "L7"):
            with self.subTest(code=code):
                self.assertIn(code, config.IC_LEVEL_XP["Google"])

    def test_meta_e_levels(self):
        self.assertIn("Meta", config.IC_LEVEL_XP)
        for code in ("E5", "E6", "E7"):
            with self.subTest(code=code):
                self.assertIn(code, config.IC_LEVEL_XP["Meta"])

    def test_linkedin_ic_levels(self):
        self.assertIn("LinkedIn", config.IC_LEVEL_XP)
        for code in ("IC5", "IC6"):
            with self.subTest(code=code):
                self.assertIn(code, config.IC_LEVEL_XP["LinkedIn"])


class TestSeniorityXPDefault(unittest.TestCase):
    """SENIORITY_XP_DEFAULT is the generic fallback used when neither a
    company-specific SENIORITY_XP entry nor an IC_LEVEL_XP entry matches."""

    def test_has_core_labels(self):
        for label in ("Senior", "Staff", "Principal"):
            with self.subTest(label=label):
                self.assertIn(label, config.SENIORITY_XP_DEFAULT)
                self.assertTrue(config.SENIORITY_XP_DEFAULT[label].strip())


if __name__ == "__main__":
    unittest.main()
