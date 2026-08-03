# Antigravity adapter notes

Treat Antigravity as a capability-based target, not as a fixed directory
layout. On every machine:

1. Detect the installed version and executable or app location.
2. Detect the Skill search path and whether it accepts symlinks or shared paths.
3. Detect which model, instruction, plugin-manifest, preference, and memory
   fields are exposed.
4. Inventory read-only before rendering anything.
5. Reuse existing local resources before proposing installation.

Do not copy Antigravity's complete application state, account data, browser
profiles, plugin caches, or runtime caches. If a capability is unavailable,
show a manual plan and mark it unsupported.
