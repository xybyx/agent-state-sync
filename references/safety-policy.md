# Safety policy

The sync engine is an allowlist-driven projection tool. It must not become a
general-purpose home-directory copier.

## Never synchronize

Reject or skip:

- API keys, OAuth tokens, passwords, cookies, session files, and private keys;
- .env files and credential/config files whose purpose is authentication;
- SQLite, WAL, SHM, browser profiles, active sockets, and local databases;
- node_modules, virtual environments, package caches, model caches, and
  plugin caches;
- complete Agent state directories when the adapter has not split safe fields;
- arbitrary symlinks that point outside an approved root.

The scanner is a guardrail, not a proof that a file is safe. Keep the state
repository private and review every change.

## Required gates

Require explicit confirmation before:

- writing an Agent-native file;
- installing or updating a Skill or plugin;
- starting authentication or opening an OAuth flow;
- changing a model provider or default route;
- committing or pushing to a remote repository;
- creating a duplicate runtime or copy exception.

## Provenance

Pin third-party Skill and plugin sources to a revision and content digest.
Never execute an installer merely because it is named in a lock file. First
show provenance, write targets, permissions, dependencies, and paid-service
implications.

## Rollback

Before changing a safe target, create a timestamped recoverable backup inside
the local sync backup directory. Never delete the previous version as part of
normal apply. If a target is active or locked, stop and report it.
