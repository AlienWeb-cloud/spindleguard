# Native Mac app

The published tree now includes a SwiftUI app that drives the real C
broker, `sg` control CLI, bindcheck, and topology helper. It is a
front door for the **prototype**, not evidence-drive isolation.

## Build (macOS only)

From `outputs/spindleguard/`, with Command Line Tools, Python 3 and FUSE-T:

```
make
make app
open SpindleGuard.app
./sg app
```

`make app` on Linux exits 2 with an example invocation. It overwrites
bundle files in place and does not delete the `.app` tree.

The bundle identifier is `cloud.alienweb.spindleguard`. Minimum macOS 13.
The app is not App Sandboxed (FUSE-T mounts will not survive a sandbox).

## What the UI actually does

| Pane | Wired to |
| --- | --- |
| Broker | New disposable session, choose source/mount, write prefix, delay, start, stop, Finder |
| Queue | Live JSONL from the broker stderr; concurrent read probe |
| Identity | Example fixture bind, tree scan, logged manifest rotation (dry-run default) |
| Topology | `sg topology --path SOURCE` after /Volumes and /dev refusal |
| Doctor | `sg doctor --json` (FUSE-T dylib, broker binary, Swift) |

Start runs `PathPolicy` in Swift, then execs `Contents/Helpers/spindleguard`.
Stop calls `/sbin/umount` then terminates the process. Sessions live under
`work/ui-session-*` and are retained.

## What it will not do

It will not open host `/dev` or `/Volumes`. Identity bind uses the
in-memory fixture. It does not confine agents, share queues across
mounts, or replace a review of unpublished local desktop code.

## `sg`

```
./sg --help
./sg doctor --json
./sg session-create --parent ./work --json
./sg start --dry-run --source DIR --mount DIR --write-prefix /Workspace --delay-ms 150 --json
./sg scan --root . --json
```

`sg start` without `--dry-run` execs the C broker only when doctor says
the host can mount (macOS + FUSE-T + built binary).
