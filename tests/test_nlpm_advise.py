"""Tests for the /nlpm:advise layer: the evidence verifier and catalog consistency.

Run from the plugin root with:
    python3 -m unittest tests.test_nlpm_advise
"""
from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
loader = SourceFileLoader("nlpm_advise_verify", str(ROOT / "bin" / "nlpm-advise-verify"))
spec = importlib.util.spec_from_loader("nlpm_advise_verify", loader)
verifier = importlib.util.module_from_spec(spec)
loader.exec_module(verifier)

SKILL = ROOT / "skills" / "nlpm" / "product-advising" / "SKILL.md"
MIRROR = ROOT / "codex" / "skills" / "product-advising" / "SKILL.md"


def report(findings, rows=None):
    body = json.dumps({"schema": 1, "findings": findings}, ensure_ascii=False)
    rules = [f.get("rule", "") for f in findings if isinstance(f, dict)] if rows is None else rows
    table = "\n".join(f"| P1 | {rule} | e | i | r | a | unit |" for rule in rules)
    return (f"# title\n\n## 发现清单\n| 级别 | 规则 | 证据 | 影响 | 需求 | 验收标准 | 验证层 |\n|---|---|---|---|---|---|---|\n"
            f"{table}\n\n## 机器可读\n```nlpm-findings\n{body}\n```\n")


class LoadFindings(unittest.TestCase):
    def test_reads_the_block(self):
        self.assertEqual(verifier.load_findings(report([{"id": "F1"}])), [{"id": "F1"}])

    def test_missing_block_is_an_error(self):
        with self.assertRaises(ValueError):
            verifier.load_findings("# no block here")

    def test_wrong_schema_is_an_error(self):
        with self.assertRaises(ValueError):
            verifier.load_findings('```nlpm-findings\n{"schema": 99, "findings": []}\n```')

    def test_wrong_field_types_are_errors_not_crashes(self):
        bad_findings = [
            [None],
            ["text"],
            [{"id": "F1", "evidence": "src/a.ts:1"}],
            [{"id": "F1", "evidence": ["src/a.ts:1"]}],
            [{"id": "F1", "evidence": [{"path": "a", "line": "12"}]}],
            [{"id": "F1", "evidence": [{"path": "a", "line": True}]}],
            [{"id": "F1", "evidence": [{"path": "a", "quote": 12}]}],
        ]
        for findings in bad_findings:
            with self.subTest(findings=findings), self.assertRaises(ValueError):
                verifier.load_findings(report(findings))

    def test_invalid_json_is_an_error(self):
        with self.assertRaises(ValueError):
            verifier.load_findings("```nlpm-findings\n{broken\n```")


