"""Verified creative-menu sector update; distinct from the old title-only flash."""
import io
import json
import os
import struct
import subprocess
import time

from pmca.backup import BackupFile
from local import LAB, ROOT, file_sha, require, sha
from camera.menu_ram import EXPECTED, payload as menu_payload, save

OUT=LAB/'creative-flash'


def configure(action):
    global OUT
    correction={'creative-fix':'fix','creative-read-fix':'read','creative-verify-fix':'verify',
                'creative-restore-fix':'restore'}
    identity={'creative-identity':'identity','creative-read-identity':'read',
              'creative-verify-identity':'verify','creative-restore-identity':'restore'}
    icons={'creative-icons':'icons','creative-read-icons':'read','creative-verify-icons':'verify','creative-restore-icons':'restore'}
    icons_list={'creative-icons-list':'icons-list','creative-read-icons-list':'read',
                'creative-verify-icons-list':'verify','creative-restore-icons-list':'restore'}
    icons_display={'creative-icons-display':'icons-display','creative-read-icons-display':'read',
                  'creative-verify-icons-display':'verify','creative-restore-icons-display':'restore'}
    if action in icons_display:
        OUT=LAB/'creative-icons-display'
        return icons_display[action]
    if action in icons_list:
        OUT=LAB/'creative-icons-list'
        return icons_list[action]
    if action in icons:
        OUT=LAB/'creative-icons'
        return icons[action]
    if action in identity:
        OUT=LAB/'creative-v3'
        return identity[action]
    OUT=LAB/('creative-v2' if action in correction else 'creative-flash')
    return correction.get(action,action.removeprefix('creative-'))


def verified(check_image=False):
    manifest=json.loads((OUT/'manifest.json').read_text())
    proof=json.loads((OUT/'qemu-proof.json').read_text())
    require(proof['manifest_sha256']==file_sha(OUT/'manifest.json'), '烧录测试与镜像清单不符。')
    native_directory=manifest.get('native_directory','menu-persistent')
    require(native_directory in ('menu-persistent','menu-lazy','menu-identity','menu-icons','style-icons-list','menu-icons-display'),'未知原厂补丁测试目录。')
    native=LAB/native_directory/'proof.json'
    require(file_sha(native)==manifest['native_proof_sha256'], '原厂菜单测试记录发生变化。')
    native_proof=json.loads(native.read_text())
    for record in (manifest,proof,native_proof):
        for name,digest in record['source_sha256'].items():
            require(file_sha(ROOT/name)==digest, f'测试后源码发生变化：{name}')
    require((manifest['model'],manifest['firmware'],manifest['partition'])==
            ('ILCE-7M3','4.04','/dev/nflasha15'), '烧录目标不符。')
    offsets=manifest['sectors']
    require(1<len(offsets)<=32 and len(set(offsets))==len(offsets) and
            all(2048<=o<300*1024*1024 and o%512==0 for o in offsets) and
            offsets[-1]==manifest['activation_sector'], '扇区范围或激活顺序异常。')
    for name,digest in manifest['blobs'].items():
        require(file_sha(OUT/name)==digest, f'补丁数据发生变化：{name}')
    require((OUT/'offsets.bin').read_bytes()==struct.pack('<'+'I'*len(offsets),*offsets), '扇区表不符。')
    require(all((OUT/f'{name}.bin').stat().st_size==512*len(offsets) for name in ('before','after')),
            '扇区数据长度不符。')
    if check_image:
        image=OUT/'a7m3-retro-wardrobe.img'
        require(image.stat().st_size==300*1024*1024 and file_sha(image)==manifest['image_sha256'], '镜像校验失败。')
        check=subprocess.run(['/opt/homebrew/opt/e2fsprogs/sbin/e2fsck','-fn',str(image)],capture_output=True,text=True)
        require(check.returncode==0, 'ext2 独立检查未通过：'+check.stdout+check.stderr)
        expected={name:record['after_sha256'] for name,record in manifest['files'].items()}
        require(json.loads((OUT/'debugfs-proof.json').read_text())==expected, '独立文件导出校验缺失。')
        print('CREATIVE_IMAGE_EXT2_VERIFIED',flush=True)
    return manifest,proof


def payload(name):
    _,proof=verified()
    require(name in ('read','write','restore'), '未知创意风格操作。')
    data=(OUT/f'{name}.so').read_bytes()
    require(0<len(data)<=32768 and data[:7]==b'\x7fELF\x01\x01\x01' and data[16:20]==b'\x03\0(\0' and
            sha(data)==proof['payloads'][name], '载荷与已测试的 ARM 共享库不符。')
    return data


