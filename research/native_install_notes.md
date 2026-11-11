# FL installation: filesystem plan and offline rehearsal

Do not use the old `creative_flash` writer for this package. That writer is
limited to at most 32 sectors, forbids the first 2 KiB, and assumes no allocation.
A new `/usr/lib/a7fl.so` requires new blocks/inodes and updates to ext2 allocation
metadata. The expanded strings grow by only 200 bytes each, but shifting their
index/body moves approximately 743 KiB of existing bytes. A loader hook written
last cannot make interrupted in-place locale rewrites safe.

The preferred allocation and namespace path is the camera's kernel ext2 driver:
temporary remount writable, complete new files, `fsync`, hardlink original locale
backups, atomic `rename` of each new locale, loader activation last, restore
read-only mount, and cold reboot. No raw ext2 metadata transaction should be used.

## Actual local evidence and remaining live gates

The saved camera mount report
`.lab/native-mounts/1794378957744617000.txt` contains:

```
/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0
```

The exact verified `.lab/creative-icons-belt/a7m3-retro-wardrobe.img` contains:

| Property | Value |
|---|---:|
| Partition image size | 314,572,800 bytes |
| Filesystem blocks | 212,172 |
| Block size | 1,024 bytes |
| Free blocks | 9,567 |
| Free inodes | 52,330 |
| Journal | None |
| Filesystem state | Clean |
| Current `viewUnified2.so` | 10,854,816 bytes / 10,644 allocated blocks |

**Full copy-on-write replacement of `viewUnified2.so` cannot fit.** With the
placeholder module, locale/module staging needs 742 blocks including an 8-block
margin. Adding a complete new view library needs 11,386 blocks; it exceeds free
space by 1,819 blocks, or **1,862,656 bytes**. The live module will change the exact
budget. The filesystem occupies less than the partition, but enlarging ext2 is a
different operation and is not implemented or authorized by this plan.

`native_install_probe.c` is a source-only read-only preflight for root UID,
CAP_SYS_ADMIN, live `/usr` `statfs`, `/proc/mounts`, and block `BLKROGET`. It never
calls mount/remount and never opens `/usr` or the block device for writing. It
creates only a temporary report if separately executed. This particular probe
has not been executed. The parent workflow executed an equivalent read-only
probe and retained
`.lab/native-install-preflight/filesystem-1794381017586636000.bin`: UID/EUID 0,
successful capability query with all effective/permitted bits set, successful
`BLKROGET` with value 0, ext2 type `0xef53`, 1,024-byte blocks, 9,567 free blocks,
52,330 free inodes, and mount flags 4,129. Its `statfs` block total 205,449 excludes
filesystem metadata and therefore differs from the superblock total 212,172.
The exact read-only mount line also matched. This establishes the read-only
capability preflight; no successful writable remount is claimed.

Installation must fail closed if root/capability, block writability, exact mount,
remount success, current preimages, space, or durable writes cannot be verified.
Unsupported or failed directory `fsync` needs explicit treatment, not silent
success. Actual remount availability remains unproven until a deliberately
bounded live check is performed by the parent workflow.

## Implemented filesystem-only installer

`native_install.c` and `native_install_linux.c` implement the guarded standard
kernel filesystem stage. They never patch `viewUnified2.so`, open a block
device writable, activate a loader, or reboot. Preflight verifies the exact
existing view and locales, root/capability, mount, block writability, available
space and absence of all candidate/final/backup names. A fixed-name exclusive
journal `/setting/A7FL.INSTALL` records intent and completion with bundle-bound
hashes and `fsync`; an existing journal blocks another run. There is no automatic
resume after interruption.

The stage creates complete candidates, fsyncs and reopens them for SHA-256
verification, retains original locale hardlinks, publishes locales through
same-directory rename and the new module through a no-overwrite hardlink,
verifies the unchanged view, and restores a verified read-only mount. Detected
failures attempt namespace rollback and read-only remount. Persistent remount
failure is explicitly reported; it is not treated as completion. All retained
backup and journal files must be inspected before a later recovery attempt.

```sh
python3 research/native_install_test.py
PYTHONPATH=research python3 research/native_install_build.py \
  --module /path/to/a7fl.so --module-proof /path/to/reviewed-proof.json
```

The fault suite passed **18,980 checks over 160 injected syscall failures** under
AddressSanitizer and UndefinedBehaviorSanitizer. It also covers short I/O,
persistent remount failure, changed bundle bytes, missing/placeholder module
attestation, a read-only block device and repeat installation. The ARM core
links with `--no-undefined` and no libc dependency. This is syscall-shim and
cross-link evidence, not a physical power-loss or live remount test.

The builder accepts only a real module whose proof says `placeholder: false`,
`ready_for_staging: true`, includes its matching `module_sha256` and nonempty,
current `source_sha256` pins. It revalidates the installer fault proof, original
native string-parser proof, locale proof, exact current preimages and module
entry. It binds these input hashes into the generated payload. A module that
only prepares an interface but lacks the actual platform bootstrap is not ready
for staging and must not receive that attestation. The builder itself never
uploads or executes the payload. Its output installs only the module and two
locales; the separate quiescent loader-activation gate remains mandatory.

