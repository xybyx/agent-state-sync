# WorkBuddy adapter notes

WorkBuddy installations can differ by version and may be GUI-first. The
adapter must not assume that a CLI, a fixed configuration directory, or a
single plugin layout exists.

1. Detect the version and available control surface.
2. Locate user-approved instruction and Skill paths.
3. Inventory model, preference, plugin-manifest, and curated-memory support
   independently.
4. Prefer a shared Skill repository or traceable link.
5. Keep account state, browser state, application caches, and active runtime
   data local.

If the current installation cannot be safely written, return an inventory,
diff, and manual action plan. Never copy the full WorkBuddy application state
to make the adapter appear complete.
