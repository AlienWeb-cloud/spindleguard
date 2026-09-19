# SpindleGuard — first architecture decision

Research checked 10 September 2026. Scope of this commit: proof of interception
and a single FIFO queue, not the complete storage gateway.

## Decision

Use C and the open-source macFUSE LoopbackFS/libfuse2 handle operations, with the
already-installed FUSE-T 1.2.7 NFS runtime for this Mac's first mount. C avoids
another language binding and keeps callbacks close to the existing example.
Rust offers stronger memory safety for the later broker; Go offers convenient
concurrency, but neither justifies rewriting the working passthrough today.
The runtime is not fully open source. Keep that distinction explicit.

| Candidate / facility | Finding and decision |
| --- | --- |
| [macFUSE](https://github.com/macfuse/macfuse), [LoopbackFS](https://github.com/macfuse/demo) | Reuse open-source example callbacks. Runtime components include closed source. [Current macFUSE supports an FSKit backend](https://github.com/macfuse/macfuse/wiki/Getting-Started) as well as its kernel backend; a kernel extension is no longer the only route. FSKit is a follow-up backend test. |
| [FUSE-T](https://github.com/macos-fuse-t/fuse-t/wiki) | Installed here. NFS adapter can mount without a kernel extension. Locks bypass FUSE callbacks, access callback is unused, and attribute caching differs. Do not claim interception of every syscall or reliable original PID. Keep its listener local; do not expose unauthenticated NFS. |
| [bindfs](https://bindfs.org/docs/bindfs.1.html) | Strong larger alternative: mature directory mirror, permission mapping, read/write rate options. Those controls do not provide a shared spindle queue or whole-job reservations. Reassess as the base when broader filesystem semantics are required. |
| [sandboxfs](https://github.com/bazelbuild/sandboxfs), [author's status](https://jmmv.dev/2025/06/whatever-happened-to-sandboxfs.html) | Useful model for arbitrary virtual views and per-mapping permissions, but abandoned; poor maintenance foundation. |
| [fuse-overlayfs](https://github.com/containers/fuse-overlayfs) | Linux container overlay implementation. Copy-up is different from the requested no-duplicate passthrough and adds unnecessary semantics. |
| [nfsserve](https://github.com/huggingface/nfsserve) | Open-source Rust NFS server alternative. Would require more work on passthrough semantics, handles and macOS behavior. Keep as fallback if runtime licensing is unacceptable. |
| Bind-like mounts / symlinks | bindfs supplies the useful macOS mirror behavior. A path alias alone has no scheduling boundary. |
| [FSEvents](https://developer.apple.com/documentation/coreservices/file_system_events) | Change notifications, useful for index invalidation; cannot delay each read or recursive scan. |
| [Endpoint Security deadlines](https://developer.apple.com/documentation/endpointsecurity/es_message_t/deadline) | Authorization responses have deadlines. This is not an indefinite disk queue and requires a separate entitled integration. Useful later for attribution and bypass controls. |
| [Disk Arbitration](https://developer.apple.com/library/archive/documentation/DriversKernelHardware/Conceptual/DiskArbitrationProgGuide/ManipulatingDisks/ManipulatingDisks.html) | Resolve volume devices and monitor topology. A whole APFS container device is not necessarily a physical spindle. Follow its physical stores and their parent whole devices. |
| [Go token bucket](https://go.dev/wiki/RateLimiting), [Rust governor](https://docs.rs/governor/latest/governor/) | Reuse if selecting those languages later. Bandwidth and request budgets are distinct from concurrency; acquire budgets before dispatch, support cancellation. |
| [BlockingConcurrentQueue](https://github.com/cameron314/concurrentqueue) / pthread conditions / GCD | Existing synchronization suffices. Choose pthread condition variables and monotonically increasing tickets for this small, ordered queue. High-performance lock-free queues offer no material benefit at HDD speeds. |
| [App Sandbox](https://developer.apple.com/library/archive/documentation/Miscellaneous/Reference/EntitlementKeyReference/Chapters/EnablingAppSandbox.html) | Supported application confinement requires packaging/entitlements and inheritance testing. Dedicated unprivileged agent account plus a broker account and source ACLs is the preferred deployment direction. |

## What this prototype guarantees

One daemon, one source tree, one active backing callback. All implemented backing
I/O (including pathname resolution) goes through its FIFO ticket queue. Metadata
waits behind reads. Unimplemented operations do not have passthrough callbacks.
The source is anchored by an open descriptor; component traversal uses openat
and O_NOFOLLOW. Nested devices are refused. Only regular files/directories are
supported. Write permission is an explicit virtual prefix with a component
boundary, and existing hardlinked files cannot be written. Default is read-only.

This deliberately restricted semantic subset is not Finder-complete or a POSIX
conformance claim. Deletion, rename, symlinks, chmod, ACL and extended attribute
mutation are not implemented. Keep the disposable source exclusively managed
during tests: external rename/hardlink changes can invalidate path policies.

## Physical disk routing next

The included read-only topology tool resolves the source mount device through
APFS physical stores to physical whole disks. It refuses unknown/virtual/RAID
mappings rather than pretending a logical device is a spindle. Its result is
observational only; the current single-root queue does not use a global registry.

Identity is not a device name. `bindcheck.assert_bound()` opens a path only
to obtain an fd, then binds on serial / PARTUUID / FS-UUID and the fd's
major:minor, and returns that fd. Permission-shaped checks (exists, read-only,
path allow-list) are not sufficient: names such as `sda1` move. See
[BINDCHECK.md](BINDCHECK.md). Device-shaped `open()` outside `bindcheck/`
fails the control-plane suite.

Production: one broker process owns all roots and a queue per stable physical
media identity. diskN names are session identifiers and can change after eject.
Multiple physical stores require reservations on every backing disk in stable
order, not one queue keyed by the tuple. Detect overlapping sets. Subscribe to
Disk Arbitration, invalidate mappings on remount, and fail closed while unknown.
Reject or explicitly model network storage, disk images, RAID and nested mounts.

## Scheduling next

Request FIFO is not copy-job scheduling: two copies can alternate their read
chunks even though only one callback runs at a time. Introduce explicit job
registration/reservations with bounded leases and cancellation; do not hold a
permit from open to close (one process can deadlock by opening source and target).
Recognize sequential offsets heuristically, label uncertainty, age low-priority
work to prevent starvation. Separate metadata/directory budgets, open-handle
limits and bytes/sec controls. Bound pending work without preventing release or
cancellation callbacks from progressing. Tests must cover scan floods, early
client exit, unmount and cross-disk copies.

The filesystem queues brokered work only. A copy using the original source path,
Spotlight, backups or another mount can still compete. Filesystem and device
caches mean syscall counts are not physical IOPS; write completion is not media
flush. Do not advertise actual disk throughput from simulated delays.

## Bypass protection next

The prototype does not confine Codex or Claude. Before evidence deployment, run
agents without source access under a dedicated account or VM, and expose only
the brokered view. Broker privileges and agent privileges must differ. Test
inherited children, path aliases, symlinks, hardlinks, old file descriptors and
raw device access. Do not grant sudo or inherited source handles. A launch
wrapper alone is not enforcement; sandbox-exec is deprecated (local macOS man
page), and broad host-volume sharing defeats VM isolation. Source ACL/account
changes require a separate deployment step; none were made here.

Keep an index on SSD later. FSEvents marks dirty subtrees; reconcile dropped
notifications. Content grep and hashes need previously indexed content, not
just filenames. Build/rebuild the index through the same disk scheduler.
