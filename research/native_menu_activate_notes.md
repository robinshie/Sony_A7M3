# Native loader activation: staged files, private code pages, then VFS patches

This helper activates only the already-tested loader in `viewUnified2.so`.
It does not install the module or locales, change LUTs, format a partition,
write a raw device, stop threads, or reboot. The module and both locales must
already match the exact hashes in the package manifest. The view file remains
the same inode; only four attested byte ranges are written through the kernel
filesystem. The existing RW edits outside those ranges remain byte-identical.

## Build and evidence

Run `python3 research/native_menu_activate_test.py`. It builds all five ARM
helpers and boots Linux under QEMU with the original Sony userspace loader.
The exact production core is used in the fixture. The fixture uses actual
private file mappings, `mprotect`, procfs `maps` / `smaps` / `pagemap`, and VFS
file writes; only the mount-state facade and specific injected failures are
mocked. It passes 184 checks including all four partial-write positions,
fsync failure, a failed shadow check, transient RX/RO restoration failures,
other-process and malformed-map refusal, before/after cold-boot recovery,
and rejection of foreign changed bytes. A real procfs regression confirms that
`/proc/mounts` is a final symlink and cannot be opened with `O_NOFOLLOW`; the
helper opens the final regular proc file `/proc/self/mounts` instead.

The fixture establishes Linux/ARM behavior, not a camera boot result. A live
read-only preflight and the helper's live per-page checks remain necessary.
Do not infer that the original firmware or LCD was emulated by this test.

Build outputs are private under `.lab/native-menu-activate/`. Require the
`proof.json` manifest hash, source hashes, and selected payload hash to agree
before execution. The bundle hashes complete old/new view files, exact staged
module/locales, all four before/after ranges, and three complete old code pages.

## Runtime sequence

1. Run only while the original camera UI is closed in the existing maintenance
   session. Do not launch a second process that maps `viewUnified2.so` during
   activation. The helper checks all numeric `/proc` PIDs twice and refuses
   another mapping by both path and device/inode identity. This is a bounded
   observation, not a kernel mechanism preventing future process creation.
2. `preflight.so` is read-only apart from its report file. It verifies root,
   the exact RO `/usr` mount, self RX mappings, absence of other mappings,
   complete old view hash, complete staged-file hashes, and three old mapped
   page images. It does not call `mprotect` or remount/write the view file.
3. `activate.so` repeats these checks. It creates an exclusive, fsynced
   `/setting/A7FL.ACTIVATE` journal and fsyncs its directory. Each target page
   is temporarily RWX, receives one volatile write of its existing first byte,
   and is checked as an isolated 4096-byte VMA with exactly 4 kB Anonymous and
   4 kB Private_Dirty. RX is restored even if verification fails. No instruction
   byte changes in the current process. All three full page images must match.
4. Only after all three page checks pass, remount `/usr` RW and open the
   existing view file without truncation. Write helper cave A (44 bytes),
   helper cave B (80 bytes), MENU branch (4 bytes), then boot branch (4 bytes).
   Every range has an intent record, preimage check, fsync, and readback.
   Current mapped pages are checked throughout. Verify the complete target
   file hash, close it, remount RO, and fsync the final journal record.
5. Current execution still sees the old instructions on its anonymous pages.
   The new loader becomes reachable after a cold boot maps the updated file.
   Keep module/locales installed throughout. Their replacement does not imply
   that already-open locale mappings have been reloaded in the current process.

Target pages are file offsets `0x188000`, `0x20d000`, and `0x5b9000`.
Target ranges, in activation order, are `0x5b9a7c+44`, `0x5b9b1c+80`,
`0x20d068+4`, and `0x188aec+4`. Both branches are aligned 32-bit Thumb-2
instructions. Atomic live instruction replacement is not assumed: the live
process has private unchanged page copies before any underlying file write.

## Failure and recovery

A failed range write triggers reverse-order restoration and whole old-file
hash verification. RX restoration and `/usr` RO restoration have three bounded
attempts. A permanent kernel I/O/protection error is reported; software cannot
guarantee restoration when the kernel permanently refuses the needed call.
No automatic reboot occurs. Inspect the report and read back the whole view.

