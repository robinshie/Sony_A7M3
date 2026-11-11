# Native bootstrap guard fixture

`native_bootstrap_test.py` compiles the actual `payloads/a7-fl-bootstrap.c` into
an ARM QEMU guest through its explicit test hooks. Linux file reads, the Backup
API calls, and the resident module API are recording mocks. The production
bootstrap's maps parser, readable-range checks, version/model checks, original
function-byte comparisons and native-page profile checks execute
unchanged. This complements the separate original-node, module-core and loader
fixtures; it does not simulate the camera LCD, ISP, real filesystem or USB.

```sh
python3 research/native_bootstrap_test.py
```

Inputs include privately generated `.lab/native-bootstrap/a7-fl-bootstrap-pins.h`
and the source-pinned dual-loader proof. The test caller actually sets ARM LR to
the new loader's `view_base + 0x5b9b31` and returns through that mapped Thumb
address. It also invokes the obsolete callsite and a normal C caller to check
their rejection. There is no test-only bypass of the production return-address
guard. The fixture maps view, Caution and Backup regions at `0x40000000`,
`0x50000000`, and `0x60000000`; harness storage lives at `0x70000000`.

The Backup test hook checks that all four original function pointers retain
their Thumb bit before replacing API calls with mocks. The six unmodified
16-byte Sony function pins remain at their original relative addresses and are
independently corrupted to prove rejection before any mocked Backup API call.

The latest run passed **848 checks**. Coverage includes MENU and boot routing,
boot ignoring the UI argument and uninitialized menu nodes, the exact warm and
cold still-photo page-14 profiles, repeated initialization, exact model/build/
length checks, native child alignment and readability, property pointer and
one-based page-index identity, ViewManager mismatch, fragmented maps reads, stale map
bases, mapped filename lookalikes, address overflow, excluded device/resource/
shared mappings and selected syscall errors. Source pins and the precise check
count are emitted to `.lab/native-bootstrap-test/proof.json` only on a passing
run. A failed run removes that proof rather than leaving a stale success marker.
The current deployment profile has one still-photo parent. Movie-menu insertion
is excluded; this fixture makes no claim for a movie-page initialization path.

No payload is uploaded or executed on the camera by this fixture. It cannot
establish physical menu-key dispatch, capture behavior, power-loss recovery or
successful persistent installation.
