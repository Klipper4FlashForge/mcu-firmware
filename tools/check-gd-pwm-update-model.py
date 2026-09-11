#!/usr/bin/env python3
"""Check PWM update's actual ARM FP, timer writes, state reads and ABI.

Isolated stock versus reconstructed C in Unicorn. Registers are ordinary
latches: this does not validate real PWM waveforms or peripheral timing.
"""
import argparse, hashlib, io, json, random, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
ENTRY, PWM, PATTERN, TIMER, STOP, STACK=0x3b38,0x24000020,0x24000080,0x40010000,0x10000000,0x2400ff00
EXTENT, NAME = 228, 'mclib_pwm_update'
STOCK_MD5 = 'fb64911bac422a27d7ed7fab3597603f'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inputs(report_path):
    blob=report_path.read_bytes()
    report=json.loads(blob)
    for filename, expected in report['source_sha256'].items():
        if sha((ROOT/filename).read_bytes()) != expected:
            raise ValueError('stale source: '+filename)
    compiler=Path(report['compiler'])
    if sha(compiler.read_bytes()) != report['compiler_sha256']:
        raise ValueError('compiler differs from canonical report')
    stock=(ROOT/'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    if hashlib.md5(stock).hexdigest()!=STOCK_MD5 or report['stock_md5']!=STOCK_MD5:
        raise ValueError('unexpected stock image')
    rows=[row for row in report['results'] if row['name']==NAME]
    if len(rows)!=1:raise ValueError('missing or ambiguous PWM row')
    row=rows[0]
    path=report_path.parent/(NAME+'.elf')
    elf_blob=path.read_bytes();elf=ELFFile(io.BytesIO(elf_blob))
    section=elf.get_section_by_name('.text')
    symbols=elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    candidate=section.data()
    expected=stock[ENTRY+0x4418:ENTRY+0x4418+EXTENT]
    if (len(symbols)!=1 or symbols[0]['st_info']['type']!='STT_FUNC'
            or symbols[0]['st_value']!=ENTRY|1 or symbols[0]['st_size']!=len(candidate)
            or elf.header['e_entry']!=ENTRY|1 or section['sh_addr']!=ENTRY
            or row['address']!=ENTRY or row['expected_size']!=EXTENT
            or not 0<len(candidate)<=EXTENT or row['actual_size']!=len(candidate)
            or row['candidate_sha256']!=sha(candidate)
            or row['expected_sha256']!=sha(expected)):
        raise ValueError('PWM extent, entry, ELF or stock digest mismatch')
    provenance=dict(
        isolated_report=str(report_path),isolated_report_sha256=sha(blob),
        elf_sha256={str(path):sha(elf_blob)},source_sha256=report['source_sha256'],
        compiler=str(compiler),compiler_sha256=report['compiler_sha256'],flags=report['flags'],
        stock_md5=STOCK_MD5,stock_sha256=sha(stock),expected_sha256=sha(expected),
        candidate_sha256=sha(candidate),checker_sha256=sha(Path(__file__).read_bytes()),
        unicorn_version=unicorn.__version__)
    return expected,candidate,provenance
class Runner:
    def __init__(self,code):
        self.cpu=c=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
        c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
        for address,size in [(0,0x10000),(0x24000000,0x10000),(TIMER,0x1000),(STOP,0x1000)]:c.mem_map(address,size)
        c.mem_write(ENTRY,code)
        c.reg_write(UC_ARM_REG_C1_C0_2,0xf<<20); c.reg_write(UC_ARM_REG_FPEXC,1<<30)
        def guard(cpu,address,size,_):
            assert ENTRY<=address and address+size<=ENTRY+len(code),hex(address)
        def read(cpu,access,address,size,value,_):
            if PWM<=address and address+size<=PWM+12:
                key=('pwm',address-PWM,size)
            elif PATTERN<=address and address+size<=PATTERN+28:
                key=('pattern',address-PATTERN,size)
            elif ENTRY<=address and address+size<=ENTRY+len(code):return
            else:
                assert STACK-240<=address and address+size<=STACK,hex(address)
                return
            self.reads[key]=self.reads.get(key,0)+1
        def write(cpu,access,address,size,value,_):
            if TIMER<=address and address+size<=TIMER+256:
                self.writes.append((address-TIMER,size,value))
            else:assert STACK-240<=address and address+size<=STACK,hex(address)
        c.hook_add(UC_HOOK_CODE,guard);c.hook_add(UC_HOOK_MEM_READ,read);c.hook_add(UC_HOOK_MEM_WRITE,write)
    def run(self,values,polarity,fpscr):
        c=self.cpu;self.writes=[];self.reads={}
        ap,ae,bp,be=values
        pattern=bytes([0x9a,0xbc,polarity,0xde])+struct.pack('<6I',ap,ae,0x11223344,bp,be,0x55667788)
        pwm=struct.pack('<3I',TIMER,0x11223344,0x55667788)
        c.mem_write(PWM,pwm);c.mem_write(PATTERN,pattern);c.mem_write(TIMER,b'\xa5'*256)
        c.mem_write(STACK-256,b'\x6d'*272)
        saved={UC_ARM_REG_R4+i:0x11223300+i for i in range(8)}
        saved.update({UC_ARM_REG_D8+i:0x1122334455667700+i for i in range(8)})
        for reg,val in saved.items():c.reg_write(reg,val)
        c.reg_write(UC_ARM_REG_R0,PWM);c.reg_write(UC_ARM_REG_R1,PATTERN)
        c.reg_write(UC_ARM_REG_SP,STACK);c.reg_write(UC_ARM_REG_LR,STOP|1);c.reg_write(UC_ARM_REG_FPSCR,fpscr)
        c.emu_start(ENTRY|1,STOP,count=150)
        assert c.reg_read(UC_ARM_REG_PC)==STOP and c.reg_read(UC_ARM_REG_SP)==STACK
        assert all(c.reg_read(reg)==val for reg,val in saved.items())
        assert bytes(c.mem_read(PWM,12))==pwm and bytes(c.mem_read(PATTERN,28))==pattern
        assert bytes(c.mem_read(STACK-256,16))==b'\x6d'*16 and bytes(c.mem_read(STACK,16))==b'\x6d'*16
        assert self.reads.get(('pwm',0,4))==8,self.reads
        assert [(offset,size) for offset,size,val in self.writes]==[(offset,4) for offset in [0x34,0x64,0x38,0x68,0x3c,0x6c,0x40,0x70]]
        return bytes(c.mem_read(TIMER,256)).hex(),self.writes,sorted(self.reads.items()),c.reg_read(UC_ARM_REG_FPSCR)
def cases():
    special=[0,0x80000000,1,0x80000001,0x007fffff,0x807fffff,0x00800000,0x80800000,
         0x3f800000,0xbf800000,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,
         0x40000000,0xc0000000,0x41200000,0xc1200000,0x3eaaaaab,0xbeaaaaab,
         0x7fc00000,0xffc12345,0x7f800001,0xff812345]
    baseline=[0x3e800000,0x3e000000,0xbe800000,0x3e000000]
    result=[]
    for field in range(4):
        for value in special:
            values=baseline.copy();values[field]=value
            result.extend((values,polarity) for polarity in range(4))
    # Opposing infinities and distinct quiet/signaling NaN payload pairs.
    for left in range(4):
        for right in range(left+1,4):
            for a in [0x7f800000,0xff800000,*special[-4:]]:
                for b in [0x7f800000,0xff800000,*special[-4:]]:
                    values=baseline.copy();values[left]=a;values[right]=b
                    result.extend((values,polarity) for polarity in range(4))
    rng=random.Random(0x50574d55)
    result += [([rng.getrandbits(32) for _ in range(4)],rng.randrange(256)) for _ in range(512)]
    result += [(baseline,polarity) for polarity in range(256)]
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report',type=Path,default=ROOT/'work/mainBoardGD-motor/results.json')
    parser.add_argument('--out',type=Path,default=ROOT/'work/mainBoardGD-pwm-update-model.json')
    args=parser.parse_args()
    expected,candidate,report=inputs(args.isolated_report.resolve())
    a,b=Runner(expected),Runner(candidate)
    count,digest=0,hashlib.sha256()
    vectors=cases()
    for mode in range(16):
        fpscr=(mode&3)<<22|(mode>>2)<<24
        for values,polarity in vectors:
            old,new=a.run(values,polarity,fpscr),b.run(values,polarity,fpscr)
            if old!=new:
                raise ValueError('PWM disagreement: '+repr((count,[hex(x) for x in values],polarity,hex(fpscr),old,new)))
            digest.update(struct.pack('<6I',*values,polarity,fpscr))
            digest.update(json.dumps(new,separators=(',',':')).encode())
            count+=1
    report.update(
        scope='isolated PWM update stock-versus-candidate FP/MMIO/state/ABI model',
        whole_image_verified=False,
        results=[dict(name=NAME,cases=count,passed=count,stock_entry=ENTRY,candidate_entry=ENTRY,
                      expected_size=len(expected),actual_size=len(candidate),byte_exact=expected==candidate,
                      result_sha256=digest.hexdigest())],
        limitations=[
            'Actual ARM instructions execute in Unicorn; no calls, conversions or FP arithmetic are mocked.',
            'Peripheral registers are ordinary latches, not physical PWM waveforms or timing validation.',
            'Compares complete final FPSCR; exercises four rounding modes and FZ/DN combinations.',
            'Finite deterministic input vectors are not exhaustive; invalid float-to-uint behavior is compiler/target-specific, not portable C.',
            'State read counts and eight ordered MMIO writes are compared; full state-load scheduling, asynchronous mutation, pointer aliasing and MMIO timing are not modeled.',
            'No complete control-loop or firmware boot equivalence is established.'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{NAME}: {count}/{count} ordered-MMIO/read-count/state/FPSCR/ABI cases PASS.')
    return 0

if __name__=='__main__':raise SystemExit(main())
