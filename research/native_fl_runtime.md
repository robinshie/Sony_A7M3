# Native FL runtime: API proof and integration contract

The portable runtime switches the experimentally verified native LUT property
`0x00030004` between the camera's immutable original and a generated FL candidate.
It does not supply an install hook, a filesystem driver, or Sony's FL algorithm.
The core and adapter have been executed in offline ARM QEMU with original Sony
4.04 library wrappers and the original fixed-size kernel write body. Live camera
startup, menu scheduling, and durable filesystem I/O remain integration checks.

## Files and build

- `payloads/a7-fl-runtime.{c,h}`: guarded read/write/readback, candidate replacement,
  original-table rollback, and a nonblocking reentrancy guard.
- `payloads/a7-fl-runtime-prefs.{c,h}`: portable, versioned 128-byte preference
  records and selection between two independent slots.
- `payloads/a7-fl-runtime-control.{c,h}`: a native-adjust callback using the five
  scalar controls in `a7-fl-color.h`, RAM-only preview, explicit commit/cancel,
  and an injected durable record writer.
- `payloads/a7-fl-runtime-recovery.{c,h}`: exact recognition of historical
  generated candidates and guarded original-baseline recovery.
- `research/native_fl_runtime.py`: reproducible private fixture builder.
- `research/native_fl_runtime_harness.c`: ABI, fault, record, and adapter tests.

Run from the repository root, using privately obtained firmware and LUT inputs:

```sh
PYTHONPYCACHEPREFIX=/private/tmp/a7m3-python-cache \
python3 research/native_fl_runtime.py \
  --usr /path/to/nflasha15_unpacked \
  --bundle .lab/native-fl-01
```

The bundle needs `00030004.bin` through `00030007.bin`, `candidate.bin`, and `codec.bin` (258 bytes of
little-endian expansion words followed by 513 compression bytes). The script
creates `.lab/native-fl-runtime/proof.json`, `runtime-test.elf`, QEMU output, and
`liba7-fl-runtime.so`. It performs no USB or camera I/O. The library has no imported
undefined symbols; API and storage functions are explicitly injected by its owner.
It must not be installed merely because the offline fixture succeeds.

## Original 4.04 API and evidence

The following offsets are Thumb function addresses in `libbackup.so`; the low bit
is part of a callable address. Supply relocated addresses, not raw offsets.

| Function | Address | Contract |
| --- | ---: | --- |
| `Backup_get_datasize(id)` | `0x1175` | Returns the property size, 1280 here |
| `Backup_get_attribute(id)` | `0x11d5` | Returns attributes, exactly 8 here |
| `Backup_read(id, output)` | `0x1205` | Returns the number of bytes read |
| `Backup_write(subsystem, id, input)` | `0x1359` | Three arguments; returns bytes written |
| `Backup_sync_subsystem(subsystem)` | `0x14f1` | Separate save request, unused by runtime |
| `Backup_sync_all()` | `0x151d` | Separate global save request, unused by runtime |

For this LUT, the actual write call is `Backup_write(3, 0x30004, table)`. Success
is **1280**, not zero. The wrappers call `backup_sync_msg` through PLT `0xda8`,
with queue `0x3e014d`; opcodes are 0 (size), 2 (attribute), 3 (read), 8 (write),
14 (save subsystem), and 15 (save all). Save wrappers do not load the result slot
after their call, so their apparent return value is not evidence of durable save.

The pinned input hashes are:

```text
libbackup.so b6420f8f7cacade524e1ba7c5b0d8b06691c22ed793dca084fdf1c1d9ae092f3
backup.ko   2d26bbdfdf06c53b5ce4caac438484bad8e1f4205cd9cdbab71531115790167e
```

`backup.ko` has an ARM entry at `.text+0x167c` calling the fixed-size writer
`0x5ec..0x888`. Its original instructions establish these behaviors:

- `0x610`: subsystem must equal `id >> 16`, otherwise return −4.
- `0x650..0x654`: acquire the subsystem's `rt_down_write` lock.
- `0x66c`: enforce the read-only attribute for the ordinary runtime context.
- `0x7cc`: determine the fixed size; variable-length entries use a different API.
- `0x80c`/`0x838`: copy user/kernel bytes into the property storage.
- `0x848`: release the subsystem lock.
- `0x85c..0x870`: attribute bit 8 triggers the shared callback after releasing it.
- `0x874`: return the byte count.

