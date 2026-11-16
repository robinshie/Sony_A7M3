import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile

import backend as b
from app import AppServer


def release_zip(extra=None, corrupt=False, missing=False):
    module = b'example-module'
    manifest = {'release':'v0.01', 'module':{'file':'a7fl.so','size':len(module),'sha256':b.digest(module)},
                'universal_installer':True}  # Untrusted claim must never enable installation.
    files = {'a7fl.so':module, 'release-manifest.json':json.dumps(manifest).encode()}
    sums = ''.join(f'{b.digest(raw)}  {name}\n' for name,raw in files.items())
    if missing:
        files['not-listed'] = b'x'
    if corrupt:
        files['a7fl.so'] = b'changed-module'
    files['SHA256SUMS'] = sums.encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w') as z:
        for name, raw in files.items():
            z.writestr('bundle/'+name, raw)
        if extra:
            z.writestr(*extra)
    return out.getvalue()


class ToolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.card = Path(self.temp.name)/'card'; self.card.mkdir(); (self.card/'DCIM').mkdir()
        self.record = b.bundled_recipes()[0]

    def test_bundled_recipes(self):
        records = b.bundled_recipes()
        self.assertEqual(len(records),12)
        self.assertEqual(len({r['recipe']['id'] for r in records}),12)

    def test_copy_readback_and_idempotence(self):
        result = b.copy_recipes(str(self.card),[self.record])
        self.assertTrue(result['ok'])
        self.assertEqual(b.parse((self.card/self.record['filename']).read_bytes()), self.record['recipe'])
        before = (self.card/self.record['filename']).stat().st_mtime_ns
        self.assertEqual(b.copy_recipes(str(self.card),[self.record])['files'][0]['state'],'present')
        self.assertEqual(before,(self.card/self.record['filename']).stat().st_mtime_ns)

    def test_conflict_does_not_write_any(self):
        b.copy_recipes(str(self.card),[self.record])
        changed = copy.deepcopy(self.record); changed['recipe']['parameters']['grain'] = 9
        new = b.bundled_recipes()[1]
        with self.assertRaises(ValueError): b.copy_recipes(str(self.card),[new, changed])
        self.assertFalse((self.card/new['filename']).exists())

    def test_existing_id_different_filename_rejected(self):
        b.copy_recipes(str(self.card),[self.record])
        renamed = dict(self.record,filename='different.a7look')
        with self.assertRaises(ValueError): b.copy_recipes(str(self.card),[renamed])

    def test_formatting_only_is_skipped(self):
        (self.card/self.record['filename']).write_text(json.dumps(self.record['recipe'], indent=4), encoding='utf-8')
        self.assertEqual(b.copy_recipes(str(self.card),[self.record])['files'][0]['state'],'present')

    def test_path_and_reserved_names_rejected(self):
        for name in ('../test.a7look','x/y.a7look','C:\\x.a7look','NUL.a7look','con.a7look','._x.a7look','x.a7look ','x.txt'):
            with self.subTest(name=name), self.assertRaises(ValueError): b.filename(name)

    def test_wrong_card_root(self):
        with self.assertRaises(ValueError): b.copy_recipes(str(self.card/'DCIM'),[self.record])

    def test_system_root_rejected(self):
        with self.assertRaises(ValueError): b.card_root(str(Path(self.temp.name).anchor))

    def test_duplicates_and_invalid_params_preflight(self):
        with self.assertRaises(ValueError): b.copy_recipes(str(self.card),[self.record,self.record])
        bad = copy.deepcopy(self.record); bad['recipe']['parameters']['grain'] = 10
        with self.assertRaises(ValueError): b.copy_recipes(str(self.card),[bad])
        self.assertEqual(len(list(self.card.glob('*.a7look'))),0)

    def test_card_limit_and_appledouble(self):
        for i in range(32): (self.card/f'{i}.a7look').write_text('legacy')
        with self.assertRaises(ValueError): b.copy_recipes(str(self.card),[self.record])
        (self.card/'0.a7look').unlink()
        (self.card/'._test.a7look').write_text('metadata')
        self.assertTrue(b.copy_recipes(str(self.card),[self.record])['ok'])

    def test_card_errors_are_reported_per_file(self):
        (self.card/'bad.a7look').write_text('not JSON')
        self.assertIn('error',b.read_card(str(self.card))['files'][0])

    def test_copy_failure_reports_partial_progress(self):
        records = b.bundled_recipes()[:2]
        original = b.os.fsync
        calls = 0
        def fail_second(fd):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('card disconnected')
            original(fd)
        with patch.object(b.os,'fsync',side_effect=fail_second):
            result = b.copy_recipes(str(self.card),records)
        self.assertFalse(result['ok']); self.assertEqual(len(result['files']),1)
        self.assertTrue((self.card/records[0]['filename']).exists())
        self.assertFalse((self.card/records[1]['filename']).exists())

    def test_package_and_untrusted_install_claim(self):
        raw = release_zip()
        result = b.inspect_package(raw,b.digest(raw))
        self.assertEqual(result['files_verified'],2)
        self.assertFalse(result['install_enabled'])
        self.assertTrue(result['external_hash_matched'])

    def test_zip_errors(self):
        for raw in (release_zip(corrupt=True), release_zip(missing=True), release_zip(('../escape',b'x')), b'invalid'):
            with self.subTest(raw=raw[:12]), self.assertRaises((ValueError,zipfile.BadZipFile)):
                b.inspect_package(raw)
        with self.assertRaises(ValueError): b.inspect_package(release_zip(),'0'*64)

    def test_zip_duplicate_path(self):
        with self.assertWarns(UserWarning): raw = release_zip(('bundle/a7fl.so',b'x'))
        with self.assertRaises(ValueError): b.inspect_package(raw)

    def test_zip_symlink(self):
        link = zipfile.ZipInfo('bundle/link'); link.external_attr = 0o120777 << 16
        with self.assertRaises(ValueError): b.inspect_package(release_zip((link,b'a7fl.so')))


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.server = AppServer(('127.0.0.1',0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def request(self,headers=None,route='status'):
        req = urllib.request.Request(self.server.origin+'/api/'+route,data=b'{}',headers=headers or {},method='POST')
        return urllib.request.urlopen(req, timeout=10)

    def test_authorized_status_and_static_assets(self):
        with self.request({'Origin':self.server.origin,'X-A7-Token':self.server.token}) as response:
            data = json.load(response)
        self.assertFalse(data['install_enabled']); self.assertEqual(len(data['recipes']),12)
        for path in ('/','/app.js','/style.css'):
            with urllib.request.urlopen(self.server.origin+path) as response:
                self.assertEqual(response.status,200); self.assertIn('frame-ancestors',response.headers['Content-Security-Policy'])

    def test_foreign_origin_host_and_missing_token_rejected(self):
        for headers in ({}, {'Origin':'https://other.example','X-A7-Token':self.server.token},
                        {'Origin':self.server.origin,'X-A7-Token':self.server.token,'Host':'other.example'}):
            with self.assertRaises(urllib.error.HTTPError) as error: self.request(headers)
            self.assertEqual(error.exception.code,403)
            error.exception.close()

    def test_no_firmware_write_route(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request({'Origin':self.server.origin,'X-A7-Token':self.server.token},'install')
        self.assertEqual(error.exception.code,404)
        error.exception.close()

    def test_first_install_requires_ack_before_any_device_job(self):
        req=urllib.request.Request(self.server.origin+'/api/first-install/prepare',data=b'{}',method='POST',
            headers={'Origin':self.server.origin,'X-A7-Token':self.server.token})
        with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
        error.exception.close()
        self.assertEqual(self.server.installer.snapshot()['phase'],'idle')


if __name__ == '__main__': unittest.main()
