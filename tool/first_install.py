"""Stock-only installation transaction, driven by an explicit GUI confirmation.

No device access on import, no automatic firmware retry, no upgrade fallback.
The transport is injectable for tests; production uses the real libusb session.
"""
import hashlib,io,json,os,re,secrets,struct,threading,time,zipfile
from pathlib import Path
import usb_transport
from backend import HOME
from stock_install_bundle import read_bundle,PINS,MODULE_SHA


def sha(raw):return hashlib.sha256(raw).hexdigest()


def save(path,raw):
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    if path.read_bytes()!=raw:raise OSError('本地备份回读失败')


def save_json(path,value):save(path,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())


def load_package(raw,expected):
    if not re.fullmatch('[0-9a-fA-F]{64}',expected) or sha(raw)!=expected.lower():
        raise ValueError('必须填写候选包的完整 SHA-256，且与文件一致')
    if len(raw)>16*1024*1024:raise ValueError('安装候选包过大')
    names={'install-manifest.json','candidate.zip','stage.so','wbi-probe.so','wbi-template.so'}
    names|={p+'/'+m+'.so' for p in ('icons','config','loader') for m in ('preflight','activate','recover')}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if (len(z.infolist())!=len(names) or set(z.namelist())!=names or
                sum(i.file_size for i in z.infolist())>24*1024*1024 or
                any(i.flag_bits&1 or (i.external_attr>>16)&0xf000==0xa000 for i in z.infolist())):
            raise ValueError('安装包内容不匹配')
        files={n:z.read(n) for n in names}
    m=json.loads(files.pop('install-manifest.json'))
    if (m.get('kind')!='a7m3-stock-installer-experimental-v1' or m.get('model')!='ILCE-7M3' or
            m.get('firmware')!='4.04' or m.get('hardware_verified') is not False or
            m.get('sha256')!={n:sha(v) for n,v in files.items()}):raise ValueError('安装候选清单或散列不符')
    _,deltas,module=read_bundle(io.BytesIO(files['candidate.zip']))
    if sha(files['stage.so'])!=m['stage']['payload_sha256']:raise ValueError('暂存程序不符')
    profiles=m['activation']['profiles']
    if [p['name'] for p in profiles]!=['icons','config','loader']:raise ValueError('激活顺序不符')
    for p in profiles:
        target={'icons':'/share/app/image_cmn_43.uxc','config':'/lib/CautionConfig.so','loader':'/lib/viewUnified2.so'}[p['name']]
        if p['path']!='/usr'+target or (p['before_sha256'],p['after_sha256'])!=PINS[target]:raise ValueError('激活目标不符')
        for mode,meta in p['payloads'].items():
            if sha(files[p['name']+'/'+mode+'.so'])!=meta['sha256']:raise ValueError('激活程序不符')
    if m['stage']['candidate_sha256']!=sha(files['candidate.zip']) or m['activation']['candidate_sha256']!=sha(files['candidate.zip']):
        raise ValueError('各阶段不属于同一候选')
    w=m['wbi'];offset=w['offset']
    if type(offset) is not int or offset<0 or w['bytes']!=1024 or sha(files['wbi-template.so'][offset:offset+1024])!=w['marker_sha256']:
        raise ValueError('WBI 绑定槽不符')
    return m,files,deltas


def wbi_report(raw):
    if len(raw)!=1112:raise ValueError('WBI 报告长度不符')
    v=struct.unpack('<3I2i9I',raw[:56])
    if v[0]!=0x57423741 or v[1]!=1 or v[4]!=0 or v[6:8]!=(0x03c00000,0) or v[13]:raise ValueError('WBI 身份或容量校验失败')
    if sha(raw[88:])!=raw[56:88].hex():raise ValueError('WBI 前像散列不符')
    if v[8]==0 and v[10]!=0:raise ValueError('只读 WBI 返回写入记录')
    data=raw[88:]
    if v[3]==1:
        if v[8]!=0 or data[:512]!=bytes(512):raise ValueError('WBI 空头判断不符')
    elif v[3]==0:
        if data[:4] not in (b'WBI0',b'WBI1') or struct.unpack_from('<I',data,20)[0]!=512:raise ValueError('不认识的 WBI 结构')
    else:raise ValueError('WBI 检查未通过')
    return v,data


