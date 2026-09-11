#!/usr/bin/env python3
"""Stepper configuration caller model with real stock GPIO/IRQ/queue helpers.

Only allocation and error lookup/shutdown are explicit boundary mocks. MMIO
uses deterministic register latches, not physical peripheral side effects.
This does not count stock dependency execution as reconstructed code coverage.
"""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import random
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE
from unicorn import arm_const as arm
import scatterload

NAME, ENTRY, SIZE = 'command_config_stepper', 0xf08, 106
RAM, STATE, ARGS, STACK, STOP = 0x24000000, 0x24011000, 0x24012000, 0x2401f000, 0x10000000
IMAGE_SHA = '9653998b1f3ba754a2ab3d045d0941b8e08c1bfa444d2f5bfc5cecaf0bab1c50'
CALLS = {0x3f30: ('allocate', 3), 0x32b8: ('gpio_setup', 3),
         0x31b0: ('gpio_reset', 4), 0x3080: ('gpio_clock', 1),
         0x38a0: ('irq_save', 0), 0x3898: ('irq_restore', 1),
         0x08000b78: ('direction', 2), 0x3e80: ('queue_setup', 2),
         0x2420: ('error_lookup', 1), 0x4410: ('shutdown', 1)}
DEPENDENCIES = [(0x3080, 40), (0x31b0, 264), (0x32b8, 104),
                (0x3898, 6), (0x38a0, 8), (0x3e80, 84),
                (0x5b9e, 10), (0x08000b78, 6)]
