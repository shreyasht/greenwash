"""Static strictness analysis (§4.1). Pure."""

import unittest

from greenwash.strictness import analyse, weakening_signals


def diff(removed=(), added=()):
    return "\n".join(f"-{r}" for r in removed) + "\n" + "\n".join(f"+{a}" for a in added)


class JvmTestSignalsTest(unittest.TestCase):
    P = "src/test/java/x/CalcTest.java"

    def test_disabled_added(self):
        s = weakening_signals(self.P, "test", diff(added=["    @Disabled"]))
        self.assertTrue(any("disabled" in r for r in s))

    def test_assertion_removed(self):
        s = weakening_signals(self.P, "test", diff(removed=["        assertEquals(5, x);"]))
        self.assertTrue(any("assertion line" in r for r in s))

    def test_test_method_removed(self):
        s = weakening_signals(self.P, "test", diff(
            removed=["    @Test", "    void t() {", "        assertTrue(x);", "    }"]))
        self.assertTrue(any("@Test method was removed" in r for r in s))

    def test_expected_value_changed(self):
        s = weakening_signals(self.P, "test", diff(
            removed=["        assertEquals(5, calc.add(2, 3));"],
            added=["        assertEquals(2, calc.add(2, 3));"]))
        self.assertTrue(any("expected value changed" in r for r in s))

    def test_pure_addition_is_not_weakening(self):
        s = weakening_signals(self.P, "test", diff(added=[
            "    @Test", "    void extra() {", "        assertEquals(1, 1);", "    }"]))
        self.assertEqual(s, [])


class ConfigSignalsTest(unittest.TestCase):
    P = "pom.xml"

    def test_threshold_decreased(self):
        s = weakening_signals(self.P, "config", diff(
            removed=["              <minimum>0.80</minimum>"],
            added=["              <minimum>0.00</minimum>"]))
        self.assertIn("a numeric threshold decreased", s)

    def test_rule_block_removed(self):
        s = weakening_signals(self.P, "config", diff(removed=["    <rule>", "    </rule>"]))
        self.assertTrue(any("block was removed" in r for r in s))

    def test_ci_continue_on_error_added(self):
        s = weakening_signals(".github/workflows/ci.yml", "config",
                              diff(added=["    continue-on-error: true"]))
        self.assertTrue(any("continue-on-error" in r for r in s))

    def test_threshold_increased_is_not_weakening(self):
        s = weakening_signals(self.P, "config", diff(
            removed=["  <minimum>0.50</minimum>"], added=["  <minimum>0.90</minimum>"]))
        self.assertEqual(s, [])


class AnalyseTest(unittest.TestCase):
    def test_unrecognised_format_is_reported_separately(self):
        self.assertEqual(weakening_signals("cases.json", "test", diff(added=['{"x": 1}'])), [])
        out = analyse([("cases.json", "test", diff(added=['{"x": 1}']))])
        self.assertEqual(out["unrecognised"], ["cases.json"])
        self.assertEqual(out["weakened_paths"], [])

    def test_analyse_collects_weakened_paths(self):
        out = analyse([
            ("a/CalcTest.java", "test", diff(added=["@Disabled"])),
            ("b/OtherTest.java", "test", diff(added=["    @Test", "    void ok() {}"])),
        ])
        self.assertEqual(out["weakened_paths"], ["a/CalcTest.java"])
        self.assertEqual(out["unrecognised"], [])


if __name__ == "__main__":
    unittest.main()