def inspect_payload():
    directory=LAB/'creative-inspection'
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    obj=directory/'inspect.o';target=directory/'inspect.so'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC',
                    '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables',
                    '-fno-asynchronous-unwind-tables','-c',str(ROOT/'payloads/a7-creative-inspect.c'),'-o',str(obj)],check=True)
    subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(obj),'-o',str(target)],check=True)
    data=target.read_bytes()
    require(len(data)<=16384 and data[:7]==b'\x7fELF\x01\x01\x01','只读探针格式异常。')
    return data


def identity_inspect_payload():
    directory=LAB/'identity-inspection'
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    obj=directory/'inspect.o';target=directory/'inspect.so'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC',
                    '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables',
                    '-fno-asynchronous-unwind-tables','-c',str(ROOT/'payloads/a7-identity-inspect.c'),'-o',str(obj)],check=True)
    subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(obj),'-o',str(target)],check=True)
    data=target.read_bytes()
    require(len(data)<=16384 and data[:7]==b'\x7fELF\x01\x01\x01','只读探针格式异常。')
    return data


def display_inspect_payload():
    directory=LAB/'display-inspection'
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    obj=directory/'inspect.o';target=directory/'inspect.so'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-fPIC',
                    '-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables',
                    '-fno-asynchronous-unwind-tables','-c',str(ROOT/'payloads/a7-display-inspect.c'),'-o',str(obj)],check=True)
    subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(obj),'-o',str(target)],check=True)
    data=target.read_bytes()
    require(len(data)<=16384 and data[:7]==b'\x7fELF\x01\x01\x01','显示路径只读探针格式异常。')
    return data


def direct_image_hash(factory,record,stem,phase='after'):
    directory=LAB/'image-hash'
    proof=json.loads((directory/'proof.json').read_text())
    for path,digest in proof['source_sha256'].items():
        require(file_sha(ROOT/path)==digest,'图标直接回读测试源码发生变化：'+path)
    data=(directory/'hash.so').read_bytes()
    require(len(data)<=16384 and data[:7]==b'\x7fELF\x01\x01\x01' and
            sha(data)==proof['payload_sha256'],'图标只读散列探针与测试不符。')
    raw=factory.run(data,'a7imagehash.bin')
    save(stem.with_suffix('.image-hash.bin'),raw)
    require(len(raw)==44,'图标直接回读报告长度异常。')
    magic,status,size=struct.unpack_from('<IiI',raw)
    require(phase in ('before','after'),'未知图标回读阶段。')
    require(magic==0x41374948 and status==0 and size==record[phase+'_bytes'] and
            raw[12:].hex()==record[phase+'_sha256'],'图标文件直接回读 SHA-256 不符。')
    print(f'LIVE_CREATIVE_IMAGE_DIRECT_HASH_VERIFIED bytes={size} sha256={raw[12:].hex()}',flush=True)


def report(factory,name,stem):
    manifest,_=verified()
    raw=factory.run(payload(name),'a7creative.bin')
    save(stem.with_suffix('.bin'),raw)
    require(len(raw)==40+512*len(manifest['sectors']), '烧录报告长度异常。')
    keys=('magic','action','status','error','capacity','header_ok','preimage','written','readback_ok','rollback_ok')
    result=dict(zip(keys,struct.unpack_from('<10i',raw)))
    save(stem.with_suffix('.json'),(json.dumps(result,indent=2)+'\n').encode())
    print('LIVE_CREATIVE_SECTOR_REPORT '+json.dumps(result),flush=True)
    require(result['magic']==0x41374346 and result['action']==('read','write','restore').index(name) and
            result['status']==1 and result['error']==0 and result['capacity']==300*1024*1024 and
            result['header_ok']==1 and result['readback_ok']==1, '扇区操作未通过，已保存完整回读报告。')
    if name!='read':
        require(raw[40:]==(OUT/('after.bin' if name=='write' else 'before.bin')).read_bytes(), '扇区回读不符。')
    return result,raw[40:]


