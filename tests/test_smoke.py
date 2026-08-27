"""Sanity: the package imports and stays stdlib-only. Runs on every commit."""

import sys
import unittest


class SmokeTest(unittest.TestCase):
    def test_package_imports(self):
        import greenwash  # noqa: F401
        from greenwash import cli, classify, config, flake, output, replay, reports, revisions, verdict  # noqa: F401

    def test_min_python(self):
        # DR-6: tomllib requires 3.11.
        self.assertGreaterEqual(sys.version_info[:2], (3, 11))

    def test_fail_open_wrapper(self):
        # NFR-4: main() must never raise; run() is not implemented yet, so main() should
        # swallow it and return 0.
        from greenwash.cli import main
        self.assertEqual(main([]), 0)


if __name__ == "__main__":
    unittest.main()
