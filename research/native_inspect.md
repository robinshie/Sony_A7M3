# Read-only resident inspection

`payloads/a7-fl-inspect.c` inspects the **already loaded** FL module. It never calls
the installer, boot initializer, preview setter, Save action or Backup writer.
It opens `/usr/lib/a7fl.so` with `RTLD_NOW | RTLD_NOLOAD`, and balances a successful
lookup with `dlclose`. An absent module is reported as absent; the probe does not
load it to make the result look successful.

The probe checks the exact firmware build and readable process mappings before
using the original Sony `dlopen`, `dlsym` and `dlclose` PLTs. It pins those PLTs,
the staged module's ELF header and both complete status-accessor functions. Only
`a7_fl_bootstrap_status` and `a7_fl_status` may be resolved, and returned function
pointers must equal their attested module-relative addresses. The returned data
must lie within that module's writable segment and readable process mappings.
Two identical copies are required, with at most three attempts if state changes.

Its only output is a temporary 148-byte report at
`/tmp/jiritsu/a7status.bin`; its maintenance loader file is removed. No preference,
calibration, firmware or activation file is written. The host verifies the complete
installed module hash before uploading this temporary probe and removes the report
after reading it. A status snapshot alone does not establish physical menu behavior.

Build and test against the current staged module:

```sh
python3 research/native_inspect.py --usr /path/to/nflasha15_unpacked
python3 -m camera.native_status --offline
```

The builder rejects changed module sources, dependency proofs or private LUT/codec
inputs. It generates `.lab/native-inspect/inspect.so` and `proof.json`. The QEMU
fixture executes the original Sony PLT machine code and exact compiled status
accessors, with modeled loader and proc files. Its 1,839 checks cover every pinned
byte, absent and failed lookups, wrong symbols, mapping bounds, unstable snapshots,
and balanced references. It does not exercise a camera or its dynamic linker.

The report is little endian: a 44-byte `<IIi4Ii3I` header, the 36-byte bootstrap
report and the 68-byte runtime report. Header status 1 means a stable loaded-module
snapshot, 0 means absent, and negative values identify validation/lookup errors.
The runtime report distinguishes ready, installed, dirty, saved generation, mode
and eight values. Host inspection additionally checks both preference records and
all four current LUTs; it regenerates the expected first-table bytes from the exact
five-control recipe. Other LUTs must still match their immutable originals.

The filesystem installer is independently reproducible with
`python3 -m camera.native_install --offline` (proof validation only), default
`verify`, or explicit `stage --write-device`. A retained journal never authorizes
automatic retry, overwrite or rollback. `rollback-review` is inspection only.
Filesystem staging and loader activation are distinct operations; cold boot and
physical Save verification must be recorded separately.