SAVED = [getattr(arm, 'UC_ARM_REG_R%d' % i) for i in range(4, 12)]
SAVED_FP = [getattr(arm, 'UC_ARM_REG_D%d' % i) for i in range(8, 16)]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inputs(report_path, override=None, elf_override=None):
    blob = report_path.read_bytes()
    report = json.loads(blob) if override is None else override
    hashes = report['source_sha256']
    for suffix in ('stepper.c', 'stepper.h', 'gpio.h', 'check-gd-stepper.py'):
        if not any(Path(p).name == suffix for p in hashes):
            raise ValueError('missing source provenance: ' + suffix)
    for path, digest in hashes.items():
        if sha((ROOT / path).read_bytes()) != digest:
            raise ValueError('stale source: ' + path)
    compiler = Path(report['compiler'])
    if sha(compiler.read_bytes()) != report['compiler_sha256']:
        raise ValueError('stale compiler')
    image = (ROOT / 'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
    if sha(image) != IMAGE_SHA or hashlib.md5(image).hexdigest() != report['stock_md5']:
        raise ValueError('unexpected stock')
    rows = [r for r in report['results'] if r['name'] == NAME]
    if len(rows) != 1:
        raise ValueError('missing or ambiguous config row')
    row = rows[0]
    elf_path = report_path.parent / (NAME + '.elf')
    elf_blob = elf_path.read_bytes() if elf_override is None else elf_override
    elf = ELFFile(io.BytesIO(elf_blob))
    section = elf.get_section_by_name('.text')
    symbols = elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
    if section is None or not symbols or len(symbols) != 1:
        raise ValueError('missing function section or symbol')
    symbol, candidate = symbols[0], section.data()
    expected = image[0x4418 + ENTRY:0x4418 + ENTRY + SIZE]
    if (section['sh_addr'] != ENTRY or symbol['st_value'] != ENTRY | 1
            or symbol['st_info']['type'] != 'STT_FUNC' or elf.header['e_entry'] != ENTRY | 1
            or symbol['st_size'] != len(candidate) or not 0 < len(candidate) <= SIZE
            or row['address'] != ENTRY or row['expected_size'] != SIZE
            or row['actual_size'] != len(candidate) or not row['entry_exact']
            or row['actual_symbol_address'] != ENTRY
            or row['actual_sha256'] != sha(candidate) or row['expected_sha256'] != sha(expected)):
        raise ValueError('entry, extent or byte hash mismatch')
    initialized, used = scatterload.decompress(image[0x3778:], 11912)
    if used != 3225 or len(initialized) != 11912:
        raise ValueError('unexpected initialized RAM region')
    audit = dict(isolated_report=str(report_path), isolated_report_sha256=sha(blob),
                 source_sha256=hashes, compiler=str(compiler), compiler_sha256=report['compiler_sha256'],
                 flags=report['flags'], stock_sha256=sha(image), expected_sha256=sha(expected),
                 candidate_sha256=sha(candidate), elf_sha256={str(elf_path):sha(elf_blob)},
                 checker_sha256=sha(Path(__file__).read_bytes()),
                 decoder_sha256=sha(Path(scatterload.__file__).read_bytes()),
                 initialized_ram_sha256=sha(initialized), unicorn_version=unicorn.__version__,
                 stock_dependencies=[dict(address=a, size=n, sha256=sha(image[
                     a-0x08000000 if a>=0x08000000 else a+0x4418:
                     (a-0x08000000 if a>=0x08000000 else a+0x4418)+n]))
                                     for a,n in DEPENDENCIES])
    return expected, candidate, image, initialized, audit

class Runner:
    def __init__(self, code, image, initialized):
        self.code = code
        self.template = initialized + bytes(0x20000-len(initialized))
        u = self.u = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
        u.ctl_set_cpu_model(arm.UC_CPU_ARM_CORTEX_M7)
        for address,size in [(0,0x10000),(0x08000000,0x10000),(RAM,0x20000),(STOP,0x1000)]:
            u.mem_map(address,size)
        u.mem_write(0,image[0x4418:0x4418+28120])
        u.mem_write(0x08000000,image)
        u.mem_write(ENTRY,code)
        u.mmio_map(0x58020000,0x10000,self.mmio_read,None,self.mmio_write,None)
        u.hook_add(UC_HOOK_CODE,self.instruction)
        u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,self.memory)

    def mmio_read(self,u,offset,size,_):
        assert size==4 and offset%4==0
        address=0x58020000+offset
        value=self.registers.setdefault(address,(address*0x9e3779b1+self.seed)&0xffffffff)
        self.trace.append(('mmio_read',address,size,value))
        return value

    def mmio_write(self,u,offset,size,value,_):
        assert size==4 and offset%4==0
        address=0x58020000+offset
        self.registers[address]=value&0xffffffff
        self.trace.append(('mmio_write',address,size,value&0xffffffff))

    def memory(self,u,access,address,size,value,_):
        if 0x58020000<=address<0x58030000:
            return  # Recorded once by the MMIO callbacks.
        if STACK-96<=address and address+size<=STACK:
            return  # Dead stack temporaries/LR encodings need not match.
        if access!=UC_MEM_WRITE and (0<=address<0x10000 or 0x08000000<=address<0x08010000):
            return  # Stock literal/string/jump-table reads, not shared state.
        allowed = (ARGS<=address and address+size<=ARGS+20 or
                   STATE<=address and address+size<=STATE+80 or
                   RAM+0x219c<=address and address+size<=RAM+0x21ec or
                   address in (RAM+0x881e,RAM+0x8824) or
                   address in (RAM+0x2514+0x5c,RAM+0x282c+0x5c,
                               RAM+0x2b44+0x5c,RAM+0x21ec+0x5c))
        assert allowed,(hex(address),size)
        if access!=UC_MEM_WRITE:
            value=int.from_bytes(u.mem_read(address,size),'little')
        self.trace.append(('write' if access==UC_MEM_WRITE else 'read',address,size,value))

    def instruction(self,u,pc,size,_):
        if pc in CALLS:
            name,count=CALLS[pc]
            args=[u.reg_read(getattr(arm,'UC_ARM_REG_R%d'%i)) for i in range(count)]
            assert u.reg_read(arm.UC_ARM_REG_SP)%8==0,(name,'unaligned SP')
            self.trace.append(('call',name,args,u.reg_read(arm.UC_ARM_REG_PRIMASK),bytes(u.mem_read(STATE,80)).hex()))
            if pc==0x3f30:
                assert args==[self.args[0]&255,ENTRY|1,80]
                result=STATE
            elif pc==0x2420:
                message=bytearray()
                for i in range(64):
                    c=u.mem_read(args[0]+i,1)[0]
                    if not c:break
                    message.append(c)
                assert bytes(message) in (b'Not an output pin',b'Invalid move request size')
                self.trace.append(('error',bytes(message).decode()))
                result=19 if bytes(message)==b'Not an output pin' else 15
            elif pc==0x4410:
                assert args[0] in (19,15)
                self.shutdown=True
                u.reg_write(arm.UC_ARM_REG_PC,STOP|1)
                return
            else:
                if pc==0x32b8:
                    assert STACK-32<=args[0] and args[0]+12<=STACK-16
                    expected_pin=self.args[1+self.gpio_calls]&255
                    assert args[1]==expected_pin,'pin was not truncated to byte'
                    expected_value=(4 if 0<self.args[3]<0x80000000 else 0) if self.gpio_calls==0 else 0
                    assert args[2]==expected_value
                    self.gpio_calls+=1
                elif pc==0x3e80:
                    assert args==[STATE+60,16]
                return  # Execute the real stock helper instructions.
            for i in (0,1,2,3,12):u.reg_write(getattr(arm,'UC_ARM_REG_R%d'%i),0xa5a50000+i)
            for i in range(8):u.reg_write(getattr(arm,'UC_ARM_REG_D%d'%i),0xa5a5000000000000+i)
            u.reg_write(arm.UC_ARM_REG_APSR_NZCV,0xb0000000)
            u.reg_write(arm.UC_ARM_REG_R0,result)
            u.reg_write(arm.UC_ARM_REG_PC,u.reg_read(arm.UC_ARM_REG_LR))
            return
        assert ENTRY<=pc and pc+size<=ENTRY+len(self.code) or any(a<=pc and pc+size<=a+n for a,n in DEPENDENCIES),(hex(pc),size)
        assert not (0x3258<=pc<0x325c or 0x330c<=pc<0x3320 or 0x3eb8<=pc<0x3ed4),'executed inline data'

    def run(self,args,state,seed,primask,move_count=0,stride=0):
        u=self.u
        self.args,self.seed,self.trace,self.registers=args,seed,[],{}
        self.shutdown,self.gpio_calls=False,0
        initial=bytearray(self.template)
        initial[STATE-RAM-16:STATE-RAM+96]=b'\x5a'*16+state+b'\x5a'*16
        initial[ARGS-RAM-16:ARGS-RAM+36]=b'\xa5'*16+struct.pack('<5I',*args)+b'\xa5'*16
        initial[STACK-RAM-256:STACK-RAM+16]=b'\x6d'*272
        struct.pack_into('<H',initial,0x881e,move_count)
        initial[0x8824]=stride
        u.mem_write(RAM,bytes(initial))
        saved=[(seed*0x1020304+i)&0xffffffff for i in range(8)]
        fp=[(seed*0x102030405060708+i)&0xffffffffffffffff for i in range(8)]
        for r,v in zip(SAVED,saved):u.reg_write(r,v)
        for r,v in zip(SAVED_FP,fp):u.reg_write(r,v)
        u.reg_write(arm.UC_ARM_REG_R0,ARGS)
        u.reg_write(arm.UC_ARM_REG_SP,STACK)
        u.reg_write(arm.UC_ARM_REG_LR,STOP|1)
        u.reg_write(arm.UC_ARM_REG_PRIMASK,primask)
        u.reg_write(arm.UC_ARM_REG_APSR_NZCV,0x60000000)
        u.emu_start(ENTRY|1,STOP,count=2000)
        assert u.reg_read(arm.UC_ARM_REG_PC)==STOP
        if not self.shutdown:
            assert u.reg_read(arm.UC_ARM_REG_SP)==STACK
            assert [u.reg_read(r) for r in SAVED]==saved
            assert [u.reg_read(r) for r in SAVED_FP]==fp
            assert u.reg_read(arm.UC_ARM_REG_PRIMASK)==primask
        final=bytes(u.mem_read(RAM,0x20000))
        assert final[STACK-RAM-256:STACK-RAM-96]==b'\x6d'*160
        assert final[STACK-RAM:STACK-RAM+16]==b'\x6d'*16
        assert final[STATE-RAM-16:STATE-RAM]==final[STATE-RAM+80:STATE-RAM+96]==b'\x5a'*16
        assert final[ARGS-RAM-16:ARGS-RAM+36]==initial[ARGS-RAM-16:ARGS-RAM+36]
        # Compare all live RAM; discard only the explicitly bounded dead stack.
        storage=sha(final[:STACK-RAM-96]+final[STACK-RAM:])
        return dict(trace=self.trace,live_ram_sha256=storage,registers=sorted(self.registers.items()),
                    shutdown=self.shutdown,sp=u.reg_read(arm.UC_ARM_REG_SP),
                    primask=u.reg_read(arm.UC_ARM_REG_PRIMASK))

