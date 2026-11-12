# Native save confirmation, ILCE-7M3 4.04

`--save-dialog` adds a Chinese Confirm / Cancel dialog before the existing durable
preference commit. Cancel keeps the preview, without calling the store or the
full preview-revert operation. Completion is displayed only when the guarded
commit returns zero. The second confirmation closes the result; it cannot save
twice. A failed commit displays failure and leaves the existing error/dirty state.

## Native binding

The module lazily loads `viewUnified6.so` and retains it and `libObj.so` through
the original view2 loader PLTs. All ABI inputs are pinned to the project's 4.04
ELFs. Code bytes, factory GOT, and the three original callback addresses must
match before changing writable data. Failure releases loader references.

`ViewExecuteConfirmDlgToInstance` (Thumb `0x4391f`) allocates 296 bytes and uses
the vtable at `0x839b8`; the primary vptr is `0x839c0`, secondary is `0x83b1c`.
The factory's GOT remains unchanged. Three data slots in the original table are
routed through the module so both new and framework-cached instances work:

| Table address | Original function | Role |
| --- | --- | --- |
| `0x83ab8` | `0x43a5d` | User action |
| `0x83abc` | `0x43b15` | State-specific drawing |
| `0x83aa4` | `0x42b6f` | Termination / original wrapper cleanup |

Routing requires the exact primary vptr, ViewManager, and boot element
`0x41374644` at object offset `0x124`. All other cases call original functions.
Custom confirm/cancel never call the original boolean BackupManager actions.
The dialog instance is bound after its visible state is reached and cleared on
close/termination. Repeated or late events after closing cannot commit.

Native `ViewBase::openViewWithoutUnsetMute` queues `0x11012001`, view ID parameter
6 and boot element parameter 26. The small sender supplies exactly the members
that this pinned nonvirtual implementation reads: a null alias map at `0x70`
and the verified ViewManager at `0x24`. No fabricated object is registered with
the framework or destroyed. The framework constructs/manages the actual view.

The title is widget `0x53034e72`; button IDs are `0x9b9fd79f` (confirm) and
`0x9b9fd7a0` (cancel). Checked native casts precede access to their GEN_Label
subobjects (`0x1bc` and `0xe00`, proven by native wrappers). The existing CJK font
and layout are reused with static UTF-8 text. The result hides Cancel and focuses
Confirm, including subsequent redraws.

## Validation and limits

`native_save_dialog.py` runs original factory/constructor, open-event code,
state-action mapping, highlight navigation and state drawing in ARM QEMU. The
production binder checks actual pinned bytes before modeled widget APIs are
installed in the fixture. It checks foreign bytes/GOT, loader cleanup, cached
instances, cancellation, failed storage, completion, repeat keys, termination,
and original stock boot elements. Rendering, EventManager and widget storage are
modeled; sensor/display hardware and actual framework scheduling are not.

The module integration fixture separately verifies that native Save only opens
the dialog, Cancel retains preview without storage writes, Confirm commits once,
and persistence errors reach the result callback. The existing capture and
cold-start regression fixtures continue to run. Physical validation remains:

1. Cold boot, edit one value, Save: check prompt and both buttons.
2. Cancel: return to the same settings, without a committed generation change.
3. Save → Confirm: show Complete, Confirm closes the dialog.
4. Reboot: the confirmed value remains. Original menu and JPEG operation work.

Only the new `a7fl.so` is written by revision 6. At the user's request, the
`v0.01` release is updated in place from r5 to this accepted r6 module. The
manifest revision and SHA-256 identify the replacement despite the same tag.

On 2026-11-12 the user confirmed that cold-start Confirm, Cancel, Complete and
return work. Read-only inspection in
`.lab/native-inspect/read-1794458174085483000/` found the expected resident module,
no fault/error/dirty state, and generation 20 matching the saved preferences,
table 0 and both CAP tables. Table 3 remains original. User feedback and hashed
evidence are recorded separately in the r6 binding's
`user-acceptance-2026-11-12.json`; automated physical-validation flags were not
rewritten. This accepts r6 as the next development baseline, without claiming a
new JPEG comparison or physical storage-failure test.

## r7: repaint the cached Save row

The asynchronous commit changed node property 0, but the underlying categorized
menu retained its previous widget text. The stock action calls
`setSettingMenuExistenceForCommonShootingSetting(true)`; this is not a generic
model-change notification and cannot invalidate the cached row.

Before SettingMenu construction, r7 pins and replaces two writable data slots:
view2 `0x87b6fc` (draw, original `0x21fc81`) and `0x87b6e4` (termination,
original `0x21e375`). Original callbacks always run. Observation requires vptr
`0x87b600`, the same ViewManager, mode 3 and an owned root vtable/properties
pair, including native owning clones. Leaving the category or terminating the
view drops the observed pointer.

After commit, widget `0xdabd8bcb` must pass the native categorized-list cast and
its root at `0x124a8` must match the live menu category at `0x188`. Original
row population `0x5944ad` reads title property 0 and repopulates the button
labels. It does not change pages, selection or preferences. This happens while
the result dialog is still visible, before its existing drawDirect call.

The fixture now executes this original row population, including page/selection
accessors and seven row setter calls. It verifies Complete before popup close,
Not Complete on failure, unchanged page 2 / selected row 4, no repaint on Cancel,
foreign category/widget exclusion and termination cleanup. Node property access,
button setters and the renderer are modeled; the module fixture separately
checks the real root ownership guard. This is not a physical display test.

r7 write/readback completed on 2026-11-12, SHA-256
`74d1df6c73ebd7d056ce741a28e3f459fdf2e7c5ac29063527e18b7111a64703`,
63,524 bytes. Evidence is in
`.lab/native-fl-releases/update-r7-yqrdhmaf/binding/replace-1794462136604332000/`.
The user subsequently completed the requested cold-start workflow and reported
that the returned menu immediately displays Complete, without moving the cursor.
Acceptance and hashed evidence are recorded separately in the r7 binding's
`user-acceptance-2026-11-12.json`. A subsequent read-only diagnostic attempt
stopped because neither UTM nor the Mac detected the camera; no resident probe
ran and no settings were written. Post-reboot resident/preferences/LUT status
was therefore not re-read. The accepted r7 readback is the next update baseline.
At the user's request, the v0.01 replacement package uses this accepted r7
module. Its manifest revision and SHA-256 distinguish it from the prior r6 ZIP.