def inspect_device(camera,factory,files,folder,progress):
    # Identity has already been checked inside the same authenticated transport.
    for path in ('/usr/lib/a7fl.so','/setting/A7FL.INSTALL'):
        if factory.read(path)[0]!=factory.missing:raise ValueError('已有安装或未完成事务，不能使用原厂首装：'+path)
    original={}
    for p,(before,_) in PINS.items():
        progress('备份原厂文件：'+Path(p).name)
        raw=factory.contents('/usr'+p)
        if sha(raw)!=before:raise ValueError('不是匹配的原厂文件：'+p+'；未发送固件写入')
        save(folder/Path(p).name,raw);original[p]=raw
    for name in ('A7FL0.CFG','A7FL1.CFG','A7FW0.CFG','A7FW1.CFG','A7CU0.CFG','A7CU1.CFG'):
        if factory.read('/setting/'+name)[0]!=factory.missing:raise ValueError('发现项目配置，本工具不覆盖已有改装机')
    from pmca.backup import BackupFile
    settings=camera.getBackupPresetData(True)
    if not 4096<len(settings)<16*1024*1024:raise ValueError('机身设置备份长度异常')
    b=BackupFile(io.BytesIO(settings))
    if b.revision!=4 or b.size!=len(settings):raise ValueError('机身 BK4 备份不完整')
    save(folder/'settings.bin',settings)
    raw=factory.run(files['wbi-probe.so'],'a7wbi.bin');v,data=wbi_report(raw)
    save(folder/'wbi-readonly.bin',raw)
    save_json(folder/'backup.json',dict(files={p:sha(v) for p,v in original.items()},settings_sha256=sha(settings),wbi_sha256=sha(data),pid=v[5]))
    return original,v,data


def write_device(factory,m,files,original,wbi,folder,progress):
    initial,data=wbi
    # Full preimages again after the user reviewed the backup; still one USB session.
    for p,raw in original.items():
        if factory.contents('/usr'+p)!=raw:raise ValueError('确认期间前像变化，未写入')
    fresh=factory.run(files['wbi-probe.so'],'a7wbi.bin');v,fresh_data=wbi_report(fresh)
    if fresh_data!=data or v[5]!=initial[5]:raise ValueError('WBI 或相机进程变化，未写入')
    save_json(folder/'write-intent.json',dict(candidate=m['sha256'],pid=v[5],automatic_retry=False))
    progress('写入模块和语言资源')
    raw=factory.run(files['stage.so'],'a7stockstage.bin');save(folder/'stage-report.bin',raw)
    if len(raw)!=72:raise ValueError('暂存报告长度不符；停止')
    s=struct.unpack('<6I4i32s',raw)
    if s[0:3]!=(0x41374649,1,100) or s[6]!=0 or s[9]!=1 or s[10].hex()!=m['stage']['bundle_sha256']:
        raise ValueError('模块/语言暂存未通过，保留记录，停止')
    for p in m['activation']['profiles']:
        name=p['name'];progress('检查并激活：'+name)
        mask=(1<<len(p['page_offsets']))-1
        for mode in ('preflight','activate'):
            raw=factory.run(files[name+'/'+mode+'.so'],'a7stockact.bin');save(folder/(name+'-'+mode+'.bin'),raw)
            if len(raw)!=80:raise ValueError('激活报告长度不符')
            r=struct.unpack('<8I4i32s',raw)
            if (r[0]!=0x41374e41 or r[1]!=1 or r[3]!=initial[5] or r[8]!=0 or r[11]!=1 or
                    r[12].hex()!=p['bundle_sha256'] or r[2]!=(3 if mode=='preflight' else 100) or
                    (mode=='activate' and (r[6],r[7])!=(mask,mask))):
                raise ValueError(name+' 激活检查未通过，停止；不自动重试')
        if sha(factory.contents(p['path']))!=p['after_sha256']:raise ValueError(name+' 独立回读失败')
    # Only invalidate a known WBI snapshot after every filesystem target verified.
    if initial[3]==0:
        progress('绑定本机 WBI 前像，处理旧启动快照')
        template=bytearray(files['wbi-template.so']);at=m['wbi']['offset'];template[at:at+1024]=data
        save(folder/'bound-wbi.so',bytes(template))
        raw=factory.run(bytes(template),'a7wbi.bin');save(folder/'wbi-write.bin',raw)
        r,seen=wbi_report(raw)
        if r[3]!=0 or r[2]!=100 or r[8]!=1 or r[5]!=initial[5] or r[10:13]!=(512,1,1) or seen!=data:
            raise ValueError('WBI 写入未完整通过；停止，不自动重试')
    raw=factory.run(files['wbi-probe.so'],'a7wbi.bin');save(folder/'wbi-final.bin',raw)
    r,final=wbi_report(raw)
    if r[3]!=1 or final[:512]!=bytes(512) or final[512:]!=data[512:] or r[5]!=initial[5]:raise ValueError('最终 WBI 回读不符')
    for p,(_,after) in PINS.items():
        if sha(factory.contents('/usr'+p))!=after:raise ValueError('最终文件回读失败：'+p)
    if sha(factory.contents('/usr/lib/a7fl.so'))!=MODULE_SHA:raise ValueError('最终模块回读失败')
    result=dict(written_and_readback=True,cold_boot_verified=False,pid=initial[5])
    save_json(folder/'written-awaiting-cold-boot.json',result)
    return result


