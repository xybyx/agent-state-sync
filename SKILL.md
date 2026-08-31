---
name: agent-state-sync
description: Synchronize safe, portable AI-agent state across Codex, Claude, OpenClaw, Antigravity, WorkBuddy, and other agents through a Git-backed state repository, including model routing, multi-agent collaboration rules, skills, plugins, preferences, and curated project memory. Use when inspecting drift, planning or applying synchronization, onboarding a machine or agent, reusing existing local resources, or auditing disk usage. Always prefer existing runtimes, shared search paths, traceable symlinks, and one local copy per artifact. Never synchronize secrets, credentials, live databases, browser sessions, caches, virtual environments, model caches, plugin caches, or active runtime state.
---

# Agent State Sync

Use this skill as a safety-first control plane for portable agent state. Keep the
public Skill code separate from the user's private state repository. Treat local
agent directories as inputs to inventory and adapters, never as files to copy
blindly.

## Core contract

- Store only normalized, portable state in the private Git repository.
- Keep secrets as references such as "keychain://..." or "env://..."; never read
  them into a snapshot.
- Start every new machine or agent with a read-only inventory.
- Generate a plan before writing anything.
- Require explicit confirmation for apply, authentication, plugin installation,
  external writes, or git push.
- Preserve existing runtimes, Skill repositories, plugin installations, and
  local services whenever they can be reused.
- Never delete duplicate files automatically. Report them and create a
  user-reviewable cleanup plan.

## Supported targets

Support these targets through capability-based adapters:

- Codex
- Claude
- OpenClaw
- Antigravity
- WorkBuddy
- Generic Agent

Do not assume that Antigravity or WorkBuddy expose the same paths, CLI, or
configuration schema on every version. Detect the installation, report
capabilities, and mark unsupported fields instead of forcing an overwrite.

## Workflow

### 1. Locate the state repository

Read the local, non-synced pointer configured by the user. It should contain:

- the private repository path or Git remote;
- a stable machine identifier;
- the current Agent identifier;
- approved local roots and adapter settings.

Do not infer a credential path or copy a complete home-directory state folder.

### 2. Inventory read-only

Use the bundled CLI for deterministic checks:

~~~bash
python3 <skill-dir>/scripts/agent_state_sync.py inventory \
  --root <approved-root> \
  --machine <machine-id> \
  --agent <agent-id> \
  --output <inventory.json>
~~~

Use 1-128 character stable ASCII identifiers for `--machine` and `--agent`.
Start with a letter or digit; after that use only letters, digits, dots,
underscores, and hyphens. Do not pass paths or user-supplied free text as
identifiers.

Skip denylisted paths, symlinks, caches, databases, virtual environments, and
files that trigger the secret scanner. Do not include secret values in output.

### 3. Validate and scan

Before comparing state, validate the repository and scan it for credentials:

~~~bash
python3 <skill-dir>/scripts/agent_state_sync.py doctor \
  --state-repo <private-state-repo>
~~~

If the check fails, stop and explain the findings. Do not repair by deleting
files or weakening the policy.

### 4. Plan a three-way change

Compare the last applied baseline, the current local inventory, and the checked
out repository state:

~~~bash
python3 <skill-dir>/scripts/agent_state_sync.py plan \
  --state-repo <private-state-repo> \
  --inventory <inventory.json> \
  --machine <machine-id> \
  --agent <agent-id> \
  --output <plan.json>
~~~

Present added, removed, changed, unsupported, secret-blocked, and
space-duplication items separately. A missing adapter capability is not a
permission to copy the source file.

### 5. Apply through an adapter

Only an adapter with an explicit target mapping may apply a plan. Require user
confirmation immediately before applying. Prefer, in order:

1. reuse an existing installation;
2. add an existing shared search path;
3. create a traceable symlink or platform equivalent;
4. use one local clone;
5. copy only with a recorded exception and a reason.

The generic core must refuse arbitrary target paths. Adapters must validate
allowed roots, make a recoverable backup of safe files, and verify after the
write.

### 6. Snapshot and publish

After verification, update only the machine baseline or curated shared state.
Commit and push only when the user explicitly requests publication. Never
publish a raw inventory containing absolute paths, credentials, or runtime
state.

## Minimum-space policy

Use one local state mirror per computer, not one per Agent. Reuse one local copy
of each Skill repository and one existing runtime whenever possible. Keep
machine-local pointers small and outside the shared repository.

Run the space audit before proposing a copy:

~~~bash
python3 <skill-dir>/scripts/agent_state_sync.py space-audit \
  --root <approved-root> \
  --output <space-audit.json>
~~~

If a duplicate is found, report its paths and hashes. Do not remove it. A
version conflict, isolation requirement, or incompatible platform may justify a
second copy, but record that exception in the machine state.

## Resource routing

Read only the reference needed for the current operation:

- State format: references/state-schema.md
- Safety boundary: references/safety-policy.md
- Adapter implementation: references/adapter-contract.md
- Merge rules: references/conflict-resolution.md
- Antigravity: references/adapters/antigravity.md
- WorkBuddy: references/adapters/workbuddy.md
