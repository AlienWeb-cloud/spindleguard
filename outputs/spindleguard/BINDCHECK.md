# Identity binding (`bindcheck`)

Permission-shaped checks are not identity. A job hardcoded to `/dev/sda1`
survived every "is this path allowed, and is it read-only?" check after
`sda`/`sdb` swapped on reboot, then ran against the wrong disk.

`assert_bound()` is the only supported way to obtain a device descriptor.
It opens first, `fstat`s the fd, resolves serial / PARTUUID / FS-UUID
independently, compares major:minor, re-asserts read-only **on that fd**,
and returns a `BoundDevice` that holds the fd. It does not return a path.
A path lets the caller re-open; that is a race, not a binding.

## Mandatory by construction

`tests/test_bindcheck_structure.py` walks the tree. The suite fails if:

- any `os.open` / `os.openat` / `posix.open` exists outside `bindcheck/`
- any builtin `open()` / `Path.open()` uses a device-shaped path
  (`/dev/sd*`, `/dev/nvme*`, `/dev/disk*`, `/dev/rdisk*`, …)
- a C translation unit both calls `open`/`openat`/`fopen` and contains a
  device-shaped string literal

`bindcheck/` is the allowlisted implementation site. Tests use an in-memory
`FakeResolver`; they do not open host `/dev` or `/Volumes`.

Planted search token in `bindcheck/scan.py`: `STRUCTURAL_CANARY_assert_bound`.

## Refusals (message-pinned)

| Condition | Message |
| --- | --- |
| No manifest / empty mapping | `no identity manifest` |
| Missing serial, PARTUUID, or FS-UUID | `unresolvable identity field: {field}` |
| fd major:minor ≠ independently resolved node | `identity mismatch: major:minor` |
| Resolved field ≠ manifest | `identity mismatch: {field}` |
| Zero or two-plus nodes share the serial | `ambiguous serial: multiple devices share {serial}` |
| Verified fd is not read-only | `device is not read-only` |

`make test-bindcheck` deletes each of those checks in turn (in-process
rewrite, then restore). The named test must go red. Files are restored
sha256-identical. That mutation run is the proof that a refusal test is
not passing on an earlier check.

## Fingerprint skip (always reported)

Sampling is off unless `allow_fingerprint` is true. `media_class=failing`
skips even then. USB bridges that enumerate as one node with one serial
do **not** currently trip the ambiguity refusal; `assert_bound` still
succeeds, and the CLI prints that fingerprint was skipped and why.

## Manifest rotation

`bindcheck.manifest.rotate_manifest` writes a **new** generation file and
an append-only audit line. It refuses to overwrite. `assert_bound` has no
`update=True` switch. Editing a manifest by hand remains possible on disk;
this API is the logged path the job should use instead.

## What this does not verify

No real block device (`BLKROGET`, live `st_rdev`, sysfs, `diskutil`).
No host `/dev` or `/Volumes` access. No `make test` mount run. Platform
resolvers that open real device nodes are out of this change; they must
live in `bindcheck/` when they land.

## Commands

From `outputs/spindleguard/`:

```
SG_REQUIRE_FULL=1 make test-control
make test-bindcheck
python3 -m bindcheck scan --root .
python3 -m bindcheck bind --manifest FILE --path PATH --fixture FILE
python3 -m bindcheck rotate-manifest --old FILE --observed FILE --reason TEXT --out FILE --audit FILE --dry-run
```

`SG_REQUIRE_FULL=1` turns skipped tests into failures.
