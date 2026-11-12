#!/usr/bin/env python3
"""Package a tested FL module for the accepted fixed-capture baseline."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

from camera.native_module_replace import REVISIONS
from local import ROOT, file_sha

LAB = ROOT / '.lab'  # The native builders use this repository-local directory.
REVISION = 5
BASELINE = (LAB / 'native-fl-releases/update-r4-4396_3_9/binding' /
            'replace-1794449171444488000')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir', type=Path, required=True,
                        help='Directory containing liba7-fl-module.so and proof.json')
    parser.add_argument('--write-device', action='store_true',
                        help='After packaging, perform USB preflight, write, and read back')
    args = parser.parse_args()
    build = args.build_dir.resolve()
    module, proof = build / 'liba7-fl-module.so', build / 'proof.json'
    if not module.is_file() or not proof.is_file():
        parser.error('Build the resident module with research/native_module.py --with-bootstrap first.')
    if file_sha(module) == REVISIONS[REVISION]['old_sha']:
        parser.error('The candidate is identical to the installed baseline; no update package will be produced.')
    baseline_module, baseline_view = BASELINE / 'new-module-readback.so', BASELINE / 'view-after.so'
    if not baseline_module.is_file() or not baseline_view.is_file():
        parser.error('The verified revision 4 camera readback is missing.')

    def run(*command):
        subprocess.run([sys.executable, *map(str, command)], cwd=ROOT, check=True)

    releases = LAB / 'native-fl-releases'
    releases.mkdir(mode=0o700, parents=True, exist_ok=True)
    binding = Path(tempfile.mkdtemp(prefix=f'update-r{REVISION}-', dir=releases)) / 'binding'
    run('research/native_module_replace_test.py', '--revision', REVISION)
    run('research/native_module_replace_bind.py', '--revision', REVISION,
        '--old', baseline_module,
        '--view', baseline_view,
        '--module', module, '--proof', proof, '--out', binding)
    run('-m', 'camera.native_module_replace', 'preflight', '--binding', binding, '--offline')
    print(f'FL update package: {binding}', flush=True)
    if args.write_device:
        # The existing writer repeats the live identity/preimage checks in the
        # same USB session and stops on any mismatch, including a prior journal.
        run('-m', 'camera.native_module_replace', 'replace', '--binding', binding, '--write-device')
        print('Write and readback passed. Cold boot the camera to load the new module.')


if __name__ == '__main__':
    main()
