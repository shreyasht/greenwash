"""Sanity: the package imports and stays stdlib-only. Runs on every commit."""

import contextlib
import io
import sys
import unittest


class SmokeTest(unittest.TestCase):
    def test_package_imports(self):
        import astroturf  # noqa: F401
        from astroturf import (  # noqa: F401
            classify, cli, config, flake, orchestrate, output, replay, reports, revisions, verdict,
        )

    def test_min_python(self):
        # DR-6: tomllib requires 3.11.
        self.assertGreaterEqual(sys.version_info[:2], (3, 11))

    def test_fail_open_wrapper_never_raises(self):
        # NFR-4: main() must never raise. Run against this repo's own working tree; with
        # nothing testable changed it returns 0 (NO_TEST_CHANGES).
        from astroturf.cli import main
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 0)


if __name__ == "__main__":
    unittest.main()
