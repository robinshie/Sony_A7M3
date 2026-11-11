# Resident FL integration

The production module supplies an independent **Creative Look** group for the
still-photo menu, with Off/FL, five working LUT controls, three disabled spatial
controls, and an explicit Save action. It uses native Sony setting nodes and the
native process-data manager. The v1 platform profile appends this group to
Camera Settings 1, page 14; it does not install a movie-menu entry.

FL here is the project's experimental approximation, not Sony A7 IV's proprietary
algorithm. Contrast, highlights, shadows, fade and saturation transform the native
1280-byte LUT. Sharpness, sharpness range and clarity remain gray and reject writes.
The original Creative Style entries and their process IDs retain native dispatch.

## Rebuild

```sh
PYTHONPYCACHEPREFIX=/private/tmp/a7m3-python-cache \
python3 research/native_module.py \
  --usr /path/to/nflasha15_unpacked \
  --bundle .lab/native-fl-01 \
  --with-bootstrap
```

This produces the private `.lab/native-module/liba7-fl-module.so` and `proof.json`.
The installer packages that file as `/usr/lib/a7fl.so`. Original firmware excerpts,
camera calibration tables, coordinate codec and generated binary data stay in
ignored `.lab` files. The builder uses `-mno-unaligned-access`; this is required
because bounded preference buffers need not begin at an aligned word address.
Internal function binding prevents another experimental DSO from interposing a
different version of the runtime APIs. The final library has no unresolved imports,
separate RX/RW segments and a non-executable stack.

Without `--with-bootstrap`, the result is an injected-platform integration fixture,
and its proof explicitly refuses staging. With the flag, the actual Linux
bootstrap and fixed-path POSIX store are linked, their guard tests run, and the
source hashes of the bootstrap and dual loader are checked before staging is
allowed. Staging readiness is not a claim that the camera was flashed or tested.

## Lifecycle and saving

The checked dual loader calls `a7_fl_install(view_base, context, mode)`. Mode 1 runs
from the original still-view entry seam and ignores the context argument. Mode 0
runs before SettingMenu construction in the corrected loader and receives the actual `ViewManager`; this
is a different object from the process manager at `view_base + 0xa61c18`.

The bootstrap verifies mappings, the readonly `ILCE-7M3` model property, exact
firmware build, original API byte pins and the expected loader return address. It
prepares the color backend without dereferencing menu objects. Color initialization
recognizes a historic generated table, restores the immutable original, then
applies the last valid saved recipe. It runs once per process; later still-view
entries preserve an active unsaved preview.

At the first MENU event, the bootstrap supplies a strictly checked page profile
and real ViewManager. The module permits menu fields to change at this step while
requiring the backend, storage, base addresses and identity callbacks to remain
identical. It builds a separate native tree, preserves all original scalar process
routes, and inserts the new group after the page's final original entry.

A cold page is still in the original constructor state. The module leaves its
initialization to the later original main-menu root initialization. An already
initialized page is reinitialized using the original four-argument deep-init API,
which updates ancestry and one-based sibling indices. Custom node initialization
restores capability grayout and current value cursors, including original owning
heap clones. Module-owned graph storage remains alive for the process lifetime.

Scalar setters use `a7_fl_control_preview`: they update backup RAM and never write
a preference file. The explicit Save node has process ID `0x7009` and routes through
the original `execProc` action slot, separately from scalar setters `0x7000..0x7008`.
Only that action commits the pending preference. It writes and verifies the next
generation in `/setting/A7FL0.CFG` or `/setting/A7FL1.CFG`; repeated Save with no
change does not write. Merely pausing on a value does not count as confirmation.

The public confirm/cancel/uninstall entry points are separately witness-gated;
the production bootstrap rejects external calls through those paths. An exact
detach can restore original parent arrays and reinitialize stock sibling indices.
If native cloning has changed the array, rollback refuses to guess ownership and
keeps module storage alive for restart/reconciliation.

## Verification and its boundary

The build runs:

- The original backup library wrappers and kernel writer with 421 checks covering
  ABI, readback, rollback, record corruption, preview/commit separation and exact
  historic-candidate recovery.
- Integrated original setting nodes, original manager dispatch for 618 stock IDs,
  the original native action handler and the actual new Save node, against modeled
  transport, kernel and filesystem services.
- A separate cold-boot case with a saved On recipe and a different serialized old
  preview. It verifies color restoration before MENU, first-MENU configuration,
  later original graph initialization and retained mode/value cursors.
- The production bootstrap guard fixture, including wrong caller, model/build,
  mapping, object-profile and initialization cases.

The proof manifest pins the final module, generated private data and source files.
`a7_fl_bootstrap_status()` reports loader stages in memory; `a7_fl_status()` reports
runtime readiness, installation, fault, dirty flag, saved generation, actual mode
and parameters. Neither diagnostic accessor writes a log or storage.

Hardware validation still has to verify native backup RPC readiness at the actual
still-view entry, physical menu navigation and Save, and a cold-power readback.
These tests do not emulate the Sony LCD, sensor or entire camera operating system.
See `native_fl_runtime.md` for the exact calibration recovery and persistence
contracts, including why avoiding explicit Backup sync calls does not intercept
unrelated Sony global saves.
