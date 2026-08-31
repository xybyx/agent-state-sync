#!/usr/bin/env python3
"""Safe, dependency-free primitives for agent-state-sync.

The first version deliberately inventories and plans before it applies anything.
Agent-native writes belong to reviewed adapters, not to this generic core.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
INVENTORY_VERSION = 1
MAX_SCAN_BYTES = 4 * 1024 * 1024
MAX_HASH_BYTES = 128 * 1024 * 1024

DENY_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "Cache",
    "Caches",
    "cache",
    "model-cache",
    "model-caches",
    "models-cache",
    "plugin-cache",
    "plugin-caches",
}

DENY_FILE_PATTERNS = [
    ".env",
    ".env.*",
    "credentials*",
    "*credentials*",
    "secrets*",
    "*secret*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "cookies*",
    "*cookies*",
    "*session*",
    "*.sqlite",
    "*.sqlite3",
    "*.sqlite-*",
    "*.db",
    "*.db-*",
    "*.wal",
    "*.shm",
]

SECRET_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    (
        "known-token-prefix",
        re.compile(
            r"\b(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
            r"xox[baprs]-[A-Za-z0-9-]{20,})\b"
        ),
    ),
    (
        "bearer-token",
        re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    ),
    (
        "credential-assignment",
        re.compile(
            r"(?i)['\"]?(?:api[_-]?key|access[_-]?token|client[_-]?secret|"
            r"password)['\"]?\s*[:=]\s*['\"]?[A-Za-z0-9._~+/=-]{16,}"
        ),
    ),
]

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
VERSION_CONTROL_DIR_NAMES = {".git", ".hg", ".svn"}


class SyncError(Exception):
    """Expected, user-actionable failure."""


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def print_json(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def validate_identifier(value, label):
    """Reject path separators and ambiguous identifiers before building filenames."""
    if not isinstance(value, str) or not IDENTIFIER_PATTERN.fullmatch(value):
        raise SyncError(
            "{} must be 1-128 ASCII letters, digits, dots, underscores, or hyphens; "
            "it must start with a letter or digit".format(label)
        )
    return value


def write_json(path, value):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".agent-state-sync-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path):
    path = Path(path).expanduser()
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise SyncError("JSON file not found: {}".format(path)) from exc
    except json.JSONDecodeError as exc:
        raise SyncError("Invalid JSON at {}: {}".format(path, exc)) from exc


def path_reason(path, root):
    path = Path(path)
    root = Path(root)
    if path.is_symlink():
        return "symlink"
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "outside-root"
    parts = relative.parts
    if any(part in DENY_DIR_NAMES for part in parts[:-1]):
        return "denylisted-directory"
    name = path.name
    if any(fnmatch.fnmatch(name, pattern) for pattern in DENY_FILE_PATTERNS):
        return "denylisted-file"
    return None


def iter_safe_files(root):
    """Yield files without following symlinks or denylisted directories."""
    root = Path(root).expanduser()
    if not root.exists():
        raise SyncError("Root does not exist: {}".format(root))
    if root.is_symlink():
        return
    if root.is_file():
        if not path_reason(root, root):
            yield root
        return

    for directory, directories, files in os.walk(str(root), followlinks=False):
        current = Path(directory)
        kept_directories = []
        for name in directories:
            candidate = current / name
            if candidate.is_symlink() or name in DENY_DIR_NAMES:
                continue
            kept_directories.append(name)
        directories[:] = kept_directories
        for name in files:
            candidate = current / name
            if path_reason(candidate, root) is None:
                yield candidate


def iter_scan_files(root):
    """Yield explicit scan targets, skipping only known binary/cache trees."""
    root = Path(root).expanduser()
    if not root.exists():
        raise SyncError("Scan path does not exist: {}".format(root))
    if root.is_file() and not root.is_symlink():
        yield root
        return
    if root.is_symlink():
        return
    for directory, directories, files in os.walk(str(root), followlinks=False):
        current = Path(directory)
        directories[:] = [
            name
            for name in directories
            if name not in {".git", "node_modules", "__pycache__", ".venv", "venv"}
            and not (current / name).is_symlink()
        ]
        for name in files:
            candidate = current / name
            if not candidate.is_symlink():
                yield candidate


def scan_file(path):
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError:
        return [{"type": "unreadable", "line": 0}]
    if size > MAX_SCAN_BYTES:
        return [{"type": "skipped-large-file", "line": 0}]
    try:
        data = path.read_bytes()
    except OSError:
        return [{"type": "unreadable", "line": 0}]
    if b"\x00" in data:
        return []
    text = data.decode("utf-8", errors="replace")
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append({"type": label, "line": line_number})
    return findings


def hash_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def relative_key(record):
    return "{}:{}".format(record["root_id"], record["relative_path"])


def inventory_root(root, root_id, excluded):
    root = Path(root).expanduser()
    records = []
    for path in iter_safe_files(root):
        findings = scan_file(path)
        if findings and findings[0]["type"] != "skipped-large-file":
            excluded.append({"root_id": root_id, "relative_path": str(path.relative_to(root)), "reason": "secret-pattern"})
            continue
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        item = {
            "root_id": root_id,
            "relative_path": relative,
            "size": size,
            "sha256": None,
        }
        if size <= MAX_HASH_BYTES:
            item["sha256"] = hash_file(path)
        else:
            item["hash_status"] = "skipped-large-file"
        records.append(item)
    return records


def cmd_inventory(args):
    if not args.root:
        raise SyncError("At least one --root is required")
    validate_identifier(args.machine, "--machine")
    validate_identifier(args.agent, "--agent")
    excluded = []
    records = []
    roots = []
    for index, root in enumerate(args.root):
        root_path = Path(root).expanduser()
        root_id = "root-{}".format(index)
        roots.append({"id": root_id, "name": root_path.name or root_id})
        records.extend(inventory_root(root_path, root_id, excluded))
    result = {
        "inventory_version": INVENTORY_VERSION,
        "created_at": utc_now(),
        "machine_id": args.machine,
        "agent_id": args.agent,
        "roots": roots,
        "files": sorted(records, key=relative_key),
        "excluded": {
            "count": len(excluded),
            "items": excluded,
        },
    }
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0


def validate_state_repo(repo):
    repo = Path(repo).expanduser()
    issues = []
    required_files = [repo / "policy.json", repo / "schema-version.json"]
    required_dirs = [repo / "state" / "shared", repo / "state" / "machines", repo / "state" / "agents"]
    if not repo.is_dir():
        return [{"type": "missing-repository", "path": str(repo)}]
    for path in required_files:
        if not path.is_file():
            issues.append({"type": "missing-file", "path": str(path.relative_to(repo))})
    for path in required_dirs:
        if not path.is_dir():
            issues.append({"type": "missing-directory", "path": str(path.relative_to(repo))})

    policy_path = repo / "policy.json"
    if policy_path.is_file():
        try:
            policy = load_json(policy_path)
            if not isinstance(policy, dict) or not isinstance(policy.get("space_policy"), dict):
                issues.append({"type": "missing-space-policy", "path": "policy.json"})
        except SyncError as exc:
            issues.append({"type": "invalid-json", "path": "policy.json", "message": str(exc)})

    schema_path = repo / "schema-version.json"
    if schema_path.is_file():
        try:
            schema = load_json(schema_path)
            if not isinstance(schema, dict):
                issues.append({"type": "invalid-schema-document", "path": "schema-version.json"})
            elif schema.get("schema") != "agent-state-sync":
                issues.append({"type": "wrong-schema", "path": "schema-version.json"})
            if isinstance(schema, dict) and schema.get("version") != SCHEMA_VERSION:
                issues.append({"type": "unsupported-schema-version", "path": "schema-version.json"})
        except SyncError as exc:
            issues.append({"type": "invalid-json", "path": "schema-version.json", "message": str(exc)})

    if repo.is_dir():
        for directory, directories, files in os.walk(str(repo), followlinks=False):
            current = Path(directory)
            for name in list(directories):
                candidate = current / name
                if candidate.is_symlink():
                    issues.append(
                        {
                            "type": "denylisted-path",
                            "path": str(candidate.relative_to(repo)),
                            "reason": "symlink",
                        }
                    )
                    directories.remove(name)
                    continue
                if current == repo and name in VERSION_CONTROL_DIR_NAMES:
                    directories.remove(name)
                    continue
                if name in DENY_DIR_NAMES:
                    issues.append(
                        {
                            "type": "denylisted-path",
                            "path": str(candidate.relative_to(repo)),
                            "reason": "denylisted-directory",
                        }
                    )
                    directories.remove(name)
            for name in files:
                path = current / name
                reason = path_reason(path, repo)
                if reason:
                    issues.append(
                        {
                            "type": "denylisted-path",
                            "path": str(path.relative_to(repo)),
                            "reason": reason,
                        }
                    )
                    continue
                relative = path.relative_to(repo).as_posix()
                if path.suffix.lower() == ".json":
                    try:
                        load_json(path)
                    except SyncError as exc:
                        issues.append({"type": "invalid-json", "path": relative, "message": str(exc)})
                findings = scan_file(path)
                if findings and findings[0]["type"] != "skipped-large-file":
                    issues.append({"type": "secret-pattern", "path": relative, "findings": findings})
    return issues


def cmd_validate(args):
    issues = validate_state_repo(args.state_repo)
    result = {"ok": not issues, "state_repo": str(Path(args.state_repo).expanduser()), "issues": issues}
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0 if not issues else 1


def cmd_doctor(args):
    issues = validate_state_repo(args.state_repo)
    repo = Path(args.state_repo).expanduser()
    result = {
        "ok": not issues,
        "checks": {
            "schema": not any(issue["type"].endswith("schema") or "schema" in issue["type"] for issue in issues),
            "space_policy": not any(issue["type"] == "missing-space-policy" for issue in issues),
            "secret_boundary": not any(issue["type"] == "secret-pattern" for issue in issues),
            "state_layout": all(
                (repo / relative).exists()
                for relative in ("state/shared", "state/machines", "state/agents")
            )
            if repo.is_dir()
            else False,
        },
        "issues": issues,
    }
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0 if not issues else 1


def load_inventory(path):
    inventory = load_json(path)
    if not isinstance(inventory, dict):
        raise SyncError("Inventory must be a JSON object: {}".format(path))
    if inventory.get("inventory_version") != INVENTORY_VERSION:
        raise SyncError("Unsupported inventory version in {}".format(path))
    if not isinstance(inventory.get("files"), list):
        raise SyncError("Inventory files must be a list: {}".format(path))
    validate_identifier(inventory.get("machine_id"), "inventory machine_id")
    validate_identifier(inventory.get("agent_id"), "inventory agent_id")
    return inventory


def cmd_plan(args):
    validate_identifier(args.machine, "--machine")
    validate_identifier(args.agent, "--agent")
    repo = Path(args.state_repo).expanduser()
    issues = validate_state_repo(repo)
    if issues:
        result = {
            "plan_version": 1,
            "status": "blocked",
            "reason": "state-repo-validation-failed",
            "issues": issues,
        }
        if args.output:
            write_json(args.output, result)
        else:
            print_json(result)
        return 1

    current = load_inventory(args.inventory)
    if current.get("machine_id") != args.machine:
        raise SyncError("inventory machine_id does not match --machine")
    if current.get("agent_id") != args.agent:
        raise SyncError("inventory agent_id does not match --agent")
    baseline_path = repo / "state" / "machines" / "{}.inventory.json".format(args.machine)
    baseline = load_inventory(baseline_path) if baseline_path.is_file() else None
    old = {relative_key(item): item for item in (baseline or {}).get("files", [])}
    new = {relative_key(item): item for item in current.get("files", [])}
    changes = []
    for key in sorted(set(old) | set(new)):
        if key not in old:
            changes.append({"key": key, "status": "added", "after": new[key]})
        elif key not in new:
            changes.append({"key": key, "status": "removed", "before": old[key]})
        elif old[key] != new[key]:
            changes.append({"key": key, "status": "changed", "before": old[key], "after": new[key]})

    counts = Counter(change["status"] for change in changes)
    result = {
        "plan_version": 1,
        "status": "ready",
        "created_at": utc_now(),
        "machine_id": args.machine,
        "agent_id": args.agent,
        "baseline": str(baseline_path.relative_to(repo)) if baseline else None,
        "requires_confirmation": bool(changes),
        "write_actions": ["snapshot-baseline"] if changes else [],
        "summary": dict(sorted(counts.items())),
        "changes": changes,
    }
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0


def cmd_snapshot(args):
    if not args.confirm:
        raise SyncError("snapshot writes the private state repository; pass --confirm")
    validate_identifier(args.machine, "--machine")
    repo = Path(args.state_repo).expanduser()
    issues = validate_state_repo(repo)
    if issues:
        raise SyncError("state repository is not valid; run doctor first")
    inventory = load_inventory(args.inventory)
    if inventory.get("machine_id") != args.machine:
        raise SyncError("inventory machine_id does not match --machine")
    repo_root = repo.resolve()
    machines_root = (repo / "state" / "machines").resolve()
    try:
        machines_root.relative_to(repo_root)
    except ValueError as exc:
        raise SyncError("state/machines resolves outside the state repository") from exc
    destination = (machines_root / "{}.inventory.json".format(args.machine)).resolve()
    if destination.parent != machines_root:
        raise SyncError("snapshot destination escaped state/machines")
    write_json(destination, inventory)
    result = {
        "ok": True,
        "action": "snapshot-baseline",
        "path": str(destination),
        "note": "No git commit or push was performed.",
    }
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0


def cmd_secret_scan(args):
    findings = []
    scanned = 0
    for path in iter_scan_files(args.path):
        file_findings = scan_file(path)
        if file_findings and file_findings[0]["type"] != "skipped-large-file":
            scanned += 1
            findings.append(
                {
                    "path": str(path),
                    "findings": file_findings,
                }
            )
        else:
            scanned += 1
    result = {
        "ok": not findings,
        "path": str(Path(args.path).expanduser()),
        "scanned_files": scanned,
        "findings": findings,
    }
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0 if not findings else 1


def cmd_space_audit(args):
    groups = defaultdict(list)
    skipped = Counter()
    for index, root in enumerate(args.root):
        root_path = Path(root).expanduser()
        root_id = "root-{}".format(index)
        for path in iter_safe_files(root_path):
            size = path.stat().st_size
            if size > MAX_HASH_BYTES:
                skipped["large-file"] += 1
                continue
            findings = scan_file(path)
            if findings and findings[0]["type"] != "skipped-large-file":
                skipped["secret-pattern"] += 1
                continue
            key = (size, hash_file(path))
            groups[key].append(
                {
                    "root_id": root_id,
                    "path": str(path),
                    "relative_path": path.relative_to(root_path).as_posix(),
                    "size": size,
                }
            )

    duplicates = []
    reclaimable = 0
    for (size, digest), paths in sorted(groups.items(), key=lambda item: (item[0][0], item[0][1])):
        if len(paths) > 1:
            duplicates.append({"sha256": digest, "size": size, "copies": paths})
            reclaimable += size * (len(paths) - 1)
    result = {
        "ok": True,
        "roots": [str(Path(root).expanduser()) for root in args.root],
        "duplicate_groups": duplicates,
        "duplicate_group_count": len(duplicates),
        "potential_reclaimable_bytes": reclaimable,
        "skipped": dict(sorted(skipped.items())),
        "deletion_performed": False,
    }
    if args.output:
        write_json(args.output, result)
    else:
        print_json(result)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Safe agent state inventory and planning tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="inventory approved roots without copying files")
    inventory.add_argument("--root", action="append", required=True)
    inventory.add_argument("--machine", required=True)
    inventory.add_argument("--agent", required=True)
    inventory.add_argument("--output")
    inventory.set_defaults(function=cmd_inventory)

    validate = subparsers.add_parser("validate", help="validate a private state repository")
    validate.add_argument("--state-repo", required=True)
    validate.add_argument("--output")
    validate.set_defaults(function=cmd_validate)

    doctor = subparsers.add_parser("doctor", help="validate layout and secret boundary")
    doctor.add_argument("--state-repo", required=True)
    doctor.add_argument("--output")
    doctor.set_defaults(function=cmd_doctor)

    plan = subparsers.add_parser("plan", help="compare current inventory with machine baseline")
    plan.add_argument("--state-repo", required=True)
    plan.add_argument("--inventory", required=True)
    plan.add_argument("--machine", required=True)
    plan.add_argument("--agent", required=True)
    plan.add_argument("--output")
    plan.set_defaults(function=cmd_plan)

    snapshot = subparsers.add_parser("snapshot", help="write a reviewed machine baseline")
    snapshot.add_argument("--state-repo", required=True)
    snapshot.add_argument("--inventory", required=True)
    snapshot.add_argument("--machine", required=True)
    snapshot.add_argument("--confirm", action="store_true")
    snapshot.add_argument("--output")
    snapshot.set_defaults(function=cmd_snapshot)

    secret_scan = subparsers.add_parser("secret-scan", help="scan an explicit file or directory")
    secret_scan.add_argument("--path", required=True)
    secret_scan.add_argument("--output")
    secret_scan.set_defaults(function=cmd_secret_scan)

    space = subparsers.add_parser("space-audit", help="find duplicate safe files without deleting anything")
    space.add_argument("--root", action="append", required=True)
    space.add_argument("--output")
    space.set_defaults(function=cmd_space_audit)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.function(args)
    except SyncError as exc:
        print_json({"ok": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
