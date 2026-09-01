"""Config load round-trip (FR-30, DR-6). Pure."""

import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from greenwash import config as config_mod


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="greenwash-config-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, body):
        Path(self.tmp, config_mod.CONFIG_FILENAME).write_text(textwrap.dedent(body))

    def test_missing_file_is_all_defaults(self):
        cfg = config_mod.load(self.tmp)
        self.assertEqual(cfg, config_mod.Config())

    def test_full_round_trip(self):
        self._write('''
            build_command = "./gradlew test --continue"
            report_globs = ["build/test-results/test/*.xml"]
            confirm_count = 3
            confirm_mode = "full"
            module_scope = false
            timeout_s = 600

            [classification_overrides]
            "scripts/*.py" = "neutral"
            "infra/**" = "config"

            [exit_overrides]
            TESTS_REMOVED_OR_SKIPPED = 1
        ''')
        cfg = config_mod.load(self.tmp)
        self.assertEqual(cfg.build_command, ["./gradlew", "test", "--continue"])
        self.assertEqual(cfg.report_globs, ["build/test-results/test/*.xml"])
        self.assertEqual(cfg.confirm_count, 3)
        self.assertEqual(cfg.confirm_mode, "full")
        self.assertFalse(cfg.module_scope)
        self.assertEqual(cfg.timeout_s, 600)
        self.assertEqual(cfg.classification_overrides["infra/**"], "config")
        self.assertEqual(cfg.exit_overrides["TESTS_REMOVED_OR_SKIPPED"], 1)

    def test_build_command_as_list(self):
        self._write('build_command = ["mvn", "-B", "verify"]\n')
        self.assertEqual(config_mod.load(self.tmp).build_command, ["mvn", "-B", "verify"])


if __name__ == "__main__":
    unittest.main()