The fixture executes those instructions, applying their original ELF relocation
types to modeled data access, copy, lock, and notification services. Transport and
kernel services are modeled; the wrapper and writer instruction sequences are
original. The proof manifest records all excerpt hashes and relocation targets.
The original maintenance writer at `0x6b84..0x6b94` independently confirms
`(id >> 16, id, data, length)` for the variable-size API.

## Core safety contract

Zero-initialize a persistent `a7_fl_context`, then call `a7_fl_init` only when the
native backup service is ready. Initialization checks both table CRCs, native
signed code range −64..63 for the 1215 nodes, the unchanged 65-byte tail, exact
size/attributes, and an exact original-or-current-candidate live preimage. It
copies both tables and does not write. Keep the original file immutable and bind
it to the camera identity, firmware build, and SHA-256 in the installer.

`a7_fl_set` and `a7_fl_replace_candidate` require an exact recognized preimage,
then perform a native write and complete readback. An acknowledgement alone does
not commit state. Failure attempts to restore the complete original table and
reads it again; failure of that recovery is explicit. Repeated values do not
write. Replacing a candidate while Off only updates the owned candidate buffer.

The runtime uses an atomic try-lock, so recursive callbacks reject with Busy
instead of waiting on themselves. This protects this context, not other Sony
threads or processes. The native property API has no exposed compare-and-swap;
a foreign writer between check and write is not excluded by this local lock.
The runtime must run in a context permitted to make synchronous backup calls.
Its stack use, load/init ordering, and concurrent native events need integration
validation, beyond the bare-metal fixture.

## Preferences and native control callback

The root integrator owns `/setting/A7FL0.CFG` and `/setting/A7FL1.CFG` after checking
these names do not collide. `/setting` was observed to be a writable, synchronous
VFAT mount; that observation does not prove crash behavior of the actual driver.
The two records must occupy independent files; never overwrite the only valid
record. A store callback returns zero only after a complete write, durable sync,
close, reopen, and exact 128-byte readback of the inactive slot. Readback failure
must remain an error even if a write appeared successful.

| Byte offset | Content |
| ---: | --- |
| 0 | Eight bytes `A7FLP001` |
| 8 | Record length, little-endian u32 = 128 |
| 12 | Nonzero generation u32 |
| 16 | Schema u32 = 1 |
| 20 | Enabled u32 = 0 or 1 |
| 24 | Eight little-endian signed i32 control values |
| 56 | Original table SHA-256, 32 binary bytes |
| 88 | Build identity, exactly 24 bytes including padding |
| 112 | CRC32 of the regenerated candidate, u32 |
| 116, 120 | Reserved zero words |
| 124 | CRC32 of bytes 0..123 |

Control order is contrast, highlights, shadows, fade, saturation, sharpness,
sharpness range, clarity. The last three are stored for schema continuity but are
disabled in the callback. Sharpness is not simulated using a color LUT. Candidate
CRC must match regeneration from the same immutable base FL and coordinate codec;
the stored CRC alone does not authenticate a LUT. The original SHA/build binding
prevents accepting another package's records; CRC detects accidental corruption.

`a7_fl_preference_choose` selects the highest valid generation, ignores a torn
other slot, and rejects conflicting valid records at the same generation. Missing
or invalid records do not authorize replacing unknown pre-existing files.
Generation wrap is forbidden; the callback reserves one extra generation for a
recovery-Off record.

After the installer has reconciled boot state, initialize `a7_fl_control` with
the core, immutable base FL and codec pointers, current preference, and storage
callback. These pointers and both contexts must outlive the menu. Initialization
verifies that the generated candidate, current state, and preference match.

`a7_fl_control_apply(void *, unsigned field, int value)` is compatible with
`native_adjust_write`: **1 means accepted and 0 means rejected**, unlike the core's
zero-success convention. Fields 0..4 generate scalar LUT changes, field 8 selects
Off/FL, and fields 5..7 reject. Its transaction is:

1. Check known live state and generate a complete candidate.
2. Store the next complete desired record in the inactive slot, durably.
3. Replace/apply the native LUT and verify the readback.
4. Only return accepted after those steps, allowing the caller to commit UI state.