class Installer:
    def __init__(self,transport=usb_transport.connect,backup_root=None):
        self.transport=transport;self.root=backup_root or Path.home()/'Documents'/'A7M3 Tool Backups'
        self.lock=threading.Lock();self.decision=threading.Event();self.confirmed=False
        self.state={'phase':'idle','messages':[]};self.thread=None
    def snapshot(self):
        with self.lock:return json.loads(json.dumps(self.state))
    def update(self,**values):
        with self.lock:self.state.update(values)
    def message(self,text):
        with self.lock:self.state['messages'].append(text)
    def active(self):return self.snapshot()['phase'] in ('checking','ready','writing')
    def start(self,raw,expected,allow_switch):
        m,files,deltas=load_package(raw,expected)
        with self.lock:
            if self.thread is not None and self.thread.is_alive():raise ValueError('已有相机任务进行中')
            job=secrets.token_hex(12);self.state=dict(job=job,phase='checking',messages=[],hardware_verified=False)
            self.decision.clear();self.confirmed=False
            def run():
                folder=self.root/(time.strftime('%Y%m%d-%H%M%S')+'-'+job)
                try:
                    folder.mkdir(parents=True,exist_ok=False);self.update(backup=str(folder))
                    save(folder/'candidate.zip',raw);save_json(folder/'install-manifest.json',m)
                    with self.transport(allow_switch=allow_switch,progress=self.message) as (camera,factory):
                        original,v,data=inspect_device(camera,factory,files,folder,self.message)
                        self.update(phase='ready');self.message('备份和原厂前像通过。等待确认，10 分钟内可取消。')
                        if not self.decision.wait(600) or not self.confirmed:
                            self.update(phase='cancelled');return
                        self.update(phase='writing')
                        result=write_device(factory,m,files,original,(v,data),folder,self.message)
                        self.update(phase='awaiting-cold-boot',result=result)
                except Exception as exc:
                    self.update(phase='error',error=str(exc))
                    if folder.is_dir():save_json(folder/'error.json',dict(error=str(exc),no_automatic_retry=True))
            self.thread=threading.Thread(target=run,daemon=True);self.thread.start()
        return {'job':job}
    def decide(self,job,confirm):
        with self.lock:
            if self.state.get('job')!=job or self.state['phase']!='ready' or self.decision.is_set():raise ValueError('没有待确认的备份任务')
            self.confirmed=confirm;self.decision.set()
        return {'ok':True}