def vectors():
    rng=random.Random(0xf081d70)
    for pin in range(256):
        for invert in (0,1,2,255,0x7fffffff,0x80000000,0xffffffff):
            for high in (0,0x100,0x7fffff00,0xffffff00):
                yield [rng.getrandbits(32),high|pin,high|(255-pin),invert,rng.getrandbits(32)],rng.randbytes(80),rng.getrandbits(32),pin&1,0,pin
    for step, direction in ((0,1),(145,149),(153,157),(127,128),(159,160),(0xffffffff,0x100),(0x180,0x122)):
        for count in (0,1,65535):
            for mask in (0,1):
                yield [0xffffffff,step,direction,1,0xffffffff],rng.randbytes(80),rng.getrandbits(32),mask,count,0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-report',type=Path,default=ROOT/'work/mainBoardGD-stepper/results.json')
    parser.add_argument('--out',type=Path,default=ROOT/'work/mainBoardGD-stepper-config-model.json')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args();path=args.isolated_report.resolve()
    stock,candidate,image,initialized,audit=inputs(path)
    if args.self_test:
        checks=[]
        original=json.loads(path.read_text())
        def reject(name,report=None,blob=None):
            try:inputs(path,report,blob)
            except (ValueError,KeyError,AssertionError):checks.append(name);return
            raise AssertionError('negative control accepted: '+name)
        for key in ('actual_sha256','expected_sha256','actual_size','address','expected_size','actual_symbol_address','entry_exact'):
            altered=copy.deepcopy(original);row=next(r for r in altered['results'] if r['name']==NAME)
            row[key]=False if key=='entry_exact' else ('0'*64 if key.endswith('sha256') else row[key]+2)
            reject('row_'+key,altered)
        for key in ('compiler_sha256','stock_md5'):
            altered=copy.deepcopy(original);altered[key]='0'*len(altered[key]);reject(key,altered)
        altered=copy.deepcopy(original);altered['source_sha256'][next(iter(altered['source_sha256']))]='0'*64;reject('stale_source',altered)
        altered=copy.deepcopy(original);altered['source_sha256']={};reject('missing_sources',altered)
        # Source-level bug control is the old full-word load for each pin.
        # These comparison-only negative instructions are never firmware input.
        bad=bytearray(candidate)
        for byte_load,word_load in ((b'\x21\x79',b'\x61\x68'),(b'\x21\x7a',b'\xa1\x68')):
            assert bad.count(byte_load)==1
            altered=bytearray(candidate);offset=altered.index(byte_load);altered[offset:offset+2]=word_load
            try:Runner(bytes(altered),image,initialized).run([1,0x100,0x101,1,10],bytes(80),1,0)
            except AssertionError:checks.append('missing_pin_truncation_'+str(offset))
            else:raise AssertionError('full-width negative pin control survived')
        result=dict(scope='stepper config provenance and pin-width negative controls',checks=checks,passed=len(checks),**audit)
    else:
        expected,actual=Runner(stock,image,initialized),Runner(candidate,image,initialized)
        count=shutdowns=0;digest=hashlib.sha256()
        for vector in vectors():
            a,b=expected.run(*vector),actual.run(*vector)
            assert a==b,(vector[:1],a,b)
            digest.update(json.dumps([vector[0],a],sort_keys=True).encode())
            count+=1;shutdowns+=a['shutdown']
        result=dict(scope='bounded config caller with actual stock GPIO/IRQ/queue dependencies; not hardware or callee source proof',
                    cases=count,passed=count,shutdown_cases=shutdowns,execution_digest=digest.hexdigest(),
                    mocks=['oid_alloc','ctr_lookup_static_string','sched_shutdown'],
                    all_cases_exact=True,**audit)
    inputs(path)  # Reject edits during execution.
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2)+'\n')
    print(str(result['passed'])+' stepper configuration '+('self-tests' if args.self_test else 'ordered-MMIO/call/ABI cases')+' PASS; '+str(args.out))

if __name__=='__main__':
    main()
