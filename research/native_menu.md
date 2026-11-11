# Native Creative Look menu integration (4.04)

These components are native ARM integration work, not the separate QEMU LCD mockup.
They do not operate USB or flash the camera. The generated proof files deliberately
set `camera_integration`, `native_display_rendered`, and `flash_ready` to false.

## Binding points

`viewUnified2.so` uses CautionConfig setting-node trees for its main menu. The
original Creative Style root is Caution VA `0xa75ff4`; its generic base vtable
address point is `0x918ec8`. A node occupies 40 bytes on ARM. Its child pointer,
count, and property-container pointer are at `+4`, `+8`, and `+12` respectively.
The property container stores a pointer to 12-byte `{key,type,value}` records and
an **inclusive last index**. Key `0` is title resource, `0xc` execution kind,
`0xe` process ID; leaves use `0xf` and `0x10` for values. The independent
`native_adjust` component supplies the complete root, mode selector and controls.

`a7_menu_attach` inserts that root immediately after a verified anchor
pointer in a parent list. The live A7M3 profile appends it to still page 14
(after Priority on Registered Face), or inserts it after Creative Style on movie
page 2; it does not replace or nest inside Creative Style. It preserves every old entry and the old array, checks
capacity and duplicates, and supports guarded rollback. The caller supplies a
persistent child array. It must use the latest `native_adjust` lifetime-safe
vtables; passing embedded nodes to the stock owning destructor is invalid.
One graph is required per live parent, or a separately proven clone strategy.

The process manager singleton is at view VA `0xa61c18`, and its vtable address
point is `0x87f720`. The scalar getter is virtual offset `0xc` (original code
`0x2f2a2b`), setter offset `0x44` (`0x2f2845`). The adapter clones the vtable
including RTTI metadata and replaces these two scalar slots. An optional explicit-action binding separately
intercepts `execProc` at virtual offset `0x54` for ID `0x7009`. It routes IDs
`0x7000..0x7008` to caller callbacks. All original IDs keep original dispatch;
other original manager methods reject IDs above `0x269`, so custom IDs cannot
accidentally select a real camera process. Bind only while the UI is idle.

## Early loader

The original exported `ViewGlobalMenuToInstance` factory at `0x20d057` allocates
the main MENU view, then calls its constructor at `0x20d068`. The bounded loader
replaces that one call, opens `/usr/lib/a7fl.so`, resolves
`a7_fl_install(uintptr_t view_base, void *view_manager)`, and calls it. Success,
missing module, missing symbol, and installer failure all preserve the original
constructor arguments and tail-call `0x20cda1` exactly once.

The loader occupies only verified NOP space from the deployed RW image:
`0x5b9a7c` (capacity 52 bytes) and `0x5b9b1c` (capacity 82 bytes). Two initial NOP
bytes in the second run are retained to align Thumb literal pools. The builder
pins the complete input SHA and verifies every byte outside the three patch
ranges remains identical. Successful module loads stay referenced because their
callbacks must remain resident. The module installer must be idempotent.

## Offline verification and live witness

```
python3 research/native_menu.py --usr /path/to/nflasha15_unpacked
python3 research/native_menu_loader.py --usr /path/to/nflasha15_unpacked
python3 research/native_menu_probe.py
python3 research/native_menu_probe.py --report /path/to/a7flnodes.bin
```

The first test executes the original native process lookup, scalar get/set and
invalid-value code against the real 618-entry dispatch table, with only the
process-element factory modeled. It checks all 618 original IDs, nine custom
IDs, failed-write state, sibling placement and rollback. The second executes the
original main-menu factory with the new loader and modeled dynamic-loader calls.
Neither test renders a native LCD or proves live page capacity/navigation.

The 5.1 KB read-only probe inspects mapped live memory, records matching generic
BSS parents, child properties, and ancestor page counts, and writes the fixed 55,620-byte version-2 report
`/tmp/jiritsu/a7flnodes.bin`. It performs no node, callback, backup, or firmware
mutation. Live parent/layout evidence and a combined module test are required
before treating the separate components as a completed camera feature.

## Confirmed live profile and cold initialization

`native_menu_profile.py` derives the insertion profile from a version-2 report
and original ELF relocations. The successful local report had 39 candidate
parents but only two active depth-3 main-menu pages. Modifying every matching
parent would be incorrect.

- Still page 14: view `0xa6dfa4`, three original rows, children `0x8f3214`,
  properties `0xa725a0`, category `0xa69c88`. Native rows are Anti-Flicker Shoot,
  Face Registration, and Priority on Registered Face. Append the fourth row.
- Movie page 2: view `0xa6c248`, four live rows, children `0xa6b5e0`,
  properties `0xa72538`, category `0xa6c400`. Insert after original CS (index 2).

Cold static constructors differ from this live profile. Still page 14 keeps its
three original children but all six trailing state/ancestry fields are zero.
Movie page 2 starts with zero children and pointer `0xa64e80`, then stock runtime
repackages its rows. Do not insert into that empty cold movie array.
The GlobalMenu constructor does not initialize the graph. SettingMenu later
calls its selected root's public initializer at view `0x21d0a0`. Validated cold
still staging should let that original initializer establish ancestry; warm
insertion needs explicit original parent deep initialization and cursor restore.

## Explicit save and optional boot loader

Native scalar setters are not proven to mean final confirmation. The separate
Save row uses existing resource `0x0204eaab` (保存 / Save), execution kind 4 and
process `0x7009`. `a7_menu_bind_action` intercepts only that ID in `execProc`.
`native_menu_action.py` executes original ViewSettingMenu handler
`0x217c7c..0x217d52` in QEMU and verifies selected-node dispatch, mode guards,
stock delegation, and error fallback. Physical key-to-action routing remains a
live UI validation item; the fixture does not claim to reproduce it.

The optional `native_menu_boot_loader.py` produces a separate artifact, leaving
the MENU-only build intact. It additionally replaces the still-view UserEntry
prologue at `0x188aec` with **B.W**, preserving the application's original LR.
A dedicated trampoline saves arguments/LR before any dynamic-loader call, then
reproduces the stolen prologue and continues at `0x188af0` on every outcome.
Its module ABI is `a7_fl_install(base, arg1, mode)`: mode 0 receives the MENU
ViewManager, mode 1 performs only boot reconciliation and must ignore `arg1`.
Both calls return at view `0x5b9b30` (Thumb LR `0x5b9b31`). Caves use 44/52 and
80/82 bytes. Tests compare complete original UserEntry trigger/action sequences
for all ten native states, including missing-module/symbol outcomes, against an
unpatched baseline, and prove module invocation precedes those sequences.
The fixture proves ABI/order, not live Backup service readiness or all possible
camera startup modes. Verify boot reconciliation on the camera before claiming
persistent FL applies before the first photograph.