If application fails, the core restores original RAM where possible. The adapter
records a newer Off preference with the prior parameters and faults itself. If
that recovery record cannot be persisted, it exposes a separate fatal storage
error. The caller must refresh its cached mode from the core and disable the
feature on fault; leaving the previous On label would be misleading. The adapter
must be rebound after explicit reconciliation before accepting further changes.

That combined `apply` callback is for a proven confirmation-only path. For a
native setter that can run during highlighting, use the separate APIs:

- `a7_fl_control_preview(ctx, field, value)` returns 1/0 like the native callback,
  updates backup RAM and current `preference`, sets `dirty`, and never invokes the
  storage callback. The last durable record is retained in `committed`.
- `a7_fl_control_commit(ctx)` returns zero only after the dirty preference is
  durably stored as the next generation. It performs no backup write. Repeated
  confirmation without a change does not write. Failed storage leaves the preview
  dirty: keep the dialog open or cancel; do not report that it was saved.
- `a7_fl_control_cancel(ctx)` restores the committed table/mode in RAM without
  filesystem writes. It returns zero on success. A faulted adapter requires
  explicit reconciliation, rather than silently resuming previews.

Connect commit and cancel only to observed native confirmation/cancellation
events. An arbitrary native `setValueToModel` call is not proof of confirmation.
The offline harness verifies that 19 wheel steps cause zero storage calls and
one explicit confirmation causes exactly one. This implementation does not
silently debounce durable records or infer confirmation from an idle timer.

## Persistence boundary: no claim of autosave interception

The core never calls `Backup_sync_*`. Nevertheless an unrelated native global save
or shutdown can serialize the modified backup RAM. `Backup_sync_subsystem` at
`backup.ko+0x1a3c..0x1bd8` copies all properties in that subsystem into a loaded
backup file and calls `backupfile_save_file`. Avoiding an explicit save here does
not make the modified calibration RAM immune to later persistence.

Two preference slots alone cannot identify every historic saved candidate. For
example, a global save at generation 2 followed by settings 3..10 and sudden power
loss can leave generation-2 LUT bytes on disk while only records 9 and 10 remain.
The basic switch core fails closed on that unrecognized preimage.

The recovery module addresses this specific gap without overwriting arbitrary
calibration. `a7_fl_recognize` tests membership in the exact finite candidate
family of this package. Chroma depends independently on 19 saturation values;
tone depends on 19 × 19 × 19 × 10 = 68,590 combinations of contrast, highlights,
shadows and fade. It rejects tone candidates early, then regenerates a complete
table using the current authoritative `a7_fl_adjust_lut` implementation and
requires an exact 1280-byte match. Shape, bounds, CRC, or approximate color
similarity alone are never sufficient. No signature is hidden in calibration
nodes or the 65-byte tail.

`a7_fl_restore_baseline` may run during startup reconciliation before UI callbacks
are installed. Its caller must provide an identity guard that verifies the actual
camera and firmware build against the immutable package. It validates original
and base-FL CRCs, exact original LUT1..3, property sizes/attributes, and the original
tail. An original LUT0 is left alone; a non-original LUT0 must be an exact member
of the generated family. It rechecks identity, LUT1..3 and the current preimage
immediately before restoring original LUT0. It requires exact readback and permits
at most one retry of restoration. Other LUTs are never written.

This permits recovery of transient previews and older generated candidates even
when their recipes are absent from both current preference slots. An arbitrary
or altered calibration table is refused, leaving the feature disabled for manual
review. The caller must still serialize startup recovery and exclude another
calibration writer; the native API has no compare-and-swap primitive. The module
does not authenticate camera identity by itself or intercept Sony global saves.

## Offline verification result

The current fixture passes 421 checks, including native return values and callback
lock order; known/foreign preimages; failed/partial/accepted-but-error writes;
rollback failure; candidate replacement; all 128 single-byte corruptions and 128
truncations of a record; generation choice and collision handling; five-control
generation; persistence-before-application order; disabled controls; durable-store
failure; recovery-store failure; reentrancy; generation exhaustion; preview,
confirmation and cancellation separation; 32 extreme and 32 varied historical
tables; exact regeneration; foreign calibration rejection; camera/build-guard
failure; LUT1..3 changes; changing preimages; and bounded baseline-restoration
retry. It uses the private bundle's real native coordinate codec.

This evidence supports the stated offline API and transaction behavior. It is not
a camera flash, a boot test, a measurement of Sony FL color accuracy, or a proof
of native menu ownership and scheduler behavior.
