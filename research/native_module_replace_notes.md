# Atomic native module replacement

The first module revision is replaced through VFS using an exclusive candidate,
an original-inode hardlink backup, and an atomic rename. The running process
keeps its original mapped module until a separate cold boot. The loader, locale
files, LUTs and WBI are not written by this operation.

Host authorization and model identity are explicit: the same authenticated
session must read `ILCE-7M3` and the pinned build before uploading either helper.
The native helper independently checks the exact build, complete old module and
view hashes, directory/file properties, and the mount state. The native identity
callback records this host precondition; it does not claim to read the model.

The original `r1` preflight stopped at phase 1006, before creating a journal or
writing a file. Its new installer guard incorrectly required every inode to be
owned by root. Existing read-only camera metadata showed that Sony's original
`/usr/lib` directory and `viewUnified2.so` have UID 57285 and GID 1000, while our
installed module has UID/GID 0. This was an installer guard error, not a camera
permission failure.

Revision `r1b` checks ownership by path:

| Target | Required UID:GID |
| --- | --- |
| `/usr/lib` and original `viewUnified2.so` | `57285:1000` |
| Current/candidate/backup `a7fl.so` and `/setting` | `0:0` |

The old `r1` package and refusal evidence remain private and unchanged. The new
package is `.lab/native-module-replace-bound-r1b`. The corrected core passed
6,282 checks including 126 syscall fault points and targeted wrong-owner cases;
the host workflow passed 126 assertions. These tests model metadata and transport;
physical replacement and cold-boot UI validation are recorded separately.

```sh
python3 -m camera.native_module_replace replace \
  --binding .lab/native-module-replace-bound-r1b --write-device --direct
```

The command first performs a fresh read-only preflight and confirms the WBI
header is already zero. It never clears WBI, resumes an existing journal, or
automatically retries a failed writer. Full original/new module and unchanged
view readbacks, the transaction journal, and durable host evidence are required
before success is reported.

The second replacement (`--revision 2`) pins deployed module `e64867d2…` and
uses `.a7fl-r2.new`, `.a7fl-e64867d2.orig`, and `/setting/A7FLUP2.LOG`. Its
separate paths preserve the first update's backup and journal. The revision is
included in the bundle digest and must match the compiled native core; the
host derives targets from a fixed revision profile. Its core regression passed
8,169 checks with 126 fault points, including preservation of prior artifacts.

The r3 feedback module `f3e2d657…` was published through this second replacement
and fully read back; the original view and WBI stayed unchanged. Physical
feedback and cold-boot preference restoration are still separate acceptance
steps.
