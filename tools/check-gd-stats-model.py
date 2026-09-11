#!/usr/bin/env python3
"""Actual stats ARM instructions with explicit encoder/send mocks and oracle."""
import argparse,copy,hashlib,io,json,random,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/python-deps'))
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_MODE_MCLASS,UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *
import unicorn
ENTRY,SIZE,RAM,STACK,STOP=0x46c8,232,0x24008a9c,0x2400ff00,0x10000000
ENCODER,PERIOD=0x6000,3000000000
image=(ROOT/'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
stock=image[ENTRY+0x4418:ENTRY+0x4418+SIZE]
NAME,STOCK_MD5='stats_update','fb64911bac422a27d7ed7fab3597603f'
def sha(data):return hashlib.sha256(data).hexdigest()
def inputs(path,report_override=None,elf_override=None):
 blob=path.read_bytes();report=json.loads(blob) if report_override is None else report_override
 for filename,digest in report['source_sha256'].items():
  if sha((ROOT/filename).read_bytes())!=digest:raise ValueError('stale source: '+filename)
 compiler=Path(report['compiler'])
 if sha(compiler.read_bytes())!=report['compiler_sha256']:raise ValueError('stale compiler')
 if hashlib.md5(image).hexdigest()!=STOCK_MD5 or report['stock_md5']!=STOCK_MD5:raise ValueError('unexpected stock')
 rows=[row for row in report['results'] if row['name']==NAME]
 if len(rows)!=1:raise ValueError('missing or ambiguous stats row')
 row=rows[0];elf_path=path.parent/(NAME+'.elf')
 elf_blob=elf_path.read_bytes() if elf_override is None else elf_override
 elf=ELFFile(io.BytesIO(elf_blob));sec=elf.get_section_by_name('.text')
 symbols=elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
 candidate=sec.data()
 if (len(symbols)!=1 or symbols[0]['st_info']['type']!='STT_FUNC'
     or symbols[0]['st_value']!=ENTRY|1 or elf.header['e_entry']!=ENTRY|1
     or sec['sh_addr']!=ENTRY or symbols[0]['st_size']!=len(candidate)
     or not 0<len(candidate)<=SIZE or row['address']!=ENTRY
     or row['actual_size']!=len(candidate) or row['expected_size']!=SIZE
     or row['actual_sha256']!=sha(candidate) or row['expected_sha256']!=sha(stock)):
  raise ValueError('stats ELF, extent, entry or hash mismatch')
 return candidate,dict(isolated_report=str(path),isolated_report_sha256=sha(blob),
  source_sha256=report['source_sha256'],compiler=str(compiler),compiler_sha256=report['compiler_sha256'],
  flags=report['flags'],stock_md5=STOCK_MD5,stock_sha256=sha(image),expected_sha256=sha(stock),
  candidate_sha256=sha(candidate),elf_sha256={str(elf_path):sha(elf_blob)},
  checker_sha256=sha(Path(__file__).read_bytes()),unicorn_version=unicorn.__version__)
def self_test(path):
 inputs(path);original=json.loads(path.read_bytes());tests=[]
 def reject(label,report=None,elf=None):
  try:inputs(path,report,elf)
  except ValueError:tests.append(label)
  else:raise AssertionError('accepted '+label)
 for key in ('compiler_sha256','stock_md5'):
  bad=copy.deepcopy(original);bad[key]='0'*64;reject(key,bad)
 bad=copy.deepcopy(original);bad['source_sha256'][next(iter(bad['source_sha256']))]='0'*64
 reject('source_sha256',bad)
 for key in ('address','actual_size','expected_size','actual_sha256','expected_sha256'):
  bad=copy.deepcopy(original);row=next(r for r in bad['results'] if r['name']==NAME)
  row[key]=row[key]+2 if isinstance(row[key],int) else '0'*64;reject(key,bad)
 original_elf=(path.parent/(NAME+'.elf')).read_bytes();parsed=ELFFile(io.BytesIO(original_elf))
 bad=bytearray(original_elf);struct.pack_into('<I',bad,24,ENTRY+3);reject('ELF entry',elf=bytes(bad))
 table=parsed.get_section_by_name('.symtab')
 symbol_index=next(i for i,s in enumerate(table.iter_symbols()) if s.name==NAME)
 symbol_offset=table['sh_offset']+symbol_index*table['sh_entsize']
 for label,offset,value in [('symbol entry',4,ENTRY+3),('symbol size',8,SIZE-2)]:
  bad=bytearray(original_elf);struct.pack_into('<I',bad,symbol_offset+offset,value);reject(label,elf=bytes(bad))
 section_index=next(i for i,s in enumerate(parsed.iter_sections()) if s.name=='.text')
 bad=bytearray(original_elf)
 struct.pack_into('<I',bad,parsed.header['e_shoff']+section_index*parsed.header['e_shentsize']+12,ENTRY+2)
 reject('section address',elf=bytes(bad))
 bad=bytearray(original_elf);bad[parsed.get_section_by_name('.text')['sh_offset']]^=1
 reject('candidate byte',elf=bytes(bad))
 print(f'{len(tests)}/{len(tests)} provenance/entry/extent rejection self-tests PASS.')
def words(data):return list(struct.unpack('<5I',data))
class Runner:
 def __init__(self,code):
  c=self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
  c.mem_map(0,0x10000);c.mem_map(0x24000000,0x10000);c.mem_map(STOP,0x1000)
  c.mem_write(ENTRY,code);c.mem_write(0x5130,image[0x9548:0x9550])
  def instruction(cpu,addr,size,_):
   if addr==0x5130:
    assert cpu.reg_read(UC_ARM_REG_R0)==5000000
    self.events.append(('timer',5000000));return
   if addr==0x21a0:
    ptr=cpu.reg_read(UC_ARM_REG_R0)
    text=b'stats count=%u sum=%u sumsq=%u\0'
    assert bytes(cpu.mem_read(ptr,len(text)))==text
    self.events.append(('encoder',ptr));self.clobber();cpu.reg_write(UC_ARM_REG_R0,ENCODER)
    cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
   if addr==0x1ca8:
    args=tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3))
    self.events.append(('send',*args));assert args[0]==ENCODER
    if self.after_send is not None:cpu.mem_write(RAM,struct.pack('<5I',*self.after_send))
    self.clobber();cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
   assert ENTRY<=addr and addr+size<=ENTRY+len(code) or 0x5130<=addr<0x5138,hex(addr)
  def read(cpu,access,addr,size,value,_):
   if RAM<=addr and addr+size<=RAM+20:
    assert size==4
    if addr==RAM+16:
     self.square_reads+=1
     if self.square_reads==self.reload_at and self.reload is not None:
      cpu.mem_write(addr,struct.pack('<I',self.reload))
    self.events.append(('r',addr-RAM,4,int.from_bytes(cpu.mem_read(addr,4),'little')))
   else:assert STACK-240<=addr and addr+size<=STACK,hex(addr)
  def write(cpu,access,addr,size,value,_):
   if RAM<=addr and addr+size<=RAM+20:
    assert size==4;self.events.append(('w',addr-RAM,4,value&0xffffffff))
   else:assert STACK-240<=addr and addr+size<=STACK,hex(addr)
  c.hook_add(UC_HOOK_CODE,instruction);c.hook_add(UC_HOOK_MEM_READ,read);c.hook_add(UC_HOOK_MEM_WRITE,write)
 def clobber(self):
  for i,r in enumerate((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12)):
   self.cpu.reg_write(r,0xb6e17a01+i*0x19343)
 def run(self,case):
  initial,start,now,self.reload,self.after_send=case
  self.events=[];self.square_reads=0;self.reload_at=2 if (now-start)&0xffffffff<=0xfffff else 1
  c=self.cpu;c.mem_write(RAM,struct.pack('<5I',*initial));c.mem_write(RAM-16,b'\x9c'*16);c.mem_write(RAM+20,b'\x9c'*16)
  c.mem_write(STACK-256,b'\x6d'*272)
  saved={UC_ARM_REG_R4+i:0x12345600+i for i in range(8)}
  for r,v in saved.items():c.reg_write(r,v)
  c.reg_write(UC_ARM_REG_R0,start);c.reg_write(UC_ARM_REG_R1,now)
  c.reg_write(UC_ARM_REG_SP,STACK);c.reg_write(UC_ARM_REG_LR,STOP|1)
  c.emu_start(ENTRY|1,STOP,count=200)
  assert c.reg_read(UC_ARM_REG_PC)==STOP and c.reg_read(UC_ARM_REG_SP)==STACK
  assert all(c.reg_read(r)==v for r,v in saved.items())
  assert bytes(c.mem_read(STACK-256,16))==b'\x6d'*16 and bytes(c.mem_read(STACK,16))==b'\x6d'*16
  assert bytes(c.mem_read(RAM-16,16))==b'\x9c'*16 and bytes(c.mem_read(RAM+20,16))==b'\x9c'*16
  return words(c.mem_read(RAM,20)),self.events
