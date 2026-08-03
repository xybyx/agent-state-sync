# State schema

The private state repository is a versioned, human-reviewable projection of
portable agent state. It is not a backup of any home directory.

## Required files

~~~text
policy.json
schema-version.json
state/shared/
state/machines/
state/agents/
~~~

schema-version.json:

~~~json
{
  "schema": "agent-state-sync",
  "version": 1
}
~~~

policy.json must contain a space_policy object and may contain:

~~~json
{
  "space_policy": {
    "enabled": true,
    "prefer_order": [
      "reuse-existing",
      "shared-search-path",
      "traceable-symlink",
      "single-local-clone",
      "copy-only-with-exception"
    ],
    "max_local_copies_per_artifact": 1,
    "reuse_existing_runtimes": true,
    "reuse_existing_skill_repositories": true,
    "reuse_existing_plugin_installations": true,
    "duplicate_requires_reason": true,
    "auto_delete_duplicates": false
  },
  "approval": {
    "apply": "explicit",
    "plugin_install": "explicit",
    "authentication": "explicit",
    "git_push": "explicit"
  }
}
~~~

## Shared state

Keep portable state under state/shared/:

- models.json: logical routes, provider/model identifiers, fallback order,
  and secret references only;
- collaboration.json: lead Agent, exact model assignment, bounded tasks,
  handoffs, retries, failures, and reviewer requirements;
- preferences.json: language, formatting, communication, and working style;
- skills.lock.json: source, revision, digest, capability, and review status;
- plugins.lock.json: plugin identifier, version, provenance, and install
  approval state;
- memory/: curated Markdown or JSONL decisions, not raw chat databases.

## Machine and Agent overlays

Use state/machines/<machine-id>.json for operating-system details, approved
roots, local path mappings, and justified space exceptions.

Use state/agents/<agent-id>.json for adapter capabilities and render targets.
Do not store native credentials, browser sessions, plugin caches, or complete
native configuration files in either overlay.

## Stability rules

- Give memory items and routing rules stable IDs.
- Keep timestamps as metadata, not merge keys.
- Use logical model names in shared state; map them to native names in adapters.
- Store content hashes for Skill and plugin sources.
- Increment version when field meaning changes, not when a value changes.