class Citations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / "repo"
        self.root.mkdir()
        (self.root / "src").mkdir()
        (self.root / "src" / "route.ts").write_text("line one\nexport const GET = handler\nline three\n", encoding="utf-8")

    def result(self, *citations):
        return verifier.verify([{"id": "F1", "rule": "P05", "evidence": list(citations)}], self.root)[0]

    def test_real_citation_is_verified(self):
        citation = {"path": "src/route.ts", "line": 2, "quote": "export const GET"}
        self.assertEqual(self.result(citation)["status"], "verified")

    def test_invented_file_fails(self):
        self.assertEqual(self.result({"path": "src/invented.ts", "line": 1})["status"], "failed")

    def test_line_past_the_end_fails(self):
        self.assertEqual(self.result({"path": "src/route.ts", "line": 99})["status"], "failed")

    def test_invented_quote_fails(self):
        result = self.result({"path": "src/route.ts", "line": 2, "quote": "stripe.charge"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("quoted text", result["reasons"][0])

    def test_quote_may_drift_two_lines(self):
        self.assertEqual(self.result({"path": "src/route.ts", "line": 1, "quote": "line three"})["status"], "verified")

    def test_quote_further_away_fails(self):
        (self.root / "long.txt").write_text("\n".join(f"row {i}" for i in range(20)), encoding="utf-8")
        self.assertEqual(self.result({"path": "long.txt", "line": 1, "quote": "row 15"})["status"], "failed")

    def test_path_escape_fails(self):
        (self.root.parent / "outside.txt").write_text("x", encoding="utf-8")
        self.assertIn("outside", self.result({"path": "../outside.txt"})["reasons"][0])

    def test_symlink_escape_fails(self):
        (self.root.parent / "outside.txt").write_text("x", encoding="utf-8")
        (self.root / "link.txt").symlink_to(self.root.parent / "outside.txt")
        self.assertIn("outside", self.result({"path": "link.txt"})["reasons"][0])

    def test_unusable_paths_fail_instead_of_crashing(self):
        for path in ("a\0b.txt", "x" * 5000 + ".txt"):
            with self.subTest(path=path[:12]):
                self.assertEqual(self.result({"path": path, "line": 1})["status"], "failed")

    def test_link_loop_fails_instead_of_crashing(self):
        (self.root / "loop").symlink_to(self.root / "loop")
        self.assertEqual(self.result({"path": "loop", "line": 1})["status"], "failed")

    def test_plain_named_link_to_a_secret_file_fails(self):
        (self.root / ".env.synthetic").write_text("x\n", encoding="utf-8")
        (self.root / "public-link.txt").symlink_to(self.root / ".env.synthetic")
        result = self.result({"path": "public-link.txt", "line": 1, "quote": "x"})
        self.assertEqual(result["status"], "failed")
        self.assertIn("secret-style", result["reasons"][0])

    def test_bare_file_name_is_unverifiable_not_verified(self):
        self.assertEqual(self.result({"path": "src/route.ts"})["status"], "unverifiable")

    def test_one_bare_citation_keeps_the_finding_unverifiable(self):
        specific = {"path": "src/route.ts", "line": 1}
        self.assertEqual(self.result(specific, {"path": "src/route.ts"})["status"], "unverifiable")

    def test_citing_a_secret_style_file_fails_without_opening_it(self):
        for name in (".env", ".env.example", "config/.env.local", "certs/server.pem", "credentials.json"):
            result = self.result({"path": name, "line": 1})
            self.assertIn("secret-style", result["reasons"][0], name)

    def test_template_named_like_source_is_not_flagged(self):
        (self.root / "environment.ts").write_text("x\n", encoding="utf-8")
        self.assertEqual(self.result({"path": "environment.ts", "line": 1})["status"], "verified")

    def test_no_evidence_is_unverifiable_not_verified(self):
        self.assertEqual(self.result()["status"], "unverifiable")

    def test_one_bad_citation_fails_the_finding(self):
        good = {"path": "src/route.ts", "line": 1}
        self.assertEqual(self.result(good, {"path": "gone.ts"})["status"], "failed")


class TableMatch(unittest.TestCase):
    def test_matching_table_and_block_agree(self):
        findings = [{"id": "F1", "rule": "P05"}, {"id": "F2", "rule": "P33"}]
        self.assertIsNone(verifier.table_mismatch(report(findings), findings))

    def test_table_row_missing_from_block_is_caught(self):
        self.assertIn("table has 1 rows", verifier.table_mismatch(report([], rows=["P99"]), []))

    def test_block_entry_missing_from_table_is_caught(self):
        findings = [{"id": "F1", "rule": "P05"}]
        self.assertIsNotNone(verifier.table_mismatch(report(findings, rows=[]), findings))

    def test_same_count_different_rule_is_caught(self):
        findings = [{"id": "F1", "rule": "P05"}]
        self.assertIsNotNone(verifier.table_mismatch(report(findings, rows=["P06"]), findings))

    def test_compound_rule_cell_uses_its_first_id(self):
        findings = [{"id": "F1", "rule": "P30"}]
        text = report(findings, rows=["P30、P12"])
        self.assertIsNone(verifier.table_mismatch(text, findings))

    def test_report_without_the_section_is_caught(self):
        self.assertIn("no 发现清单", verifier.table_mismatch("# nothing", []))


class StateDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.root, self.state = base / "repo", base / "state"
        self.root.mkdir()
        self.state.mkdir()
        (self.state / "usage-log.md").write_text("entry\n", encoding="utf-8")
        self.finding = {"id": "F1", "rule": "P31",
                        "evidence": [{"path": "usage-log.md", "line": 1, "in_state_dir": True}]}

    def test_citation_is_checked_in_the_state_dir(self):
        self.assertEqual(verifier.verify([self.finding], self.root, self.state)[0]["status"], "verified")

    def test_citation_without_a_state_dir_fails(self):
        self.assertEqual(verifier.verify([self.finding], self.root)[0]["status"], "failed")

    def test_state_dir_boundary_is_enforced(self):
        self.finding["evidence"][0]["path"] = "../repo/x.txt"
        self.assertEqual(verifier.verify([self.finding], self.root, self.state)[0]["status"], "failed")


class Cli(unittest.TestCase):
    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "a.txt").write_text("hello\n", encoding="utf-8")
            good = root / "good.md"
            good.write_text(report([{"id": "F1", "rule": "P05", "evidence": [{"path": "a.txt", "line": 1}]}]), encoding="utf-8")
            bad = root / "bad.md"
            bad.write_text(report([{"id": "F1", "rule": "P05", "evidence": [{"path": "b.txt"}]}]), encoding="utf-8")
            empty = root / "empty.md"
            empty.write_text("no block", encoding="utf-8")
            self.assertEqual(verifier.main([str(good), "--target", str(root)]), 0)
            self.assertEqual(verifier.main([str(bad), "--target", str(root)]), 1)
            self.assertEqual(verifier.main([str(empty), "--target", str(root)]), 2)


class Catalog(unittest.TestCase):
    def test_rule_ids_are_contiguous_and_unique(self):
        ids = re.findall(r"^\| (P\d\d) \|", SKILL.read_text(encoding="utf-8"), re.MULTILINE)
        expected = [f"P{i:02d}" for i in range(1, len(ids) + 1)]
        self.assertEqual(ids, expected)

    def test_every_doc_names_the_same_range(self):
        count = len(re.findall(r"^\| P\d\d \|", SKILL.read_text(encoding="utf-8"), re.MULTILINE))
        wanted = f"P01–P{count}"
        for rel in ("skills/nlpm/product-advising/SKILL.md", "agents/advisor.md", "commands/advise.md", "README.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn(wanted, text, rel)
            # P01–P04 is the gate-evidence group, a legitimate sub-range.
            ranges = set(re.findall(r"P01[–-]P\d\d", text)) - {"P01–P04"}
            self.assertEqual(ranges, {wanted}, rel)

    def test_codex_mirror_differs_only_by_the_invocable_line(self):
        source = [line for line in SKILL.read_text(encoding="utf-8").splitlines() if line != "user-invocable: false"]
        self.assertEqual(source, MIRROR.read_text(encoding="utf-8").splitlines())

    def test_manifest_versions_match(self):
        versions = set()
        for rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            versions.add(json.loads((ROOT / rel).read_text(encoding="utf-8"))["version"])
        market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        versions.add(market["plugins"][0]["version"])
        self.assertEqual(len(versions), 1, versions)


if __name__ == "__main__":
    unittest.main()
