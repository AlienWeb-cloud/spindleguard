# Native Mac app

The published tree includes a SwiftUI app that drives the real C
broker, `sg` control CLI, bindcheck, and topology helper. It is a
front door for the **prototype**, not evidence-drive isolation.

## Install (macOS)

From the repository root, with Apple's Command Line Tools and Python 3:

```
./sg setup
./sg verify --quick
open outputs/spindleguard/SpindleGuard.app
```

`./sg setup` builds the native app when `swiftc` is present. It builds
the C broker only when FUSE-T is already installed. FUSE-T is **never**
installed unless you pass `--install-fuse --yes`:

```
./sg setup --install-fuse --yes
```

or copy `brew install macos-fuse-t/homebrew-cask/fuse-t` from the Setup
pane. Official docs: https://github.com/macos-fuse-t/fuse-t

From `outputs/spindleguard/`:

```
./sg setup
make app
open SpindleGuard.app
./sg app
```

`make app` on Linux exits 2 with an example invocation. It overwrites
bundle files in place and does not delete the `.app` tree. It does **not**
require FUSE-T: the UI opens on Setup/Doctor first, then you install
FUSE-T and run Setup again to compile the helper.

The bundle identifier is `cloud.alienweb.spindleguard`. Minimum macOS 13.
The app is not App Sandboxed (FUSE-T mounts will not survive a sandbox).

When the app is launched from a copied bundle whose Resources directory
is not writable, sessions are created under
`~/Library/Application Support/SpindleGuard/sessions`. They are retained.

## What the UI actually does

| Pane | Wired to |
| --- | --- |
| Setup | Doctor checklist, `sg setup` / dry-run, FUSE-T confirm+brew, `sg verify --quick`, session parent, new/load session |
| Broker | New/load session, source/mount pickers, write prefix, delay, start, stop, unmount, policy-check, start dry-run, Finder, reveal log |
| Queue | Live JSONL from the broker stderr; concurrent read probe; reveal log |
| Identity | Example fixture bind, JSON pickers, tree scan, logged manifest rotation (dry-run default) |
| Retain | List retained sessions. There is **no deletion bucket**; nothing is emptied or unlinked |
| Topology | `sg topology --path SOURCE` after /Volumes and /dev refusal |
| Doctor | Same checklist, setup, verify, FUSE-T command copy |

Start runs `PathPolicy` in Swift, then execs `Contents/Helpers/spindleguard`
when doctor says the host can mount. Stop calls `/sbin/umount` then
terminates the process. Session files are never deleted.

Every `sg` subcommand that the prototype exposes is reachable from a
button, the Control menu, the Setup/Broker/Control command menus, or the
**menu bar extra** (the SpindleGuard disk icon in the macOS menu bar).

A loopback preview of the same chrome is available without compiling Swift:

```
./sg ui --port 8765
```

It binds `127.0.0.1` only and refuses FUSE install, `verify --full`, and
non-dry-run start/unmount.

## What it will not do

It will not open host `/dev` or `/Volumes`. Identity bind uses the
in-memory fixture. Homebrew FUSE-T install requires an explicit confirm
(`--yes`). It does not confine agents, share queues across mounts, or
replace a review of unpublished local desktop code.

## `sg`

```
./sg --help
./sg setup --dry-run --json
./sg setup
./sg verify --quick
./sg doctor --json
./sg session-create --parent ./work --json
./sg session-load --file ./work/ui-session-*/session.json --json
./sg session-list --parent ./work --json
./sg ui --port 8765
./sg start --dry-run --source DIR --mount DIR --write-prefix /Workspace --delay-ms 150 --json
./sg unmount --mount DIR --dry-run
./sg scan --root . --json
```

`sg start` without `--dry-run` execs the C broker only when doctor says
the host can mount (macOS + FUSE-T + built binary).
