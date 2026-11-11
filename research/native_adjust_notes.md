# Native adjustment component, Sony A7M3 4.04

This is a native setting-node component, not the standalone `ui/` camera mockup.
It is **not a complete loadable UI payload**: it still requires the native menu
attachment, process-data manager adapter, registered title resources, real
backend callbacks, and camera validation. The QEMU fixture executes original
node machine code with recorded backend callbacks; it does not render the
camera LCD or emulate the ISP.

## Build and evidence

```sh
PYTHONPATH=research:.lab/research-deps python3 research/native_adjust_fixture.py \
  --usr /path/to/nflasha15_unpacked
```

Requires `arm-none-eabi-gcc` and `qemu-system-arm`. It reads locally supplied
firmware and writes extracted Sony bytes only under ignored `.lab/native-adjust`.
The fixture pins original `CautionConfig.so` SHA-256 to
`0b9f2b855c032fc36cc83386a1fe706a8b59042e52702035a7d1a293b4e9f8a0`.
The latest run passed **1,310 checks**. `.lab/native-adjust/report.json` records
component hashes and scope. The checks cover:

- Original constructors and original node vtable dispatch, parent linkage, a
  group containing Off/FL and eight adjustment fields.
- Original binary-search property getters, nonnegative UI enums and native numeric
  labels, selection and forward navigation.
- The actual `PAS_SelectListTab` layer-one traversal reads two pages with six
  and four rows. A negative control reproduces the prior flat-tree bug: direct
  fields beneath the root are interpreted as pages and numeric options become
  page contents. Page wrappers are required even though the old generic node
  construction and lifetime tests passed.
- Signed backend values round-trip through nonnegative model enums. Native
  `SettingMenu` uses `-1` as an unavailable-value sentinel, so a real adjustment
  of `-1` must never be passed directly to the UI model interface.
- Accepted callback updates followed by original cursor selection; rejected
  callbacks preserve the value and cursor.
- Same-value updates restore a cursor reset by original parent initialization
  without invoking the real backend again.
- Later original parent initialization also restores the current mode/scalar
  selection automatically, including heap clones and graphs with Save. This
  covers the cold MENU path that initializes its graph after the loader seam.
- Sharpness range and clarity remain visible but gray and reject writes.
- Unrelated stock PP process IDs, invalid ranges and disabled fields never
  call the recording backend.
- Real stock destruction of an owning heap parent with an embedded child,
  destruction of an uninitialized shallow clone, and destruction of an
  initialized deep clone, with and without the optional Save row: 498 native
  allocations and 498 frees, with no free of
  embedded storage, no double free, and surviving original embedded graph.
- Capability grayout remains correct in all eight fields after original native
  deep cloning and initialization.

The test's title resource IDs are placeholders and cannot render on a camera.
Integration must pass actual registered resource IDs. The production resource
builder currently assigns root `0x0204fd9e`, FL `0x0204fd9f`, and eight labels
`0x0204fda0..0x0204fda7`; these are caller inputs, not hard-coded requirements.

## C API and native ABI

`native_adjust.h` declares a 40-byte ARM `NativeAdjustNode` and an 8-byte
`NativeAdjustProperties`. The latter contains a property-array pointer and an
**inclusive last index**, not a count: original search at `0x6835b2` tests
`low <= high`. Properties are sorted `(key, type, value)` triples of 12 bytes.

`native_adjust_build` constructs one group containing two kind-0 page wrappers,
six rows on the first page and three on the second (four with Save), using these
custom process-data IDs:

| ID | Field | Intended backend |
|---|---|---|
| `0x7000` | Off / FL experimental | Restore original / apply experimental LUT |
| `0x7001` | Contrast | Bounded native LUT generator |
| `0x7002` | Highlights | Bounded native LUT generator |
| `0x7003` | Shadows | Bounded native LUT generator |
| `0x7004` | Fade | Bounded native LUT generator |
| `0x7005` | Saturation | Bounded native LUT generator |
| `0x7006` | Sharpness | Native CS -3..+3, only if separately verified |
| `0x7007` | Sharpness range | Unproven: disabled |
| `0x7008` | Clarity | Unproven: disabled |
| `0x7009` | Optional Save action | Explicit native execution, not a scalar setter |

Ranges, defaults, title/help IDs and an enabled-field mask are supplied by the
caller. The existing native LUT generator uses -9..+9 for contrast, highlights,
shadows and saturation, and 0..9 for fade. Use mask `0x1f` until sharpness has a
verified backend. Mode is always available; the callback must reject unsafe
operations. There is no hidden Picture Profile activation.

`native_adjust_read`/`native_adjust_write` return 1 for success, 0 for rejection.
These APIs retain signed backend values. The process-manager boundary must use
`native_adjust_encode` and `native_adjust_decode`: scalar enums are
`value - minimum`, while mode remains 0/1. Invalid enums, including `-1`, are
rejected without changing output. Persistence and LUT parameters remain signed.
The `apply(context, field, value)` callback must also return nonzero only when
the **real backend accepted** the change. Field indices are 0..7 in table order;
mode uses `NA_MODE == 8`. Callbacks happen before stored value/cursor updates.
Persistence and loading saved state are the integration's responsibility.

`native_adjust_add_save(tree, 0x0204eaab)` optionally appends the fourth row of
the second page before attachment or cloning. The stock resource is 保存 / Save.
It uses kind 2, execution 4, process `0x7009`, no children and no scalar value.
The integration must bind the original manager execution callback separately.
Calling it twice, using a missing title, or modifying an attached tree fails.
Original initialization establishes its parent and 1-based index; as with
original action nodes, no subtree recursion is performed for this child. The
function restores all current scalar and mode cursors after reinitialization.

