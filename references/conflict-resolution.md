# Conflict resolution

Use a three-way comparison:

~~~text
base:     last applied baseline
local:    current machine/Agent inventory
remote:   checked-out private state repository
~~~

## Merge classes

| Class | Default |
| --- | --- |
| Shared canonical field | Semantic merge by stable ID |
| Machine overlay | Local machine wins |
| Agent overlay | Adapter wins after capability check |
| Derived native file | Regenerate from canonical state |
| Secret or runtime state | Exclude and report |
| Path or version conflict | Stop and request a decision |

Do not use whole-file replacement for model configuration, collaboration rules,
or memory. A changed timestamp is not a semantic conflict.

Every plan should contain:

- the base revision or missing-baseline status;
- local and remote hashes;
- change class;
- proposed action;
- whether explicit approval is required;
- the reason if the action would create a second local copy.

When a conflict cannot be resolved safely, preserve both inputs in the plan,
make no write, and ask the user to choose.
