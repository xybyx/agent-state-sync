import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import agent_state_sync as sync  # noqa: E402


class AgentStateSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.state = self.root / "state-repo"
        (self.state / "state" / "shared").mkdir(parents=True)
        (self.state / "state" / "machines").mkdir(parents=True)
        (self.state / "state" / "agents").mkdir(parents=True)
        sync.write_json(
            self.state / "schema-version.json",
            {"schema": "agent-state-sync", "version": 1},
        )
        sync.write_json(
            self.state / "policy.json",
            {
                "space_policy": {
                    "enabled": True,
                    "max_local_copies_per_artifact": 1,
                    "auto_delete_duplicates": False,
                }
            },
        )
        self.source = self.root / "approved"
        self.source.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_example_state_repo_is_valid(self):
        example = Path(__file__).parents[1] / "examples" / "state-repo"
        self.assertEqual(sync.validate_state_repo(example), [])

    def test_inventory_excludes_secret_pattern(self):
        (self.source / "safe.md").write_text("portable rule\n", encoding="utf-8")
        (self.source / "note.md").write_text(
            "token = sk-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8"
        )
        output = self.root / "inventory.json"
        code = sync.main(
            [
                "inventory",
                "--root",
                str(self.source),
                "--machine",
                "machine-a",
                "--agent",
                "antigravity",
                "--output",
                str(output),
            ]
        )
        self.assertEqual(code, 0)
        inventory = json.loads(output.read_text(encoding="utf-8"))
        paths = {item["relative_path"] for item in inventory["files"]}
        self.assertEqual(paths, {"safe.md"})
        self.assertEqual(inventory["excluded"]["count"], 1)

    def test_plan_and_snapshot_detect_change(self):
        safe = self.source / "safe.md"
        safe.write_text("version one\n", encoding="utf-8")
        inventory = self.root / "inventory.json"
        sync.main(
            [
                "inventory",
                "--root",
                str(self.source),
                "--machine",
                "machine-a",
                "--agent",
                "workbuddy",
                "--output",
                str(inventory),
            ]
        )
        plan = self.root / "plan.json"
        code = sync.main(
            [
                "plan",
                "--state-repo",
                str(self.state),
                "--inventory",
                str(inventory),
                "--machine",
                "machine-a",
                "--agent",
                "workbuddy",
                "--output",
                str(plan),
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(plan.read_text())["summary"], {"added": 1})

        self.assertEqual(
            sync.main(
                [
                    "snapshot",
                    "--state-repo",
                    str(self.state),
                    "--inventory",
                    str(inventory),
                    "--machine",
                    "machine-a",
                    "--confirm",
                ]
            ),
            0,
        )
        safe.write_text("version two\n", encoding="utf-8")
        sync.main(
            [
                "inventory",
                "--root",
                str(self.source),
                "--machine",
                "machine-a",
                "--agent",
                "workbuddy",
                "--output",
                str(inventory),
            ]
        )
        plan_result = self.root / "changed-plan.json"
        sync.main(
            [
                "plan",
                "--state-repo",
                str(self.state),
                "--inventory",
                str(inventory),
                "--machine",
                "machine-a",
                "--agent",
                "workbuddy",
                "--output",
                str(plan_result),
            ]
        )
        self.assertEqual(json.loads(plan_result.read_text())["summary"], {"changed": 1})

    def test_space_audit_never_deletes(self):
        first = self.source / "one.txt"
        second = self.source / "two.txt"
        first.write_text("same content\n", encoding="utf-8")
        second.write_text("same content\n", encoding="utf-8")
        output = self.root / "space.json"
        code = sync.main(
            [
                "space-audit",
                "--root",
                str(self.source),
                "--output",
                str(output),
            ]
        )
        self.assertEqual(code, 0)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["duplicate_group_count"], 1)
        self.assertFalse(result["deletion_performed"])
        self.assertTrue(first.exists())
        self.assertTrue(second.exists())

    def test_state_repo_rejects_secret_content(self):
        (self.state / "state" / "shared" / "bad.json").write_text(
            '{"api_key": "abcdefghijklmnop1234"}\n', encoding="utf-8"
        )
        issues = sync.validate_state_repo(self.state)
        self.assertTrue(any(issue["type"] == "secret-pattern" for issue in issues))


if __name__ == "__main__":
    unittest.main()
