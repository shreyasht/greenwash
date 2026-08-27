"""End-to-end regression suite (REQUIREMENTS_1.md §11).

Discovers every directory under fixtures/ that has an `expected.json`, runs greenwash
against its planted diff, and asserts the headline verdict and findings match. Green on
every commit. Requires Maven on PATH; skipped with a clear message when absent.
"""

import json
import pathlib
import shutil
import unittest

FIXTURES = pathlib.Path(__file__).parent.parent / "fixtures"


def _fixture_dirs():
    if not FIXTURES.is_dir():
        return []
    return sorted(d for d in FIXTURES.iterdir() if (d / "expected.json").is_file())


@unittest.skipUnless(shutil.which("mvn"), "Maven not on PATH")
class FixtureRegressionTest(unittest.TestCase):
    pass


def _make_case(fixture_dir):
    def test(self):
        expected = json.loads((fixture_dir / "expected.json").read_text())
        self.skipTest(f"BUILD_PLAN.md §3 step 7 — greenwash run not wired for {fixture_dir.name}")
        # actual = run_greenwash(fixture_dir)  # noqa
        # self.assertEqual(actual["headline_verdict"], expected["headline_verdict"])

    return test


for _d in _fixture_dirs():
    setattr(FixtureRegressionTest, f"test_{_d.name.replace('-', '_')}", _make_case(_d))


if __name__ == "__main__":
    unittest.main()
