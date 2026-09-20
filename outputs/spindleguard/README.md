# SpindleGuard

A working, deliberately restricted macOS filesystem prototype: a real directory
appears through a virtual mount, with one FIFO queue around supported backing
operations. Ordinary applications wait when another callback is active.

**Disposable test data only. This does not yet protect your evidence drives or
confine Claude/Codex.** No driver, account, ACL, disk format or evidence changes
were made during development. The prototype refuses source and mount paths under
`/Volumes`. Tests use the local repository's `work/` directory and retain files.

## What works

- Real FUSE-T NFS mount; ordinary listing, reads, file creation and writes.
- Read-only default; explicit existing virtual directory prefix permits writes.
- One active backing callback; FIFO logs show queued/start/finish and wait times.
- Descriptor-relative paths reject symlinks, `..`, nested devices and special files.
- Writes to existing hardlinked files are refused; write-prefix matching respects
  directory boundaries.
- Read-only topology helper resolves APFS volume → physical store → whole disk.
- A real mount test uses two separate Python client processes and checks that a
  request for the second file waits behind a deliberately delayed first-file read.
- Identity binding (`bindcheck.assert_bound`): open a path only to get an fd,
  verify serial / PARTUUID / FS-UUID independently, return the fd. Device-shaped
  `open()` outside `bindcheck/` fails the control-plane suite. See
  [BINDCHECK.md](BINDCHECK.md).
- Native macOS SwiftUI app (`./sg setup` / `make app`) with Setup, Broker,
  Queue, Identity, Retain, Topology and Doctor panes wired to the C broker
  and `./sg`. Retain keeps three lists (active, bucket, purged). See
  [DESKTOP-APP.md](DESKTOP-APP.md).

See [architecture and reuse research](ARCHITECTURE.md), [upstream attribution](PROVENANCE.md)
and [recorded proof](PROOF.md).

## Install and test on another Mac

1. Copy this `spindleguard` directory onto the Mac's internal storage. Keep it in
   a local Git repository. If it is standalone, run `git init` in that directory
   before testing. No remote is required.
2. Install Apple's Command Line Tools if absent (`xcode-select --install`). You
   need `clang`, `make`, Git, Python 3, and `swiftc` for the native app.
3. From the **repository root**:

   ```sh
   ./sg setup
   ./sg verify --quick
   open outputs/spindleguard/SpindleGuard.app
   ```

   From this `outputs/spindleguard` directory, `./sg setup` then
   `open SpindleGuard.app` is enough. Setup builds the SwiftUI app when
   `swiftc` is present, and the C broker only when FUSE-T is already
   installed. It does not mount and does not open `/dev`.
4. FUSE-T is a system dependency with a separate license. The project never
   installs it unless you confirm:

   ```sh
   ./sg setup --install-fuse --yes
   ```

   Equivalent package-manager command (also copied from the Setup pane):
   `brew install macos-fuse-t/homebrew-cask/fuse-t`.
   Follow FUSE-T's [official instructions](https://github.com/macos-fuse-t/fuse-t).
   Tested runtime: **1.2.7**, macOS **26.5 / Darwin 25.5.0**, Apple Silicon.
5. Real mount proof (disposable data only; retains files):

   ```sh
   make
   make test
   ```

Build uses `/usr/local/include/fuse` and `/usr/local/lib/libfuse-t.dylib`, including
its required runtime search path. If the installed package uses different paths,
change the Makefile paths to match `fuse-t.pc`. Do not substitute Linux FUSE3
headers: this version uses the macOS FUSE2 API.

Agent-safe tests (no mounts, no host `/dev` or `/Volumes`):

```sh
SG_REQUIRE_FULL=1 make test-control
make test-bindcheck
./sg verify --quick
```

Native Mac UI (macOS 13+, Command Line Tools; FUSE-T only needed to mount):

```sh
./sg setup
open outputs/spindleguard/SpindleGuard.app
./outputs/spindleguard/sg --help
```

The Setup pane is the default. Create a disposable session there, then Start.

`make test` runs five topology tests, then real read/write and read-only mounts.
It prints `ALL MOUNT TESTS PASSED` only after content comparisons, cross-process
queue evidence, policy checks and unmounts. Its retained source files and logs
live under `<local-git-root>/work/proof-<unique-number>/`. It does not delete files.
A test failure raises an error; inspect that run's `broker.jsonl` for the runtime
error. If unmount fails, the printed retained mount path needs attention.

## Manual demonstration

Within the local Git repository, choose a new unused test directory name. Create
`work/manual/source/Workspace` and `work/manual/mount`, then place only disposable
files in the source. Add an empty `.spindleguard-test-root` marker in that source.
The explicitly writable directory must already exist.

Run in the project directory (use absolute paths for SOURCE and MOUNT):

```sh
./build/spindleguard SOURCE MOUNT /Workspace 150
```

It stays in the foreground and prints JSON lines to stderr. The last argument is
an artificial delay of 150 ms per read callback, solely to make waiting visible.
Omit both optional arguments for the default read-only mount. Pass `-` instead
of `/Workspace` to use read-only mode with a test delay.

Browse MOUNT from a second terminal, read a large disposable file, and start a
read of a different file in a third terminal. Read-ahead may enqueue multiple
requests: logs describe callbacks, not entire commands. `make test` performs
this scenario automatically and verifies the file-specific event ordering.

Unmount with `/sbin/umount MOUNT` after clients finish. The daemon then exits.
Do not remove directories as part of testing. The program does not daemonize or
install a service. Do not run it as root.

To inspect the source's physical backing without walking its files:

```sh
python3 -B tools/topology.py SOURCE
```

This uses read-only `df`/`diskutil` queries. macOS can label a real device
`VirtualOrPhysical=Unknown`; membership in `diskutil list -plist physical` supplies
additional confirmation. Unknown mappings and RAID are refused. The helper's
output does not configure the queue yet.

## Limits before real deployment

This milestone has one source and one queue, not a shared broker across multiple
mounts or daemon instances. Only duplicate use of the exact same source is locked.
It serializes callbacks, not whole copy jobs. Metadata may therefore run between
chunks of a copy. Priorities, bandwidth/IOPS budgets, directory-walk detection,
handle caps, cancellation, process names and a management UI remain unimplemented.

FUSE-T's NFS adapter caches/transforms requests and cannot provide reliable original
caller PID for this test. Logs use a deterministic file-path hash to distinguish
requests, not process identity; these hashes are not cryptographic anonymization.
Locks and some operations do not enter FUSE. Kernel/drive cache I/O and unrelated
applications accessing the source are outside this queue. The test delay is not
a measured HDD bandwidth control.

Unsupported filesystem semantics include deleting, renaming, creating directories
through the mount, symlinks, ACLs, xattrs, locks, and full timestamp/permission
preservation. This is not yet suitable for rsync metadata fidelity or Finder
workflows. A read-only view is not a forensic guarantee against access-time or
other host filesystem activity. The backend source must not be concurrently
modified outside the broker: external renames/hardlinks can undermine path policy.

The next engineering milestone is one broker owning multiple roots with shared
physical-disk queues, followed by explicit copy reservations and enforced agent
confinement. Read the architecture decision before connecting real storage.