The syscall adapter uses Linux ARM flags, which differ from asm-generic:
`O_DIRECTORY=0x4000`, `O_NOFOLLOW=0x8000`, `O_DIRECT=0x10000`, and
`O_LARGEFILE=0x20000`; inherited `O_NONBLOCK=0x800`. These values are defined in
the primary [Linux ARM fcntl header](https://raw.githubusercontent.com/torvalds/linux/v3.10/arch/arm/include/uapi/asm/fcntl.h)
and [generic fcntl header](https://raw.githubusercontent.com/torvalds/linux/v3.10/include/uapi/asm-generic/fcntl.h).

## Rehearsal

```sh
PYTHONPATH=research python3 research/native_install_plan.py
# Or use a real locally built module:
PYTHONPATH=research python3 research/native_install_plan.py --module /path/to/a7fl.so
```

The default module is clearly marked as a placeholder: its entry returns zero
and implements no FL feature. The script accepts only the exact baseline and
source-pinned locale/loader proofs. It uses `debugfs` on a local image copy to
allocate files and create independently checked endpoint states:

1. **Stage:** New module plus complete candidate locales, original locale names
   and contents untouched. `e2fsck -fn` passes; `debugfs dump` independently
   verifies module, original files and candidate files.
2. **Publish locales:** New locale names point to complete new files. Old inode
   contents remain reachable under `.a7fl-zh.orig` and `.a7fl-en.orig`.
   `e2fsck -fn` and independent file exports pass again.
3. **Activate:** Apply only the previously proved three loader sites to the
   existing view file. The local final filesystem passes `e2fsck -fn` and the
   complete view export matches its pinned hash.

This rehearsal passed for the placeholder module. Results are in
`.lab/native-install-plan/manifest.json`. It is explicitly
`flash_ready: false`, `live_writer_implemented: false`; it is **not** compatible
with an existing flash command. `rehearsal.img` is an offline endpoint artifact.
Debugfs commands reproduce final namespace states and are not a power-loss-safe
live command sequence. A live installer must use kernel `link`/`rename`/`fsync`.

## Candidate live transaction, subject to unresolved loader gate

Before any mutation, persist a transaction journal in `/setting` and on the Mac
with baseline identities, file hashes, new file hashes, exact loader before/after
bytes, stage number and recovery actions. Use a fixed journal version/build ID;
reject another unfinished transaction. Revalidate actual available blocks and
inodes. Keep the connection and power stable.

1. Remount the exact `/usr` ext2 mount writable, preserving existing options;
   independently reread mounts. No automatic fallback to raw block writes.
2. Create candidates with `O_CREAT|O_EXCL`; write complete bytes, check every
   write result, `fsync`, reopen and hash. Preserve intended mode/ownership.
   Publish `/usr/lib/a7fl.so` only after its contents and integration are proved.
3. Create a hardlink backup of each original locale, `fsync` its directory, then
   `rename(candidate, original)` and `fsync` again. Each locale includes every
   old resource unchanged, so publishing one language before the other is valid.
   Old mapped inodes remain valid; new opens see the complete new inode.
4. Verify both published locales and the installed module. Stage the two loader
   helper caves, verify them, then publish the four-byte `menu_hook` last. This
   is the unresolved live executable-update gate described below.
5. Check full final file hashes, update journal, flush all writes, remount `/usr`
   read-only and independently confirm it. Cold reboot is required before
   claiming the on-disk integration is running. Verify postboot files and UI.

The view cannot currently be COW replaced. Tiny in-place helper/hook writes avoid
large rewrites but are **not automatically safe in a running executable mapping**:
the current process may retain instruction-cache lines or execute the hook while
it changes. A cold reboot removes stale mappings afterward but does not by itself
prove the transition safe. The parent must establish a quiescent activation path
or another sufficiently verified technique before making this installer live.
No hot-patch/cache safety is claimed by the offline rehearsal.

## Rollback and interruption

- Before the hook is active, old menu code remains the recovery entry point.
  Keep old locale hardlinks and module candidates; never delete a required
  original to make space.
- After activation, restore and verify the original hook first, then restore
  helper caves. Restore locale names from retained backups using the same
  atomic-rename discipline. Cold reboot and verify original behavior.
- Do not unlink a live shared library mapping as a substitute for deactivation.
  Retain module/backup files until the hook is inactive and a cold boot confirms
  rollback. Their small space cost is preferable to premature cleanup.
- Ext2 has no journal. A series of correct kernel operations plus `fsync` reduces
  exposure but does not make the entire multi-file operation atomic. On an
  unexpected disconnect, consult the durable transaction state, reread every
  relevant file, and recover deliberately. Never blindly resume at the last
  requested operation or claim completion from a transport success alone.
