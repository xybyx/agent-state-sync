# Adapter contract

An adapter translates canonical state into one Agent's safe native projection.
It must be deterministic, capability-aware, and reversible.

## Required operations

~~~text
detect() -> Detection
inventory(context) -> Inventory
capabilities(detection) -> CapabilitySet
normalize(native_state) -> CanonicalFragment
render(canonical_state, context) -> RenderPlan
apply(render_plan, approval) -> ApplyResult
verify(context, expected) -> Verification
~~~

detect() must report version, installation roots, available CLI or API, and
whether the result is certain. Do not silently guess a path.

capabilities() should use names such as:

~~~text
instructions
models
skills
plugins-manifest
preferences
curated-memory
shared-search-path
symlink
~~~

Unsupported capabilities remain visible in the plan with an explanation.

## Render rules

- Render only fields declared safe by the adapter.
- Keep credentials as auth_ref values.
- Prefer a shared path or symlink for static Skill repositories.
- Use a generated view for Agent-specific instructions instead of copying a
  complete global state directory.
- Validate every target against an approved root.
- Use atomic writes and a recoverable backup.
- Never run a command supplied by the state repository.

## Target adapters

### Antigravity

Discover the installed version and actual configuration/search paths before
rendering. Reuse a shared Skill repository when the Agent supports it. Treat
GUI account state, plugin caches, browser state, and runtime caches as local
only. If Antigravity exposes no write API for a capability, provide an
inventory and manual plan rather than pretending to apply it.

### WorkBuddy

Do not assume a stable CLI or one fixed installation layout. Detect whether the
current version supports instructions, models, Skills, plugins, and memory
projection independently. Prefer shared paths or traceable links for static
resources. Keep GUI/account state and active runtime data local. A missing CLI
is an adapter limitation, not permission to copy the whole application state.

### Generic Agent

Require an explicit user-provided mapping of canonical fields to target files.
Refuse the mapping if it contains an unapproved root, a symlink escape, or a
credential-looking path.