- `recover.so` is independent pre-boot recovery. It requires all three mapped
  pages still equal the old image. File bytes outside the four ranges must
  normalize to the full old hash. Every byte inside the four ranges must equal
  its attested old or new value, allowing an interrupted short write. It
  restores branches first, then caves, verifies the full old file, and returns
  `/usr` to RO. Journal: `/setting/A7FL.ACTIVATE.RECOVER`.
- `deactivate.so` is rollback after the new loader has booted. It requires the
  complete new file and all three new mapped pages. It privately shadows those
  new pages, restores the old file in reverse order, and leaves current process
  instructions unchanged until the next cold boot. Journal:
  `/setting/A7FL.DEACTIVATE`.
- `deactivate-recover.so` repairs an interrupted post-boot rollback. It requires
  new mapped pages and the same strictly attested mixed-file condition as
  `recover.so`. Journal: `/setting/A7FL.DEACTIVATE.RECOVER`.

These helpers intentionally retain module/locales and do not alter LUTs or
preferences. After a new-loader boot, restoring camera settings is a separate
parent-controlled step before removing the module. Existing journals are not
silently reused or deleted. Preserve and inspect them, verify the file state,
and explicitly archive/remove a completed journal before a deliberate retry.

## Report ABI

The constructor creates `/tmp/jiritsu/a7activate.bin` exclusively; remove or
archive the previous report before a new invocation. The 80-byte LE report is:

| Offset | Field |
|---:|---|
| 0 | Magic `0x41374e41` |
| 4 | Version 1 |
| 8 | Phase |
| 12 | PID |
| 16 | View library base |
| 20 | Other process mappings found |
| 24 | COW page mask (7 means all three) |
| 28 | Attempted file-range mask (15 means all four) |
| 32 | Signed status (0 success) |
| 36 | First raw negative syscall result, if any |
| 40 | Automatic rollback verified |
| 44 | `/usr` RO confirmed |
| 48 | Bundle SHA-256 (32 bytes) |

Read-only success is status 0, phase 3, masks 0, other mappings 0, RO 1.
Write/recovery success is status 0, phase 100, COW 7, writes 15, RO 1.
A nonzero first syscall error can coexist with success only when a bounded
retry succeeded; inspect that event. Status -4 means RO restoration failed;
-5 means RX restoration failed. Treat either as unresolved.

## Kernel compatibility

The camera's module vermagic identifies Linux 3.0.27. In upstream Linux 3.0,
pagemap bit 61 is reserved; it must not be used as the later file/anonymous bit.
This helper checks only present/not-swapped bits there. COW ownership is proven
by the isolated VMA's Anonymous/Private_Dirty counters, whose Linux 3.0 source
counts `PageAnon` pages and exclusive dirty pages respectively. Sources:

- [Linux 3.0 procfs page accounting and pagemap](https://raw.githubusercontent.com/torvalds/linux/v3.0/fs/proc/task_mmu.c)
- [Linux 3.0 ARM open flags](https://raw.githubusercontent.com/torvalds/linux/v3.0/arch/arm/include/asm/fcntl.h)
- [Linux mmap semantics](https://man7.org/linux/man-pages/man2/mmap.2.html)
- [Linux mprotect semantics](https://man7.org/linux/man-pages/man2/mprotect.2.html)

## Reusable host CLI

`python3 -m camera.native_activate --offline` validates the entire activation,
staging, module, native-resource and loader proof chain without importing USB
libraries. `python3 -m camera.native_activate` runs read-only preflight. Add
`--direct` for a currently enumerated maintenance device; otherwise it uses the
existing UTM handoff. Each operation creates a fresh private evidence directory
with exclusively created, fsynced files and directory entries.

`python3 -m camera.native_activate activate --write-device` repeats native
preflight in that same maintenance connection before writing. It verifies the
model/build, refuses an existing activation journal, durably records intent,
then checks the native report, journal and complete 10.85 MB view readback.
The returned process/base/bundle must match its same-session preflight.
`recover`, `deactivate`, and `deactivate-recover` each require their own explicit
`--write-device` and refuse an existing journal for that exact transaction.
Nothing resumes automatically; transport failure preserves evidence and exits.

`python3 research/native_menu_activate_host_test.py` passes 17 offline mocked
transport tests covering authorization, preflight ordering, foreign-state
refusal, process identity, whole-file readback, failure evidence, no automatic
retry/recovery, and distinct pre/post-boot recovery. Its proof is
`.lab/native-menu-activate/host-proof.json`. The CLI has not itself been run
against a camera by the authoring sub-agent.
