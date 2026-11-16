"""Temporarily query mounted Fsys drives; no persistent camera writes."""
import sys,subprocess,time,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from camera import service,handoff
from local import LAB,BUILD_ID,require

def main():
    out=LAB/'sd-fsys-probe'/str(time.time_ns());out.mkdir(parents=True)
    module=out/'probe.so'
    subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft',
        '-fPIC','-Os','-nostdlib','-shared','-Wall','-Wextra','-Werror',
        '-Wl,-z,noexecstack',str(ROOT/'research/sd_fsys_probe.c'),'-o',str(module)],check=True)
    def collect(camera,action):
        require(action=='settings-snapshot','Unexpected action')
        f=service.Factory(camera)
        require(f.contents('/version.txt')==BUILD_ID,'Wrong firmware')
        require(bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong model')
        raw=f.run(module.read_bytes(),'sdfsys.bin');(out/'report.bin').write_bytes(raw)
        require(len(raw)==124+12+12288+20,'Invalid report')
        magic,status,drives=struct.unpack_from('<IiI',raw)
        require(magic==0x53444653,'Wrong magic')
        print('FSYS_READ_ONLY',status,hex(drives),'EVIDENCE',out)
        print('LISTING',struct.unpack_from('<3i',raw,124))
        print('OPEN_READ_CLOSE',struct.unpack_from('<9i',raw,12))
        print('B_CONTENT',repr(raw[73:98]))
        print('ENDS_EOF_ERROR',struct.unpack_from('<5i',raw,12424))
        for i in range(3):
            print(chr(65+i),[raw[136+i*4096+j*256:136+i*4096+(j+1)*256].split(b'\0')[0] for j in range(16)])
    service.perform=collect;handoff.SWITCH+=' --host-identity-check'
    handoff.run('settings-snapshot')
if __name__=='__main__':main()
