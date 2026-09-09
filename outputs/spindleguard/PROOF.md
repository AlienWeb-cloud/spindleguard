# Recorded proof — 10 September 2026

Command: `make -C outputs/spindleguard test` from the task repository.

Result: `ALL MOUNT TESTS PASSED`.

- Five physical topology fixture tests: `Ran 5 tests ... OK`.
- Real FUSE-T mount established; directory browsing succeeded.
- Two independent client processes read through the virtual filesystem.
- The first read consumed 2 MiB; bytes matched the source exactly.
- First-file read ticket **92** held the queue when second-file request **98** queued.
- The second-file metadata request waited **925.935 ms**.
- File creation/write under `/Workspace` reached the backing directory.
- Root writes, prefix-boundary escapes, symlink access and hardlink writes were refused.
- Protected source bytes stayed unchanged; the queue remained usable after errors.
- A separate mount without a write prefix refused writes inside `/Workspace` too.
- All 285 backing callbacks in the read/write run completed in FIFO order with no overlap.
- Both test mounts were unmounted; no active request remained.

Machine: Apple Silicon, Darwin 25.5.0, installed FUSE-T 1.2.7.
The source was disposable test data on the internal SSD. Artificial read delays
make queueing visible; these are not physical HDD throughput measurements.

[Machine-readable queue evidence](queue-proof.json) records monotonic timestamps
and file tags for both requests. All timestamps refer to this one broker run.
Full logs and fixtures are retained in the repository's work directory under
`proof-1788967743921782000`. No test files were deleted.

Read-only topology command: `python3 -B outputs/spindleguard/tools/topology.py .`
resolved `/dev/disk3s9` → `disk0`, classified SSD. This is observation, not a
multi-mount scheduling demonstration. No mechanical drive contents were read.

## What remains unproven

Evidence-drive safety, cross-mount spindle sharing, full filesystem semantics,
whole-copy reservations, agent bypass prevention, cancellation, bounded scan
pressure and real HDD performance. See the architecture and README for scope.
