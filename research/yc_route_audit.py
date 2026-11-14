#!/usr/bin/env python3
"""Audit the observed YC sample's route against pinned local Sony code.

Static branch/log evidence is not producer ownership or a live-view callback.
No USB I/O; Sony bytes and camera samples stay in the user's private .lab.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import capstone
from elf32 import ELF

ROOT = Path(__file__).resolve().parents[1]
OBJECT_SHA = '1117453a969c9dedeb9bf6b006514fd9c2644a79085590a797189df109d64d23'
AVCAM_SHA = 'e1b0f84e8323005a34b43de6dd0083fca712d2c654f0d9716512e0a54631bbe7'
GETTER = '_ZN26C_DataflowInfra_StdData_YC22GetEntry_ImageSizeInfoEP35C_DataflowInfra_Entry_ImageSizeInfo'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def thumb():
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.detail = True
    return md


def call(e, address, target, mnemonic):
    insns = list(thumb().disasm(e.read(address, 4), address))
    require(len(insns) == 1 and insns[0].size == 4 and
            insns[0].mnemonic == mnemonic and len(insns[0].operands) == 1 and
            insns[0].operands[0].type == capstone.arm.ARM_OP_IMM and
            insns[0].operands[0].imm == target, 'Unexpected native call')
    return dict(address=hex(address), target=hex(target), instruction=mnemonic,
                bytes_sha256=sha(e.read(address, 4)))


def instruction(e, address, mnemonic, operands):
    i = next(thumb().disasm(e.read(address, 4), address, count=1), None)
    require(i and (i.mnemonic, i.op_str) == (mnemonic, operands),
            f'Unexpected instruction at {address:#x}')
    return dict(address=hex(address), instruction=f'{mnemonic} {operands}')


def log_reference(e, load, expected):
    code = list(thumb().disasm(e.read(load, 32), load))
    require(code and code[0].mnemonic.startswith('ldr') and
            code[0].operands[1].type == capstone.arm.ARM_OP_MEM and
            code[0].operands[1].mem.base == capstone.arm.ARM_REG_PC,
            'Expected literal log reference')
    i = code[0]
    literal = ((i.address + 4) & ~3) + i.operands[1].mem.disp
    for following in code[1:]:
        if (following.mnemonic == 'add' and len(following.operands) == 2 and
                following.operands[0].reg == i.operands[0].reg and
                following.operands[1].type == capstone.arm.ARM_OP_REG and
                following.operands[1].reg == capstone.arm.ARM_REG_PC):
            target = (following.address + 4 + e.word(literal)) & 0xffffffff
            text = e.read(target, len(expected) + 1)
            require(text == expected.encode() + b'\0', 'Unexpected native log identity')
            return dict(load=hex(load), address=hex(target), text=expected)
    raise ValueError('Missing PC-relative log address')


def direct_callers(e, target):
    """Syntactic Thumb BL/BLX cross references, not a complete control-flow graph."""
    hits = []
    for section in e.sections:
        if not section[2] & 4:
            continue
        data = e.data[section[4]:section[4] + section[5]]
        for offset in range(0, len(data) - 3, 2):
            a, b = struct.unpack_from('<HH', data, offset)
            if a & 0xf800 != 0xf000 or b & 0xc000 != 0xc000:
                continue
            sign = (a >> 10) & 1
            i1, i2 = 1 - (((b >> 13) & 1) ^ sign), 1 - (((b >> 11) & 1) ^ sign)
            delta = (sign << 24) | (i1 << 23) | (i2 << 22) | ((a & 1023) << 12) | ((b & 2047) << 1)
            if sign:
                delta -= 1 << 25
            address = section[3] + offset
            pc = address + 4 if b & 0x1000 else (address + 4) & ~3
            if pc + delta != target:
                continue
            insns = list(thumb().disasm(data[offset:offset + 4], address))
            if (len(insns) == 1 and insns[0].mnemonic in ('bl', 'blx') and
                    insns[0].operands[0].imm == target):
                hits.append(hex(address))
    return hits


def audit(object_path, trace):
    e = ELF(object_path)
    require(sha(e.data) == OBJECT_SHA, 'Requires pinned ILCE-7M3 4.04 libObj.so')
    require(e.relocations[0x126ce20][1]['name'] == GETTER, 'Unexpected metadata import')
    calls = [call(e, 0x33c5d8, 0x106088, 'blx'),
             call(e, 0x33ce82, 0x33c594, 'bl'),
             call(e, 0x2af894, 0x106088, 'blx')]
    logs = [log_reference(e, 0x33c61a, '[InfDecoder]<IMAGE_SIZE_INFO>-----------------'),
            log_reference(e, 0x33ce68, '[InfDecoder][OUTPUT_YC_STD_DATA]-----START-----'),
            log_reference(e, 0x33ce3c, '[InfDecoder][SeqDecResize][%d] ResponceSequence. err =0x%x\n'),
            log_reference(e, 0x2af906, '[ObjRenderer]ExecCommandGetYcDataParam Out')]
    result = dict(object_sha256=OBJECT_SHA, calls=calls, logs=logs,
                  decoder_helper_direct_callers=direct_callers(e, 0x33c594),
                  observed_route='InfDecoder SeqDecResize / output YC metadata',
                  live_view_producer_verified=False, capture_before_encode_verified=False,
                  writable_ownership_verified=False, flash_ready=False,
                  limitation='Direct calls and log identities only; indirect calls and scheduling are not proven')
    if trace:
        report_bytes = (trace / 'live.json').read_bytes()
        report = json.loads(report_bytes)
        pixels = (trace / 'frame.raw').read_bytes()
        q = report['unit_query']
        require(report['status'] == 2 and report['armed'] == 0 and
                q['phase'] == 4 and all(q[k] == 0 for k in ('constructed', 'pending', 'held', 'poisoned', 'disposal')),
                'Sample reader is not fully stopped and cleaned')
        require(report.get('frame_exported') and report.get('camera_frame_removed') and
                report['frame_sha256'] == sha(pixels), 'Unverified frame download/cleanup')
        require(report['sampling'] == dict(row_bytes=1920, row_step=16) and
                len(pixels) == 261120 and len(report['records']) == 1 and
                report['records'][0]['object_relative_return'] == '0x33c5dd',
                'Sample was captured at a different route or geometry')
        result['camera_sample'] = dict(report_sha256=sha(report_bytes), pixel_sha256=sha(pixels),
                                       bytes=len(pixels), return_offset='0x33c5dd', cleaned=True)
    result['source_sha256'] = sha(Path(__file__).read_bytes())
    return result


def avcam_candidates(path):
    class Flat:
        def __init__(self, data):
            self.data = data

        def read(self, offset, length):
            require(0 <= offset <= len(self.data) - length, 'AV-CAM range outside file')
            return self.data[offset:offset + length]

        def word(self, offset):
            return struct.unpack('<I', self.read(offset, 4))[0]

    e = Flat(path.read_bytes())
    require(sha(e.data) == AVCAM_SHA, 'Requires pinned ILCE-7M3 4.04 AV-CAM')
    # Resolve names through actual RTTI/vtables, rather than attributing a
    # nearby string to an arbitrary function. These are firmware VAs in data.
    base = 0x635c6000
    def rtti(vtable, name):
        require(e.word(vtable) == 0, 'Unexpected primary vtable offset-to-top')
        info = e.word(vtable + 4) - base
        text = e.word(info + 4) - base
        require(e.read(text, len(name) + 1) == name.encode() + b'\0', 'Unexpected RTTI name')
        return dict(vtable_offset=hex(vtable), typeinfo_offset=hex(info), name=name)
    art = rtti(0x10e3fc0, '34ModuleImageFilterArtfilterOriginal')
    art['vtable_entries'] = [hex(e.word(0x10e3fc8 + 4*i) - base) for i in range(6)]
    require(art['vtable_entries'] == ['0x116e1d', '0x6b4b0f', '0x6b4edb',
                                     '0x6b4a99', '0x6b5071', '0x6b4ad9'],
            'Unexpected art-filter vtable')
    resize = rtti(0x10e41d8, '12ModuleResize')
    # ModuleImageFilterArtfilterOriginal's execution helper creates a resize
    # object. A filter class name alone does not locate a grain pixel kernel.
    got = (e.word(0x12a1fc) + 0x12a1d2) & 0xffffffff
    require(e.word(got + e.word(0x12a200)) == base + 0x10e41d8,
            'Resize constructor resolves a different vtable')
    jpeg = dict(
        source_handle=instruction(e, 0x3401ce, 'ldrh.w', 'r8, [r3, #0xf6]'),
        logs=[log_reference(e, 0x34020e, 'Stage_EncodeJpeg.cpp'),
              log_reference(e, 0x35cff8, 'AllocSetStdYc'),
              log_reference(e, 0x35cf36, 'CaptureUtilityStdYc.cpp')],
        calls=[call(e, site, target, 'bl') for site, target in (
            (0x340258, 0x35cfc8), (0x35cfee, 0x35e060), (0x35e08e, 0x776a5a),
            (0x776a82, 0x3a5970), (0x35d03a, 0x35cf10), (0x35cfb6, 0x35cc7c),
            (0x35cd90, 0x7c6d96), (0x35cd98, 0x7c7654), (0x3402b2, 0x33fff4))],
        descriptor_sets_original_source_handle=instruction(e, 0x35cd2e, 'strh.w', 'r4, [sp, #0x16c]'),
        limitation='Descriptor allocation does not grant a CPU lease over image pixels')
    sync_yc = dict(
        logs=[log_reference(e, 0x38fe76, 'SyncYCOut.cpp'),
              log_reference(e, 0x36fede, 'ImagingMain.cpp'),
              log_reference(e, 0x3a587c, 'MemoryHandle::AllocShare: DMM_UNIT_INVALID!')],
        calls=[call(e, site, target, 'bl') for site, target in (
            (0x37eda2, 0x38fc24), (0x37f804, 0x38fc24), (0x38fc70, 0x780972),
            (0x38fc80, 0x3a5868), (0x38fca8, 0x780934), (0x3a5894, 0x3a5140),
            (0x36feaa, 0x3903c0))],
        caller_flags=[instruction(e, 0x37ed98, 'movs', 'r0, #1'),
                      instruction(e, 0x37ed9e, 'strb.w', 'r0, [sp, #0x267]'),
                      instruction(e, 0x37f7fa, 'movs', 'r0, #1'),
                      instruction(e, 0x37f800, 'strb.w', 'r0, [sp, #0x2df]')],
        branch=[instruction(e, 0x38fc74, 'ldrb.w', 'r2, [r8]'),
                instruction(e, 0x38fc78, 'cbnz', 'r2, #0x38fc86'),
                instruction(e, 0x38fc8c, 'ldm.w', 'ip!, {r0, r1, r2, r3}'),
                instruction(e, 0x38fc90, 'stm.w', 'lr!, {r0, r1, r2, r3}')],
        limitation='Known callers pass a descriptor copy flag; alternate allocation shares an existing handle. Neither grants independent pixel ownership or proves LCD/EVF frame cadence.')
    display_sa = dict(
        logs=[log_reference(e, address, label) for address, label in (
            (0x4e8a3a, 'SA_EXEC_PROGRAM_COMP'),
            (0x4e88b2, '[SFRA][ERR] replaceYcSdsYcData: saYcData'),
            (0x4e898c, '[SFRA]  Disp SA Ycin'),
            (0x4e89aa, '[SFRA]  Disp SA Ycout'),
            (0x4e84bc, 'sendSaNotify NOTIFY MSG'))],
        calls=[call(e, site, target, 'bl') for site, target in (
            (0x4e8a6a, 0x4e8844), (0x4e8a9a, 0x4e88a0), (0x4e8962, 0x4e1848),
            (0x4e8984, 0x4e15f4), (0x4e89a6, 0x4e15f4), (0x4e8894, 0x4e83ec))],
        selects_existing_handle=[instruction(e, 0x4e896e, 'ldrb.w', 'r3, [r5, #0x3f5]'),
                                 instruction(e, 0x4e8988, 'ldrh.w', 'r3, [r5, #0x118]'),
                                 instruction(e, 0x4e89ac, 'ldrh.w', 'r3, [r5, #0x298]'),
                                 instruction(e, 0x4e89b2, 'strh', 'r3, [r4, #8]')],
        limitation='SA completion handler has a distinct display-selection branch; coverage of ordinary LCD/EVF cadence, actual pixel layout and exclusive CPU access remain unverified')
    scalar_path_transitions = dict(
        logs=[log_reference(e, address,
                f'[SFRS] ScalarInfraPathCmdSetPath::{name}() msg->GetStatus()=0x%08x')
              for address, name in ((0x4e4af8, 'TransPathSaThrough'),
                                    (0x4e4be8, 'TransPathSaProc'),
                                    (0x4e4de8, 'TransPathLiveView'))],
        common_helpers=[call(e, address, target, 'bl') for address, target in (
            (0x4e4b2c, 0x4e4854), (0x4e4c1c, 0x4e4854), (0x4e4e04, 0x4e4854),
            (0x4e4b82, 0x4e46d4), (0x4e4c72, 0x4e46d4), (0x4e4e14, 0x4e46d4))],
        limitation='The three transitions have distinct entry points although they share helpers; SA completion alone cannot classify active LiveView frames')
    scalar_live_jpeg = dict(
        logs=[log_reference(e, addr, label) for addr, label in (
            (0x4e7c1a, 'ScalarInfraSequenceLiveViewStage.cpp'),
            (0x4e7c82, '[SFRA][ERROR] ScalarInfraSequenceLiveViewStageAutoexec_jpeg ddl_jpeg err=%d file=%s line=%d'),
            (0x4e7a22, '[SFRA][ERROR] ScalarInfraSequenceLiveViewStageAutoexec_jpeg_comp NG file=%s line=%d'))],
        calls=[call(e, address, target, 'bl') for address, target in (
            (0x4e7c16, 0x4e156c), (0x4e7c44, 0x646ddc),
            (0x4e7c6c, 0x646ddc), (0x4e7c7a, 0x7a7a2a),
            (0x4e7a4a, 0x4e94e0))],
        parameters=[instruction(e, 0x4e7c56, 'mov.w', 'r3, #0x280'),
                    instruction(e, 0x4e7c5c, 'mov.w', 'r3, #0x168'),
                    instruction(e, 0x4e7c68, 'str', 'r0, [sp, #8]'),
                    instruction(e, 0x4e7c76, 'str', 'r0, [sp, #0x24]')],
        limitation='One LiveView JPEG command stage sets 640x360 fields and submits a JPEG request. It proves neither ordinary panel scanout nor the full-size still source.')
    return dict(avcam_sha256=AVCAM_SHA,
                jpeg_descriptor_route=jpeg, sync_yc_route=sync_yc, display_sa_selector=display_sa,
                scalar_path_transitions=scalar_path_transitions,
                scalar_live_jpeg=scalar_live_jpeg,
                logs=[log_reference(e, 0x17185c,
                        'VDF::VDF_ERR VDF::VdfInputCmdUpdateYuv::UpdateYuvThrough(VDF::MsgAccessorIf*, VDF::SubsystemAccessorIf*)'),
                      log_reference(e, 0x1757ce,
                        'VDF::VDF_ERR VDF::VdfInputCmdUpdateYuvPin::UpdateYuvThrough(VDF::MsgAccessorIf*, VDF::SubsystemAccessorIf*)'),
                      log_reference(e, 0x34f6d4, 'SoftFocus_Base')],
                soft_focus_calls=[call(e, 0x34f668, 0x54cb2c, 'bl'),
                                  call(e, 0x34f6ca, 0x54ccd4, 'bl')],
                soft_focus_address_checks=[
                    log_reference(e, 0x54cd28, "GetAddr error `src_addr'"),
                    log_reference(e, 0x54cd4a, "GetAddr error `dst_addr'"),
                    log_reference(e, 0x54cd6c, "GetAddr error `work_addr'")],
                soft_focus_submit_calls=[call(e, 0x54ce4e, 0x7d4d6a, 'bl'),
                                         call(e, 0x7d4d9a, 0x54a7a4, 'bl')],
                artfilter_original=art, resize_type=resize,
                artfilter_resize_calls=[call(e, 0x6b5076, 0x6b4f6a, 'bl'),
                                        call(e, 0x6b5028, 0x12a1c0, 'bl'),
                                        call(e, 0x6b5030, 0x6b95e8, 'bl')],
                offsets_are='AV-CAM file offsets; not Linux pointers',
                runtime_called=False, pixels_modified=False,
                limitation='Names/call instructions identify candidates only; no writable-frame ABI or coexistence with FL3 is proven')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--object-library', type=Path, required=True)
    p.add_argument('--trace', type=Path)
    p.add_argument('--avcam', type=Path)
    p.add_argument('--out', type=Path, default=ROOT / '.lab/yc-route-audit')
    a = p.parse_args()
    result = audit(a.object_library, a.trace)
    if a.avcam:
        result['avcam_candidates'] = avcam_candidates(a.avcam)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'proof.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('observed_route', 'decoder_helper_direct_callers',
                                           'live_view_producer_verified', 'capture_before_encode_verified')}, indent=2))
    if a.avcam:
        print('AV-CAM JPEG descriptor, SyncYCOut and SA display selector references verified locally')
    print(a.out / 'proof.json')


if __name__ == '__main__':
    main()
