# SpindleGuard

**Give your drives room to breathe.**

An experimental macOS filesystem broker exploring how to protect physical
storage from uncontrolled AI-agent I/O. Its first working prototype mounts a
disposable source directory and serializes supported backing operations through
a single FIFO queue.

[Project website](https://alienweb-cloud.github.io/spindleguard/) ·
[Installation guide](outputs/spindleguard/README.md) ·
[Architecture and research](outputs/spindleguard/ARCHITECTURE.md) ·
[Recorded proof](outputs/spindleguard/PROOF.md)

## The first proof

A real FUSE-T mount served two independent client processes. A second-file
metadata request waited **925.935 ms** behind first-file reads. The test injected
150 ms delays into read callbacks to make queueing observable; this is not a
physical HDD benchmark. Reads, explicitly permitted writes, read-only defaults,
policy boundaries, FIFO completion and clean unmounts passed.

## Try it

On a Mac with Apple's Command Line Tools and Python 3:

```sh
git clone https://github.com/AlienWeb-cloud/spindleguard.git
cd spindleguard
./sg setup
./sg verify --quick
open outputs/spindleguard/SpindleGuard.app
```

`./sg setup` builds the native app when `swiftc` is present. It compiles the
C broker only after FUSE-T is installed. FUSE-T is never installed unless you
confirm with `./sg setup --install-fuse --yes` (or the Setup pane's confirm
dialog). Real mount proof (`make test`) still needs FUSE-T and disposable
data on internal storage.

Agent-safe checks (no mounts, no host `/dev` or `/Volumes`):

```sh
SG_REQUIRE_FULL=1 make test-control
make test-bindcheck
```

## Scope

Working: one source tree, one queue, real file reads and permitted writes,
structured logs, a separate read-only physical-device lookup tool,
`bindcheck.assert_bound()` so a device fd is bound by identity (serial /
PARTUUID / FS-UUID) rather than by a path that can move, and a native macOS
SwiftUI app (`./sg setup` / `make app`) that can drive setup, verify, bind,
topology, and the broker from the UI. The control-plane suite fails if a
device-shaped `open()` exists outside `bindcheck/`.

Not yet implemented: shared queues across mounts, whole-copy reservations,
agent bypass prevention, scan and bandwidth budgets, or the index/cache layer.
The prototype refuses `/Volumes` paths and supports a restricted filesystem
subset. **It does not yet protect evidence drives or confine Claude/Codex.**

## Repository layout

- `outputs/spindleguard/`: prototype source, tests and engineering documentation.
- `outputs/spindleguard/bindcheck/`: identity-binding layer; see
  [BINDCHECK.md](outputs/spindleguard/BINDCHECK.md).
- `outputs/spindleguard/macos/`: native SwiftUI app sources; see
  [DESKTOP-APP.md](outputs/spindleguard/DESKTOP-APP.md).
- `docs/`: static marketing website, served by GitHub Pages; no build dependencies.
- `work/`: ignored local scratch space and disposable fixtures.

The website queue animation is an illustration and never accesses a drive.

## Contribute

Reproduce the test, discuss a bounded next milestone in an issue, or submit a
focused change with its validation. Keep changes test-only until disk routing
and agent confinement have been independently verified. Do not include private
paths, real evidence, credentials or raw production logs in issues.

## License

Project code: GPL-2.0-or-later. See [LICENSE](LICENSE) and
[upstream provenance](outputs/spindleguard/PROVENANCE.md). FUSE-T is a separate
runtime with its own license; not every runtime component is open source.
