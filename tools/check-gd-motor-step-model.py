#!/usr/bin/env python3
"""Bounded stock-versus-candidate motor step state/FP/MMIO/ABI gate."""
import argparse,copy,hashlib,io,json,random,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
ENTRY,RAM,TIMER,STACK,STOP=0x08001670,0x24000020,0x4000e024,0x2400ff00,0x10000000
EXTENT,NAME,STOCK_MD5=156,'mclib_gpio_step','fb64911bac422a27d7ed7fab3597603f'
def sha(data):return hashlib.sha256(data).hexdigest()
def inputs(report_path,report_override=None,elf_override=None):
    report_blob=report_path.read_bytes()
    report=json.loads(report_blob) if report_override is None else report_override
    for filename,digest in report['source_sha256'].items():
        if sha((ROOT/filename).read_bytes())!=digest:raise ValueError('stale source: '+filename)
    compiler=Path(report['compiler'])
    if sha(compiler.read_bytes())!=report['compiler_sha256']:raise ValueError('stale compiler')
    stock=(ROOT/'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    if hashlib.md5(stock).hexdigest()!=STOCK_MD5 or report['stock_md5']!=STOCK_MD5:
        raise ValueError('unexpected stock image')
    rows=[row for row in report['results'] if row['name']==NAME]
    if len(rows)!=1:raise ValueError('missing or ambiguous step row')
    row=rows[0];elf_path=report_path.parent/(NAME+'.elf')
    elf_blob=elf_path.read_bytes() if elf_override is None else elf_override
    elf=ELFFile(io.BytesIO(elf_blob));section=elf.get_section_by_name('.text')
    symbols=elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    candidate=section.data();expected=stock[ENTRY-0x08000000:ENTRY-0x08000000+EXTENT]
    if (len(symbols)!=1 or symbols[0]['st_info']['type']!='STT_FUNC'
            or symbols[0]['st_value']!=ENTRY|1 or symbols[0]['st_size']!=len(candidate)
            or elf.header['e_entry']!=ENTRY|1 or section['sh_addr']!=ENTRY
            or row['address']!=ENTRY or row['expected_size']!=EXTENT
            or not 0<len(candidate)<=EXTENT or row['actual_size']!=len(candidate)
            or row['candidate_sha256']!=sha(candidate) or row['expected_sha256']!=sha(expected)):
        raise ValueError('step extent, entry, ELF or digest mismatch')
    return expected,candidate,dict(
        isolated_report=str(report_path),isolated_report_sha256=sha(report_blob),
        source_sha256=report['source_sha256'],compiler=str(compiler),compiler_sha256=report['compiler_sha256'],
        flags=report['flags'],stock_md5=STOCK_MD5,stock_sha256=sha(stock),
        expected_sha256=sha(expected),candidate_sha256=sha(candidate),
        elf_sha256={str(elf_path):sha(elf_blob)},checker_sha256=sha(Path(__file__).read_bytes()),
        unicorn_version=unicorn.__version__)

def self_test(path):
    inputs(path)
    original=json.loads(path.read_bytes())
    tests=[]
    def reject(label,report=None,elf=None):
        try:inputs(path,report,elf)
        except ValueError:tests.append(label)
        else:raise AssertionError('accepted '+label)
    for key in ['compiler_sha256','stock_md5']:
        bad=copy.deepcopy(original);bad[key]='0'*32;reject(key,bad)
    bad=copy.deepcopy(original);filename=next(iter(bad['source_sha256']))
    bad['source_sha256'][filename]='0'*64;reject('source_sha256',bad)
    for key in ['address','expected_size','actual_size','candidate_sha256','expected_sha256']:
        bad=copy.deepcopy(original);row=next(row for row in bad['results'] if row['name']==NAME)
        row[key]=row[key]+2 if isinstance(row[key],int) else '0'*64
        reject(key,bad)
    elf=bytearray((path.parent/(NAME+'.elf')).read_bytes())
    struct.pack_into('<I',elf,24,ENTRY+3);reject('shifted ELF entry',elf=bytes(elf))
    original_elf=(path.parent/(NAME+'.elf')).read_bytes()
    parsed=ELFFile(io.BytesIO(original_elf));table=parsed.get_section_by_name('.symtab')
    symbol_index=next(i for i,symbol in enumerate(table.iter_symbols()) if symbol.name==NAME)
    symbol_offset=table['sh_offset']+symbol_index*table['sh_entsize']
    for label,offset,value in [('shifted symbol',4,ENTRY+3),('shortened symbol',8,EXTENT-2)]:
        bad=bytearray(original_elf);struct.pack_into('<I',bad,symbol_offset+offset,value)
        reject(label,elf=bytes(bad))
    section_index=next(i for i,section in enumerate(parsed.iter_sections()) if section.name=='.text')
    section=parsed.get_section_by_name('.text')
    bad=bytearray(original_elf)
    struct.pack_into('<I',bad,parsed.header['e_shoff']+section_index*parsed.header['e_shentsize']+12,ENTRY+2)
    reject('shifted section',elf=bytes(bad))
    bad=bytearray(original_elf);bad[section['sh_offset']]^=1
    reject('changed candidate byte',elf=bytes(bad))
    print(f'{len(tests)}/{len(tests)} provenance/extent/entry rejection self-tests PASS.')
def u32(data,offset):return struct.unpack_from('<I',data,offset)[0]
def h16(data,offset):return struct.unpack_from('<H',data,offset)[0]
def put32(data,offset,value):struct.pack_into('<I',data,offset,value&0xffffffff)
class Runner:
    def __init__(self,code):
        self.cpu=c=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        for addr,size in [(0x08000000,0x10000),(0x24000000,0x10000),(0x4000e000,0x1000),(STOP,0x1000)]:c.mem_map(addr,size)
        c.mem_write(ENTRY,code);c.reg_write(UC_ARM_REG_C1_C0_2,0xf<<20);c.reg_write(UC_ARM_REG_FPEXC,1<<30)
        def guard(cpu,addr,size,_):assert ENTRY<=addr and addr+size<=ENTRY+len(code),hex(addr)
        def read(cpu,access,addr,size,value,_):
            if RAM<=addr and addr+size<=RAM+792:
                key=(addr-RAM,size);self.reads[key]=self.reads.get(key,0)+1
                self.accesses.append(('r','state',addr-RAM,size,int.from_bytes(cpu.mem_read(addr,size),'little')))
            elif addr==TIMER and size==4:
                value=u32(cpu.mem_read(addr,size),0)
                self.mmio.append(('r',addr,size,value))
                self.accesses.append(('r','timer',addr,size,value))
            elif ENTRY<=addr and addr+size<=ENTRY+len(code):pass
            else:assert STACK-240<=addr and addr+size<=STACK,hex(addr)
        def write(cpu,access,addr,size,value,_):
            if RAM<=addr and addr+size<=RAM+792:
                self.writes.append((addr-RAM,size,value))
                self.accesses.append(('w','state',addr-RAM,size,value))
            else:assert STACK-240<=addr and addr+size<=STACK,hex(addr)
        c.hook_add(UC_HOOK_CODE,guard);c.hook_add(UC_HOOK_MEM_READ,read);c.hook_add(UC_HOOK_MEM_WRITE,write)
    def run(self,before,sampled,fpscr):
        c=self.cpu;self.reads={};self.writes=[];self.mmio=[];self.accesses=[]
        c.mem_write(RAM,before);c.mem_write(TIMER,struct.pack('<I',sampled));c.mem_write(STACK-256,b'\x6d'*272)
        saved={UC_ARM_REG_R4+i:0x12345600+i for i in range(8)}
        saved.update({UC_ARM_REG_D8+i:0x1122334455667700+i for i in range(8)})
        for reg,value in saved.items():c.reg_write(reg,value)
        c.reg_write(UC_ARM_REG_R0,RAM);c.reg_write(UC_ARM_REG_SP,STACK);c.reg_write(UC_ARM_REG_LR,STOP|1);c.reg_write(UC_ARM_REG_FPSCR,fpscr)
        c.emu_start(ENTRY|1,STOP,count=150)
        assert c.reg_read(UC_ARM_REG_PC)==STOP and c.reg_read(UC_ARM_REG_SP)==STACK
        assert all(c.reg_read(reg)==value for reg,value in saved.items())
        assert bytes(c.mem_read(STACK-256,16))==b'\x6d'*16 and bytes(c.mem_read(STACK,16))==b'\x6d'*16
        assert self.mmio==[('r',TIMER,4,sampled)]
        assert self.reads.get((0x68,2))==2,self.reads
        after=bytes(c.mem_read(RAM,792))
        expected=bytearray(before)
        sign=1 if before[0x5c] else -1
        phase=(h16(before,0x68)+sign*h16(before,0x6a))&0xffff
        put32(expected,0x74,sampled);put32(expected,0x80,sampled-u32(before,0x74))
        put32(expected,0x60,u32(before,0x60)+sign);struct.pack_into('<H',expected,0x68,phase)
        if phase&0x3fff==0 and before[0x98]!=255:expected[0x98]+=1
        if before[0xcc]==1:
            expected[0xd1]=0;expected[0x1c:0x20]=before[0x10:0x14]
            expected[0x80:0x84]=before[0x8c:0x90];expected[0xcc]=2
        # Independent integer/state oracle; FP angle is compared to actual stock below.
        assert after[:0x4c]==expected[:0x4c] and after[0x50:]==expected[0x50:]
        return after.hex(),self.writes,sorted(self.reads.items()),self.mmio,c.reg_read(UC_ARM_REG_FPSCR),self.accesses
def cases():
    rng=random.Random(0x53544550)
    result=[]
    def one(phase,direction,gate,mode):
        before=bytearray(rng.randbytes(792));before[0x5c]=direction;before[0x98]=gate;before[0xcc]=mode
        step=rng.randrange(65536);old=(phase-step if direction else phase+step)&0xffff
        struct.pack_into('<HH',before,0x68,old,step)
        return bytes(before),rng.getrandbits(32)
    phases=[0,1,2,0x3ffe,0x3fff,0x4000,0x4001,0x7fff,0x8000,0x8001,0xbfff,0xc000,0xc001,0xfffe,0xffff]
    for phase in phases:
        for direction in [0,1]:
            for gate in [0,1,254,255]:
                for mode in [0,1,2,255]:result.append(one(phase,direction,gate,mode))
    result += [one(0,direction,direction%256,direction%4) for direction in range(256)]
    result += [one(0,mode%2,mode,mode) for mode in range(256)]
    result += [one(rng.randrange(65536),rng.randrange(256),rng.randrange(256),rng.randrange(256)) for _ in range(1024)]
    return result
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report',type=Path,default=ROOT/'work/mainBoardGD-motor/results.json')
    parser.add_argument('--out',type=Path,default=ROOT/'work/mainBoardGD-motor-step-model.json')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args();path=args.isolated_report.resolve()
    if args.self_test:self_test(path);return 0
    expected,candidate,report=inputs(path)
    a,b=Runner(expected),Runner(candidate);count=0;digest=hashlib.sha256()
    vectors=cases()
    for mode in range(16):
        fpscr=(mode&3)<<22|(mode>>2)<<24
        for before,sampled in vectors:
            old,new=a.run(before,sampled,fpscr),b.run(before,sampled,fpscr)
            if old!=new:
                raise ValueError('motor step disagreement: '+repr((count,hex(sampled),hex(fpscr),old,new)))
            digest.update(before+struct.pack('<II',sampled,fpscr))
            digest.update(json.dumps(new,separators=(',',':')).encode())
            count+=1
    report.update(
        scope='isolated motor step stock/candidate state, integer oracle, MMIO and FP/ABI model',
        whole_image_verified=False,
        results=[dict(name=NAME,cases=count,passed=count,stock_entry=ENTRY,candidate_entry=ENTRY,
                      expected_size=len(expected),actual_size=len(candidate),byte_exact=expected==candidate,
                      result_sha256=digest.hexdigest())],
        limitations=[
            'Actual ARM instructions execute in Unicorn, with no mocked calls or FP operations.',
            'Complete state and combined state/timer read-write traces are compared, including values, widths and ordering; literal-pool and stack accesses are guarded but excluded from that trace.',
            'Compares complete final FPSCR; exercises four rounding modes and FZ/DN combinations, not all initial sticky-flag settings or physical FP exception timing.',
            'Timer input is an ordinary register latch, not hardware timer timing, asynchronous state mutation or interrupt validation.',
            'Finite deterministic vectors, not exhaustive input-state combinations or complete loop/firmware equivalence.'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{NAME}: {count}/{count} state/oracle/ordered-access/MMIO/FPSCR/ABI cases PASS.')
    return 0

if __name__=='__main__':raise SystemExit(main())