The root has kind `0xb = 2`, execution `0xc = 3` (generic group, as used by the
original PP Detail group). Its children are page nodes with the single property
`0xb = 0`; each page contains at most six field/action rows. Each scalar node has
kind 2, execution 0, process ID at key `0xe`. Leaves have kind 0, execution 1,
nonnegative enum at both `0xf` and `0x10`. The original mode/list code compares
key `0x10`, falling back to `0xf`.
Off uses existing resource `0x0204e0d2`; signed numeric labels -15..+15 use
`0x0204e7ad + value`, except zero uses `0x0204e39c`.

The owner must keep embedded tree storage alive. Its private copy of the
original 65-slot vtable retains the original RTTI prefix and overrides D0/D1,
clone and deep initialization. Destruction of embedded nodes clears the parent
pointer without freeing storage. Never bypass virtual dispatch
and directly call the stock recursive destructor on embedded nodes. The stock
clone constructor allocates its own child pointer array; the clone hook then
installs a second vtable retaining original owning D0/D1. Original initialization deep-clones children with a
different existing parent; such clones use stock owning destructors normally.
Initialization hooks reapply capability grayout and current mode/scalar cursor,
which stock init would reset. They act on the actual node passed by native code,
including owning clones, while obtaining accepted state from the persistent tree.
These clone/destruction paths are exercised in the fixture. The standalone
embedded graph itself requires no heap allocation. Prefer process-lifetime
ownership; safe dynamic unloading still requires proving that no native widget,
parent, clone or callback retains a pointer into the tree or its property arrays.

### Original addresses, relative to CautionConfig.so load base

| Function/data | Address |
|---|---:|
| Node constructor | `0x68338d` (Thumb) |
| Node vtable, address point | `0x918ec0`, `0x918ec8` |
| Node vtable GOT slot | `0x9880b0` |
| `initSettingNode` | `0x682869` |
| `getSelectedItem` | `0x682951` |
| `getIntProperty` | `0x683297` |
| `setItemSelectedByIndex` (1-based) | `0x682e59` |
| `setItemSelectedByDiffSRNum` | `0x682e9d` |
| `setItemGrayout` | `0x682edb` |
| `CmnViewSettingProperties::_getPropertyIndex` | `0x6835b3` |

Original virtual slots relative to node address point: `0x24` get child by
selectable index, `0x28` get selected child, `0x5c` get integer property, `0xb8`
select item, `0xbc` select by 1-based index, `0xc4` move selected index, `0xc8`
grayout, `0xe0` update node.

## Original native widget seam

`ViewPictureProfileToInstance` in `viewUnified4.so` is `0x1cbd91` and allocates
`0x184` bytes. Constructor `0x1cbaf4`; layout setup `0x1cba1c` uses layout resource
`0xd9e36df9`. The list widget resource `0xdd5e78a7` is a `PAS_SelectListTab`.

Original first-page initialization `0x1cd400` gets the widget, sets layer 0,
sets the profile, selects the first child from the node root at object `+0x164`,
then calls `PAS_SelectListTab::initMenuDataForList(root)`. In the original PP
subpage setup `0x1cc6cc`, it changes to layer 1 and passes the node root at
`+0x16c`. These are evidence that the native widget consumes generic node trees;
the original PP view event handlers **must not** be reused as FL backend handlers.
They write selected PP bank data and issue PP model commands.

Original exported generic utility functions in `viewUnified2.so` also exist at
`CmnSettingNodeUtil::initSettingNodeData = 0x399871`,
`initWidgetForSettingNodeTable = 0x399939`, and
`initWidgetForLvWithUpperLabel = 0x399ae5`. The separate `native_menu` component
hooks the central process-data manager for the custom IDs and delegates other
IDs to original code.

The fixture executes original `PAS_SelectListTab::initMenuDataForList` at
`0x5741bd` and its layer-one worker at `0x5740d4`. Rendering setters are recording
stubs; node traversal is original code. The original PP Detail root array
`CautionConfig.so:0x9b3e7c` points to Page1, whose kind-only property list is
`0x7ec7bc`; the page array `0x99eb94` then points to its field rows. This
distinction was missing in the first deployed graph and caused numeric pages.

## Detail, sharpness range and clarity: evidence boundary

The A7M3 native Creative Style setter is `viewUnified2.so:0x420d19`. It supports
contrast/saturation/sharpness -3..+3 and sends `@M00B`, command 38, parameters
383/386/389/392/383. Existing `creative_setter` QEMU evidence proves that this
setter still reports success when the mocked model request fails. Its return
value alone cannot certify actual sharpness application; verification must read
back the active CS state.

The following **Picture Profile** paths are precisely located, but do not prove
an independent FL spatial backend:

| PP control | Process ID | Native setter | Model request |
|---|---:|---:|---|
| Detail Level | `0x14c` | `0x41cfb9` | `@M00B`, command 64, parameter `0x23c`, -7..+7 |
| Crispening | `0x151` | `0x426515` | `@M00B`, command 64, parameter `0x24c`, 0..7 |

Detail Level dispatches through factory type `0xb0`, singleton factory
`0x3fcf24`, constructor `0x41cd30`, vtable `0x8a08a8` (+8 address point), setter
slot `+0x58`. Conversion `0x41cd54` maps 15 UI enums to signed -7..+7.
Crispening dispatches through type `0xc9`, factory `0x3fda14`, constructor
`0x4262f0`, vtable `0x8a1090`, setter slot `+0x58`.

Both setters construct `CmnViewPictureProfileCommon`; their memory-recall branch
uses a selected PP bank, and field indices 18/23 respectively to obtain PP backup
IDs. A7 IV Sharpness Range is not established to equal Crispening, and Clarity is
not established to equal any of these PP controls. No independent processing
API has yet been verified for either. They remain disabled.
