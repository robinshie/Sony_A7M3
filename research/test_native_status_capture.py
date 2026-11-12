"""Offline checks for read-only reporting of the capture LUT transaction."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from camera import native_status as status
from local import file_sha, sha


class CaptureStatusTests(unittest.TestCase):
    def setUp(self):
        self.original=[bytes([i])*1280 for i in range(4)]
        self.fixed={key:bytes([8+i])+self.original[i][1:]
                    for i,key in enumerate(status.CAPTURE_PROPERTIES,1)}
        self.profile=SimpleNamespace(original=self.original,original_sha=sha(self.original[0]),
                                     base=bytes(1280),codec=bytes(771),capture=self.fixed)
        self.module_attestation={'capture_look':{
            'arm_transaction_verified':True,'fixed_capture_tables':True,
            'property_ids':list(status.CAPTURE_PROPERTIES),
        }}

    def test_offline_proof_and_both_candidate_files_are_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof_path=Path(tmp)/'proof.json'
            records=[]
            for i,(key,candidate) in enumerate(self.fixed.items(),1):
                name=f'offline-capture-table{i}.bin'
                (proof_path.parent/name).write_bytes(candidate)
                records.append(dict(property=hex(key),file=name,bytes=1280,
                                    original_sha256=sha(self.original[i]),candidate_sha256=sha(candidate),
                                    original_packed_table_restored=True))
            proof_path.write_text(json.dumps(dict(capture_candidates=records,source_sha256={
                'camera/native_status.py':file_sha(status.ROOT/'camera/native_status.py'),
            })))
            self.module_attestation['capture_look']['source_qemu_proof_sha256']=file_sha(proof_path)
            self.module_attestation['capture_look']['tables']=records
            self.assertEqual(status.capture_candidates(proof_path,self.module_attestation,self.original),self.fixed)
            with self.assertRaisesRegex(ValueError,'requires the bound'):
                status.capture_candidates(None,self.module_attestation,self.original)
            with self.assertRaisesRegex(ValueError,'no attested'):
                status.capture_candidates(proof_path,{},self.original)
            with self.assertRaisesRegex(ValueError,'Unexpected capture proof record'):
                status.capture_candidates(proof_path,self.module_attestation,self.original[::-1])
            candidate_path=proof_path.parent/records[1]['file']
            candidate_path.write_bytes(bytes(1280))
            with self.assertRaisesRegex(ValueError,'Capture candidate differs'):
                status.capture_candidates(proof_path,self.module_attestation,self.original)
            proof_path.write_bytes(proof_path.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'Capture proof differs'):
                status.capture_candidates(proof_path,self.module_attestation,self.original)

    def test_on_mismatch_off_and_unstable_readback(self):
        # Synthetic monotonic codec satisfying the normal LUT validator.
        self.profile.codec=(b'\0\0'+b'\0\2'*128)+bytes(512)+b'\x80'
        report={'header':{'status':1,'stable':1,'dlclose_result':0},
                'runtime':{'runtime_ready':1,'fault':0,'mode':1,'parameters':[0]*8}}
        live=[self.profile.base,*self.fixed.values(),self.original[3]]
        def observe(tables):
            return status.observations(self.profile,report,[None,None],tables)
        good=observe(live)
        self.assertTrue(good['active_table_matches_runtime'])
        self.assertTrue(good['capture_tables_match_runtime'])
        self.assertTrue(good['untouched_table3_original'])
        self.assertFalse(good['other_three_tables_original'])
        self.assertFalse(good['jpeg_application_verified'])
        self.assertEqual([t['state'] for t in good['tables'][1:3]],['fixed-capture-FL']*2)
        for i in (1,2):
            partial=list(live);partial[i]=self.original[i]
            failed=observe(partial)
            self.assertTrue(failed['preview_table_matches_runtime'])
            self.assertFalse(failed['capture_tables_match_runtime'])
            self.assertFalse(failed['active_table_matches_runtime'])
        live[3]=bytes(1280)
        self.assertFalse(observe(live)['untouched_table3_original'])
        report['runtime']['mode']=0
        self.assertTrue(observe(self.original)['capture_tables_match_runtime'])
        self.assertFalse(observe(live)['capture_tables_match_runtime'])
        report['header']['stable']=0
        self.assertIsNone(observe(live)['capture_tables_match_runtime'])
        self.assertIsNone(observe(live)['active_table_matches_runtime'])


if __name__=='__main__':
    unittest.main()