def oracle(case):
 initial,start,now,reload,after_send=case
 state=initial.copy();events=[]
 def read(index):events.append(('r',index*4,4,state[index]));return state[index]
 def write(index,value):state[index]=value&0xffffffff;events.append(('w',index*4,4,state[index]))
 diff=(now-start)&0xffffffff
 write(2,read(2)+1);write(3,read(3)+diff)
 if diff<=0xffff:next_square=(read(4)+((diff*diff+255)>>8))&0xffffffff
 elif diff<=0xfffff:next_square=(read(4)+((diff+255)>>8)*diff)&0xffffffff
 else:next_square=0xffffffff
 if reload is not None:state[4]=reload
 if next_square<read(4):next_square=0xffffffff
 previous=read(0);write(4,next_square);events.append(('timer',5000000))
 if (now-previous)&0xffffffff<PERIOD:return state,events
 events.append(('encoder',0x4790))
 count,total,square=read(2),read(3),read(4)
 events.append(('send',ENCODER,count,total,square))
 if after_send is not None:state[:]=after_send
 if read(0)>now:write(1,read(1)+1)
 write(0,now);write(4,0);write(3,0);write(2,0)
 return state,events
def cases():
 rng=random.Random(0x46c8);result=[]
 diffs=[0,1,15,16,255,256,0xfffe,0xffff,0x10000,0xffffe,0xfffff,0x100000,0x7fffffff,0x80000000,0xffffffff]
 elapsed=[0,PERIOD-1,PERIOD,PERIOD+1,0x80000000,0xffffffff]
 for diff in diffs:
  for gap in elapsed:
   for reload in (None,0,0xffffffff):
    for mutate in (False,True):
     now=rng.getrandbits(32);initial=[(now-gap)&0xffffffff,*[rng.getrandbits(32) for _ in range(4)]]
     result.append((initial,(now-diff)&0xffffffff,now,reload,[rng.getrandbits(32) for _ in range(5)] if mutate else None))
 for i in range(1024):
  result.append(([rng.getrandbits(32) for _ in range(5)],rng.getrandbits(32),rng.getrandbits(32),rng.getrandbits(32),None if i&1 else [rng.getrandbits(32) for _ in range(5)]))
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--isolated-report',type=Path,default=ROOT/'work/mainBoardGD-base/results.json')
 parser.add_argument('--out',type=Path,default=ROOT/'work/mainBoardGD-stats-model.json')
 parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
 if args.self_test:self_test(args.isolated_report.resolve());return 0
 candidate,report=inputs(args.isolated_report.resolve())
 a,b=Runner(stock),Runner(candidate);count=0;digest=hashlib.sha256()
 for case in cases():
  expected=oracle(case);old,new=a.run(case),b.run(case)
  if old!=new or new!=expected:raise ValueError('stats state/trace/oracle mismatch: '+repr((count,case,old,new,expected)))
  digest.update(json.dumps((case,new),separators=(',',':')).encode());count+=1
 report.update(scope='bounded stats arithmetic/state/ordered-access/call/ABI model',whole_image_verified=False,
  results=[dict(name=NAME,cases=count,passed=count,byte_exact=candidate==stock,stock_entry=ENTRY,
    candidate_entry=ENTRY,actual_size=len(candidate),expected_size=SIZE,result_sha256=digest.hexdigest())],
  limitations=[
   'Actual stock timer_from_us code executes; encoder lookup and sending are explicit ABI-clobbering mocks.',
   'Complete statistics state, combined ordered state accesses/calls, independent integer oracle and preserved core ABI are checked.',
   'Selected accumulator-read and post-send state changes test reload behavior; they do not simulate interrupt timing or prove concurrency safety.',
   'Deterministic finite vectors, ordinary RAM latches and guarded stack; not hardware, complete scheduler or whole-firmware validation.'])
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
 print(f'{NAME}: {count}/{count} state/oracle/ordered-access/call/reload/ABI cases PASS.');return 0
if __name__=='__main__':raise SystemExit(main())