def perform(camera,factory,action):
    directory=LAB/'creative-live'
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    stem=directory/f'{action}-{time.time_ns()}'
    manifest,_=verified()
    if action=='inspect':
        raw=factory.run(inspect_payload(),'a7inspect.bin')
        save(stem.with_suffix('.inspect.bin'),raw)
        require(len(raw)==2556,'代码诊断报告长度异常。')
        head=struct.unpack_from('<4I',raw)
        print('LIVE_CREATIVE_MEMORY_LAYOUT '+json.dumps(dict(zip(('magic','base','status','count'),head))),flush=True)
        print('LIVE_CREATIVE_MEMORY_CODE sha256='+sha(raw[56:714]),flush=True)
        print('LIVE_CREATIVE_MEMORY_HOOK '+raw[716:720].hex()+' INIT '+raw[720:724].hex(),flush=True)
        print('LIVE_CREATIVE_MEMORY_CREATE '+raw[2552:2556].hex(),flush=True)
        english=factory.contents('/usr/share/app/string_english.uxc',maximum=manifest['files']['/share/app/string_english.uxc']['after_bytes']+16)
        save(stem.with_suffix('.english.uxc'),english)
        print(f'LIVE_CREATIVE_ENGLISH bytes={len(english)} sha256={sha(english)}',flush=True)
        print(f'LIVE_CREATIVE_INSPECTION_SAVED {stem}',flush=True)
        return
    if action in ('flash','fix','identity','icons','icons-list','icons-display'):
        settings=camera.getBackupPresetData(True)
        backup=BackupFile(io.BytesIO(settings))
        require(backup.revision==4 and backup.size==len(settings), '设置备份不完整。')
        save(stem.with_suffix('.settings.bin'),settings)
        expected=EXPECTED if action=='flash' else {k:EXPECTED[k] for k in (0x0107075e,0x01070a11,0x01070a17,0x01070a1d)}
        require(all(backup.getProperty(k).data==v for k,v in expected.items()), '机身配方与实测配置不符。')
        if action in ('identity','icons','icons-list','icons-display'):
            # Both full file preimages and the running previous helper are required.
            # The sector payload independently checks every changed sector again.
            previous=None
            for path in (manifest['files'] if action in ('icons','icons-list','icons-display') else ('/lib/viewUnified2.so','/lib/CautionConfig.so')):
                record=manifest['files'][path]
                if path=='/share/app/image_cmn_43.uxc':
                    direct_image_hash(factory,record,stem,phase='before')
                    continue
                data=factory.contents('/usr'+path,maximum=record['before_bytes']+16)
                require(len(data)==record['before_bytes'] and sha(data)==record['before_sha256'],
                        '机身文件不是此修复需要的上一版：'+path)
                save(stem.with_name(stem.name+'-'+path.rsplit('/',1)[-1]+'.before'),data)
                if path.endswith('viewUnified2.so'):previous=data
            native=factory.run(inspect_payload(),'a7inspect.bin')
            save(stem.with_suffix('.memory-before.bin'),native)
            require(len(native)==2556 and struct.unpack_from('<4I',native)[2:]==(3,20) and
                    native[56:714]==previous[0x5b98dc:0x5b9b6e], '运行内存与更新前的已验证版本不符。')
            report(factory,'write',stem)
            print(f'LIVE_CREATIVE_{action.upper()}_READBACK_VERIFIED image_sha256={manifest["image_sha256"]}',flush=True)
            return
        if action=='fix':
            native=factory.run(inspect_payload(),'a7inspect.bin')
            save(stem.with_suffix('.memory-before.bin'),native)
            previous=(LAB/'creative-v1/viewUnified2.so').read_bytes()
            prior=json.loads((LAB/'creative-v1/manifest.json').read_text())
            require(sha(previous)==prior['files']['/lib/viewUnified2.so']['after_sha256'], '前一版库的备份校验失败。')
            require(len(native)==2556 and struct.unpack_from('<4I',native)[2:]==(3,19) and
                    native[56:714]==previous[0x5b98dc:0x5b9b6e], '运行内存与已定位的前一版状态不符。')
            report(factory,'write',stem)
            print(f'LIVE_CREATIVE_FIX_READBACK_VERIFIED image_sha256={manifest["image_sha256"]}',flush=True)
            return
        # Require the actual RAM entry's UI dispatch witness before the first installation.
        native=factory.run(menu_payload('inspect'),'a7menu.bin')
        save(stem.with_suffix('.ram-before.bin'),native)
        require(len(native)==48, '原厂菜单调用报告缺失。')
        values=struct.unpack('<11Ii',native)
        require(values[0]==0x41374d54 and values[1:3]==(1,2) and values[6]==20 and
                values[7]>0 and values[8:12]==(98,3,3,0), '没有确认新增入口的真机选择记录。')
        restored=factory.run(menu_payload('restore'),'a7menu.bin')
        save(stem.with_suffix('.ram-restored.bin'),restored)
        require(len(restored)==48 and struct.unpack('<11Ii',restored)[1:3]==(2,3) and
                struct.unpack('<11Ii',restored)[5:7]==(0,19) and struct.unpack('<11Ii',restored)[11]==0,
                '临时内存补丁未恢复。')
        print('LIVE_RAM_EXPERIMENT_RESTORED',flush=True)
        report(factory,'write',stem)
        print(f'LIVE_CREATIVE_FLASH_READBACK_VERIFIED image_sha256={manifest["image_sha256"]}',flush=True)
    elif action=='restore':
        report(factory,'restore',stem)
        print('LIVE_CREATIVE_ORIGINAL_SECTORS_RESTORED',flush=True)
    else:
        result,data=report(factory,'read',stem)
        if action=='verify':
            require(data==(OUT/'after.bin').read_bytes(), '机身扇区不是创意风格补丁。')
            view_bytes=None
            for path,record in manifest['files'].items():
                if path=='/share/app/image_cmn_43.uxc':
                    # The camera can retain pre-update resource-header pages even
                    # after power cycling. Hash the ENTIRE file using O_DIRECT;
                    # do not mask differences or patch bytes before hashing.
                    direct_image_hash(factory,record,stem)
                    continue
                contents=factory.contents('/usr'+path,maximum=record['after_bytes']+16)
                if len(contents)!=record['after_bytes'] or sha(contents)!=record['after_sha256']:
                    save(stem.with_name(stem.name+'-'+path.rsplit('/',1)[-1]+'.mismatch'),contents)
                    print(f'LIVE_CREATIVE_FILE_MISMATCH {path} bytes={len(contents)} sha256={sha(contents)}',flush=True)
                require(len(contents)==record['after_bytes'] and sha(contents)==record['after_sha256'],
                        f'重启后文件校验不符：{path}')
                if path=='/lib/viewUnified2.so':view_bytes=contents
                print(f'LIVE_CREATIVE_FILE_VERIFIED {path} sha256={sha(contents)}',flush=True)
            if OUT.name in ('creative-v2','creative-v3','creative-icons','creative-icons-list','creative-icons-display'):
                native=factory.run(inspect_payload(),'a7inspect.bin')
                save(stem.with_suffix('.memory.bin'),native)
                require(len(native)==2556 and struct.unpack_from('<4I',native)[2:]==(3,20) and
                        native[56:714]==view_bytes[0x5b98dc:0x5b9b6e] and
                        native[716:720]==view_bytes[0x5b9fba:0x5b9fbe] and
                        native[2552:2556]==view_bytes[0x5bb266:0x5bb26a], '运行代码或菜单数量不符。')
                entry=struct.unpack_from('<10I',native,724+190*4)
                require(entry[2:4]==(98,0x0204ed84),'新增菜单记录不符。')
                if OUT.name in ('creative-icons','creative-icons-list','creative-icons-display'):
                    expected_icons=(0x0205c87e,0x0205c823) if OUT.name=='creative-icons-display' else (0x0205c049,0x0205c04a)
                    require((entry[4],entry[8])==expected_icons,'RW 大小图标引用不符。')
                    print('LIVE_CREATIVE_RW_ICON_REFERENCES_VERIFIED',flush=True)
                if OUT.name=='creative-icons-display':
                    display=factory.run(display_inspect_payload(),'a7display.bin')
                    save(stem.with_suffix('.display.bin'),display)
                    require(len(display)==20 and struct.unpack_from('<I',display)[0]==0x41374449 and
                            struct.unpack_from('<I',display,8)[0]==1 and
                            display[12:16]==view_bytes[0x5b9e36:0x5b9e3a] and
                            display[16:20]==view_bytes[0x5bb998:0x5bb99c],
                            '显示路径尚未完整加载，请断电重启后回读。')
                    print('LIVE_CREATIVE_DISPLAY_HOOKS_VERIFIED',flush=True)
                settings=camera.getBackupPresetData(True)
                backup=BackupFile(io.BytesIO(settings))
                require(backup.revision==4 and backup.size==len(settings),'重启后设置备份不完整。')
                save(stem.with_suffix('.settings.bin'),settings)
                require(all(backup.getProperty(k).data==v for k,v in EXPECTED.items()), '重启后配方保存参数不符。')
                print('LIVE_CREATIVE_RUNTIME_MENU_AND_RECIPE_VERIFIED count=20 id=98 style_box=3 C=1 S=-1 H=-1',flush=True)
                if OUT.name in ('creative-v3','creative-icons','creative-icons-list','creative-icons-display'):
                    identity=factory.run(identity_inspect_payload(),'a7identity.bin')
                    save(stem.with_suffix('.identity.bin'),identity)
                    require(len(identity)==28 and struct.unpack_from('<I',identity)[0]==0x41374944 and
                            struct.unpack_from('<I',identity,12)[0]==7 and
                            identity[16:20]==view_bytes[0x5bb18e:0x5bb192] and
                            identity[20:24]==view_bytes[0x5bb9de:0x5bb9e2] and
                            struct.unpack_from('<I',identity,24)[0]==0x0204ed84,
                            '名称或光标恢复逻辑尚未加载，请完整断电重启后再验证。')
                    print('LIVE_CREATIVE_IDENTITY_RUNTIME_VERIFIED cursor_hooks=2 fn_resource=0x0204ed84',flush=True)
            print('LIVE_CREATIVE_REBOOT_VERIFIED',flush=True)
