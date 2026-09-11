#!/usr/bin/env python3
"""Bounded stock/candidate loop-B caller equivalence with explicit callee mocks."""
import argparse,copy,hashlib,io,json,random,struct,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'work/python-deps'))
from elftools.elf.elffile import ELFFile
import unicorn
from unicorn import *
from unicorn.arm_const import *
ENTRY,RAM,ACQ,PWM,STACK,STOP=0x08001258,0x24000020,0x24001000,0x24001100,0x2400ff00,0x10000000
TIMER=0x4000e024
stock=(ROOT/'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()[0x1258:0x15b4]
NAME,SIZE,STOCK_MD5='mclib_control_loop_b',860,'fb64911bac422a27d7ed7fab3597603f'
def sha(data):return hashlib.sha256(data).hexdigest()
CALLS={0x080031ac:'acquire',0x08002c58:'observer',0x08002970:'sincos',0x080020b0:'park',0x080020d0:'pi',0x080015e0:'limit',0x08002950:'inverse',0x08002e28:'prepare',0x080031b6:'pwm',0x080031c0:'polarity'}
def put(data,offset,value):struct.pack_into('<I',data,offset,value&0xffffffff)
def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def candidate(path,override=None):
 with io.BytesIO(path.read_bytes() if override is None else override) as stream:
  elf=ELFFile(stream);sec=elf.get_section_by_name('.text');data=sec.data()
  symbols=elf.get_section_by_name('.symtab').get_symbol_by_name(NAME)
  assert symbols is not None and len(symbols)==1
  sym=symbols[0]
  assert sym['st_info']['type']=='STT_FUNC'
  assert sec['sh_addr']==ENTRY and sym['st_value']==ENTRY|1 and elf.header['e_entry']==ENTRY|1 and sym['st_size']==len(data)
  mapping=[(s.name[1],s['st_value']) for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name.startswith(('$t','$d')) and ENTRY<=s['st_value']<ENTRY+len(data)]
  assert sorted(mapping,key=lambda s:s[1])==[('t',ENTRY),('d',ENTRY+len(data)-44)]
  return data
def inputs(path,report_override=None,elf_override=None):
 blob=path.read_bytes();report=json.loads(blob) if report_override is None else report_override
 if (not report['source_sha256']
     or not any(p.endswith('mclib_state.h') for p in report['source_sha256'])
     or not any(p.endswith('mclib_commands.c') for p in report['source_sha256'])):
  raise ValueError('missing source/header provenance')
 for filename,digest in report['source_sha256'].items():
  if sha((ROOT/filename).read_bytes())!=digest:raise ValueError('stale source: '+filename)
 compiler=Path(report['compiler'])
 if sha(compiler.read_bytes())!=report['compiler_sha256']:raise ValueError('stale compiler')
 image=(ROOT/'mcu/mainBoardGD/stock/mainBoardGD.bin').read_bytes()
 if hashlib.md5(image).hexdigest()!=STOCK_MD5 or report['stock_md5']!=STOCK_MD5:raise ValueError('unexpected stock')
 rows=[r for r in report['results'] if r['name']==NAME]
 if len(rows)!=1:raise ValueError('missing or ambiguous loop B row')
 row=rows[0];elf_path=path.parent/(NAME+'.elf')
 data=candidate(elf_path,elf_override)
 if (row['address']!=ENTRY or row['expected_size']!=SIZE or row['actual_size']!=len(data)
     or not 0<len(data)<=SIZE or row['candidate_sha256']!=sha(data) or row['expected_sha256']!=sha(stock)):
  raise ValueError('loop B extent or digest mismatch')
 elf_blob=elf_path.read_bytes() if elf_override is None else elf_override
 return data,dict(isolated_report=str(path),isolated_report_sha256=sha(blob),
  source_sha256=report['source_sha256'],compiler=str(compiler),compiler_sha256=report['compiler_sha256'],
  flags=report['flags'],stock_md5=STOCK_MD5,stock_sha256=sha(image),expected_sha256=sha(stock),
  candidate_sha256=sha(data),elf_sha256={str(elf_path):sha(elf_blob)},
  checker_sha256=sha(Path(__file__).read_bytes()),unicorn_version=unicorn.__version__)
class Runner:
 def __init__(self,code):
  self.code=code;c=self.cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB|UC_MODE_MCLASS)
  c.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M7)
  for addr,size in [(0x08000000,0x10000),(0x24000000,0x10000),(0x4000e000,0x1000),(STOP,0x1000)]:c.mem_map(addr,size)
  c.mem_write(ENTRY,code);c.reg_write(UC_ARM_REG_C1_C0_2,0xf<<20);c.reg_write(UC_ARM_REG_FPEXC,1<<30)
  # Prime the emulator's lazy FP context with the real stock VLDR at12aa,
  # before any hooks/test state. Otherwise its first FP access resets FPSCR
  # from lazy defaults, silently losing the requested initial rounding/FZ/DN.
  c.mem_write(0x08006000,stock[0x12aa-0x1258:0x12ae-0x1258])
  c.reg_write(UC_ARM_REG_R4,RAM)
  c.emu_start(0x08006001,0x08006004,count=1)
  def access(cpu,kind,addr,size,value,_):
   if RAM<=addr and addr+size<=RAM+792:region,offset='motor',addr-RAM
   elif ACQ<=addr and addr+size<=ACQ+48:region,offset='acq',addr-ACQ
   elif PWM<=addr and addr+size<=PWM+12:region,offset='pwm',addr-PWM
   elif addr==TIMER and size==4:region,offset='timer',0
   elif ENTRY<=addr and addr+size<=ENTRY+len(code):
    assert kind==UC_MEM_READ;return
   else:
    assert STACK-240<=addr and addr+size<=STACK,hex(addr)
    return
   action='r' if kind==UC_MEM_READ else 'w'
   if action=='r':value=int.from_bytes(cpu.mem_read(addr,size),'little')
   self.trace.append((action,region,offset,size,value))
  c.hook_add(UC_HOOK_MEM_READ,access);c.hook_add(UC_HOOK_MEM_WRITE,access)
  sites={};offset=0;it_remaining=0
  # Every candidate in this scoped profile has a final44-byte literal pool;
  # candidate() verifies the ELF $d boundary rather than scanning its words.
  while offset<len(code)-44:
   h1=struct.unpack_from('<H',code,offset)[0]
   width=4 if h1>>11>=0x1d else 2
   h2=struct.unpack_from('<H',code,offset+2)[0] if width==4 else 0
   assert offset+width<=len(code)-44
   if h1&0xf800==0xf000 and h2&0xd000==0xd000:
    assert it_remaining==0,'mocked BL inside IT block'
    s=(h1>>10)&1;i1=1^((h2>>13)&1)^s;i2=1^((h2>>11)&1)^s
    imm=s<<24|i1<<23|i2<<22|(h1&1023)<<12|(h2&2047)<<1
    if s:imm-=1<<25
    target=ENTRY+offset+4+imm
    assert target in CALLS,hex(target)
    sites[ENTRY+offset]=CALLS[target]
   if h1&0xff00==0xbf00 and h1&15:
    assert it_remaining==0 and (h1>>4)&15<14
    mask=h1&15;it_remaining=4-((mask&-mask).bit_length()-1)
   elif it_remaining:it_remaining-=1
   offset+=width
  assert it_remaining==0
  assert len(sites)==11
  def instruction(cpu,addr,size,_):
   if addr==ENTRY:assert cpu.reg_read(UC_ARM_REG_FPSCR)==self.initial_fpscr
   if addr in sites:
    # Mock the BL/callee/return boundary at the caller. No call is in an IT
    # block. Clear pending ITSTATE at this architectural call boundary: Unicorn
    # exposes stale IT bits after conditional VFP stores to a target code hook.
    cpu.reg_write(UC_ARM_REG_CPSR,cpu.reg_read(UC_ARM_REG_CPSR)&~0x0600fc00)
    cpu.reg_write(UC_ARM_REG_LR,addr+5)
    self.call(sites[addr]);return
   assert ENTRY<=addr and addr+size<=ENTRY+len(code)-44,hex(addr)
  c.hook_add(UC_HOOK_CODE,instruction)
 def call(self,name):
  c=self.cpu;r=[c.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
  assert c.reg_read(UC_ARM_REG_SP)%8==0,'unaligned call stack'
  if name in ('acquire','observer'):assert c.reg_read(UC_ARM_REG_FPSCR)==self.initial_fpscr
  fp=[c.reg_read(UC_ARM_REG_S0+i) for i in range(4)]
  args=[];values=self.values
  def store(addr,value):c.mem_write(addr,struct.pack('<I',value))
  if name=='acquire':
   assert r[0]==ACQ;args=[r[0]]
   store(ACQ+4,values[0]);store(ACQ+8,values[1])
  elif name=='observer':
   assert r[0]==RAM+0xf0;args=[r[0],*fp]
   for offset,value in zip([0x124,0x128,0x12c],values[2:5]):store(RAM+offset,value)
  elif name=='sincos':
   assert STACK-240<=r[0]<=STACK-4 and STACK-240<=r[1]<=STACK-4
   assert r[1]==r[0]+4;args=[fp[0]]
   store(r[0],values[5]);store(r[1],values[6])
  elif name=='park':
   assert r[:2]==[RAM+0x30,RAM+0x34];args=[*r[:2],*fp]
   store(r[0],values[7]);store(r[1],values[8])
  elif name=='pi':
   assert r[0] in (RAM+0x284,RAM+0x2b0);args=[r[0],*fp[:2]]
   result=values[9 if r[0]==RAM+0x284 else 10]
   store(r[0]+0x28,result)
  elif name=='limit':
   assert r[0]==RAM;args=[r[0],int.from_bytes(c.mem_read(RAM+0x40,4),'little'),int.from_bytes(c.mem_read(RAM+0x44,4),'little')]
   store(RAM+0x40,values[11]);store(RAM+0x44,values[12])
  elif name=='inverse':
   assert r[:2]==[RAM+0x38,RAM+0x3c];args=[*r[:2],*fp]
   store(r[0],values[13]);store(r[1],values[14])
  elif name=='prepare':
   assert r[0]==RAM+0xd4;args=[r[0],*fp[:2]]
   c.mem_write(r[0]+2,bytes([values[15]&255]))
  elif name=='pwm':
   assert r[:2]==[PWM,RAM+0xd4];args=r[:2]
  elif name=='polarity':
   assert r[:2]==[ACQ,values[15]&255];args=r[:2];c.mem_write(ACQ,bytes([r[1]]))
  self.calls.append((name,args,c.reg_read(UC_ARM_REG_FPSCR)))
  self.trace.append(('call',name,args))
  c.reg_write(UC_ARM_REG_CPSR,(c.reg_read(UC_ARM_REG_CPSR)&~0xf0000000)|0xa0000000)
  for i,reg in enumerate([UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]):c.reg_write(reg,0x91827300+i)
  for i in range(16):c.reg_write(UC_ARM_REG_S0+i,0x3f123450+i)
  if name=='pi':c.reg_write(UC_ARM_REG_S0,result)
  c.reg_write(UC_ARM_REG_PC,c.reg_read(UC_ARM_REG_LR))
 def run(self,case,fpscr):
  before,sample,self.values=case;c=self.cpu;self.trace=[];self.calls=[]
  c.mem_write(RAM,before);c.mem_write(ACQ,b'\x8b'*48);c.mem_write(PWM,b'\x93'*12)
  for address,length in [(ACQ,48),(PWM,12)]:
   c.mem_write(address-16,b'\x9c'*16);c.mem_write(address+length,b'\x9c'*16)
  c.mem_write(TIMER,struct.pack('<I',sample));c.mem_write(STACK-256,b'\x6d'*272)
  c.mem_write(RAM-16,b'\x3a'*16);c.mem_write(RAM+792,b'\x3a'*16)
  saved={UC_ARM_REG_R4+i:0x12468000+i for i in range(8)}
  saved.update({UC_ARM_REG_D8+i:0x1234567812340000+i for i in range(8)})
  for reg,value in saved.items():c.reg_write(reg,value)
  c.reg_write(UC_ARM_REG_R0,RAM);c.reg_write(UC_ARM_REG_SP,STACK);c.reg_write(UC_ARM_REG_LR,STOP|1)
  self.initial_fpscr=fpscr
  c.reg_write(UC_ARM_REG_FPSCR,fpscr)
  assert c.reg_read(UC_ARM_REG_FPSCR)==fpscr
  c.emu_start(ENTRY|1,STOP,count=1500)
  assert c.reg_read(UC_ARM_REG_PC)==STOP and c.reg_read(UC_ARM_REG_SP)==STACK
  assert all(c.reg_read(reg)==value for reg,value in saved.items())
  assert bytes(c.mem_read(STACK-256,16))==b'\x6d'*16 and bytes(c.mem_read(STACK,16))==b'\x6d'*16
  assert bytes(c.mem_read(RAM-16,16))==b'\x3a'*16 and bytes(c.mem_read(RAM+792,16))==b'\x3a'*16
  for address,length in [(ACQ,48),(PWM,12)]:
   assert bytes(c.mem_read(address-16,16))==b'\x9c'*16 and bytes(c.mem_read(address+length,16))==b'\x9c'*16
  return dict(state=bytes(c.mem_read(RAM,792)).hex(),acq=bytes(c.mem_read(ACQ,48)).hex(),pwm=bytes(c.mem_read(PWM,12)).hex(),calls=self.calls,fpscr=c.reg_read(UC_ARM_REG_FPSCR),trace=self.trace)
def cases():
 rng=random.Random(0x1258);result=[]
 corners=[0,0x80000000,1,0x80000001,0x7f800000,0xff800000,0x7fc00123,0x7f800123,0xffc00456,bits(1),bits(-1),bits(24),bits(-24),bits(0.005),bits(3.141593),0x7f7fffff]
 for i in range(320):
  state=bytearray(rng.randbytes(792));sample=rng.getrandbits(32)
  for off in [0x14,0x18,0x1c,0x38,0x3c,0x4c,0x54,0xa0,0xa4]:put(state,off,rng.choice(corners) if i>=64 else bits(rng.uniform(-10,10)))
  state[0xcc]=[0,1,2,255][i%4];state[0x5c]=[0,1,2,255][i//4%4];state[0x72]=i//16%2
  for off in [0x74,0x80,0x88,0x8c,0x90]:put(state,off,rng.getrandbits(32))
  if i<64:
   put(state,0x74,sample-100);put(state,0x80,200);put(state,0x88,1000);put(state,0x8c,1000);put(state,0x90,1000)
  put(state,0x310,ACQ);put(state,0x314,PWM)
  values=[rng.choice(corners) if i>=64 else bits(rng.uniform(-10,10)) for _ in range(16)]
  result.append((bytes(state),sample,values))
 original=result.copy();index=0
 for mode in (0,1,2,255):
  for direction in (0,1,2,255):
   for interpolate in (0,1):
    for elapsed in (0,1,99,100,101,0x7fffffff,0x80000000,0xffffffff):
     for interval in (0,1,99,100,101,0xffffffff):
      before,sample,values=original[index%len(original)];state=bytearray(before)
      state[0xcc]=mode;state[0x5c]=direction;state[0x72]=interpolate
      state[0xd1]=index%2;state[0x98]=(0,16,17,255)[index//2%4]
      put(state,0x74,sample-elapsed);put(state,0x80,interval)
      put(state,0x88,100);put(state,0x8c,100);put(state,0x90,(0,1,0xffffffff)[index%3])
      result.append((bytes(state),sample,values));index+=1
 for raw in range(256):
  for which in ('mode','direction'):
   before,sample,values=original[raw%len(original)];state=bytearray(before)
   state[0xcc]=2;state[0x5c]=1;state[0x72]=1;state[0xd1]=0;state[0x98]=17
   state[0xcc if which=='mode' else 0x5c]=raw
   put(state,0x74,sample-50);put(state,0x80,100);put(state,0x88,100);put(state,0x8c,100);put(state,0x90,0)
   result.append((bytes(state),sample,values))
 return result
def eager_counterexample():
 state=bytearray(792);sample=5000
 state[0xcc]=1;state[0x5c]=255
 for offset,value in [(0x4c,0xbf800000),(0x74,4900),(0x80,200),(0x88,1000),(0x8c,1000),(0x90,1000),(0x310,ACQ),(0x314,PWM)]:put(state,offset,value)
 values=[0]*16;values[4]=0x7f7fffff
 return bytes(state),sample,values
def self_test(path,out):
 code,provenance=inputs(path);original=json.loads(path.read_bytes());tests=[]
 def reject(label,report=None,elf=None):
  try:inputs(path,report,elf)
  except (ValueError,AssertionError):tests.append(label)
  else:raise AssertionError('accepted '+label)
 for key in ('compiler_sha256','stock_md5'):
  bad=copy.deepcopy(original);bad[key]='0'*64;reject(key,bad)
 bad=copy.deepcopy(original);bad['source_sha256'][next(iter(bad['source_sha256']))]='0'*64;reject('source_sha256',bad)
 bad=copy.deepcopy(original);bad['source_sha256']={};reject('empty provenance',bad)
 bad=copy.deepcopy(original)
 bad['source_sha256']={p:h for p,h in bad['source_sha256'].items() if not p.endswith('mclib_commands.c')}
 reject('missing C provenance',bad)
 for key in ('address','actual_size','expected_size','candidate_sha256','expected_sha256'):
  bad=copy.deepcopy(original);row=next(r for r in bad['results'] if r['name']==NAME)
  row[key]=row[key]+2 if isinstance(row[key],int) else '0'*64;reject(key,bad)
 elf_path=path.parent/(NAME+'.elf');original_elf=elf_path.read_bytes();parsed=ELFFile(io.BytesIO(original_elf))
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
 bad=bytearray(original_elf);bad[parsed.get_section_by_name('.text')['sh_offset']]^=1;reject('candidate byte',elf=bytes(bad))
 data_index=next(i for i,s in enumerate(table.iter_symbols()) if s.name.startswith('$d') and s['st_value']==ENTRY+len(code)-44)
 bad=bytearray(original_elf)
 struct.pack_into('<I',bad,table['sh_offset']+data_index*table['sh_entsize']+4,ENTRY+len(code)-42)
 reject('literal pool mapping',elf=bytes(bad))
 # Decoder-only corrupt control: replace the LDR before stock's first BL with
 # NOP/IT EQ. The unchanged BL must now be rejected, not silently mocked.
 bad=bytearray(stock);struct.pack_into('<HH',bad,0x129e-0x1258,0xbf00,0xbf08)
 try:Runner(bytes(bad))
 except AssertionError as error:
  assert 'BL inside IT' in str(error);tests.append('conditional mocked BL')
 else:raise AssertionError('accepted conditional mocked BL')
 vector=eager_counterexample()
 for mode in range(16):
  fpscr=(mode&3)<<22|(mode>>2)<<24
  # A fresh emulator every time: the explicit entry/acquire/observer assertions
  # must not rely on a previous mode-zero case warming the FP context.
  Runner(stock).run(vector,fpscr)
 tests.append('fresh FP context all16 modes')
 source=next(ROOT/p for p in original['source_sha256'] if p.endswith('/mclib_commands.c'))
 text=source.read_text();needle='float reverse_phase = observed_angle - commanded_angle;'
 assert text.count(needle)==1,'negative control needs the independently evaluated reverse subtraction'
 mutant=text.replace(needle,'float reverse_phase = -(commanded_angle - observed_angle);')
 with tempfile.TemporaryDirectory(prefix='gd-loop-b-negative-') as directory:
  temporary=Path(directory);src=temporary/'negative.c';obj=temporary/'negative.o';elf=temporary/'negative.elf'
  src.write_text(mutant)
  compile_command=[original['compiler'],*original['flags'],'-DMCLIB_CONTROL_LOOP_B','-I',str(source.parent),'-c',str(src),'-o',str(obj)]
  link_command=[original['compiler'],*original['flags'][:4],'-nostdlib','-Wl,--entry='+NAME,'-Wl,-T,'+str(path.parent/(NAME+'.ld')),str(obj),'-o',str(elf)]
  subprocess.run(compile_command,check=True);subprocess.run(link_command,check=True)
  negative=candidate(elf);old=Runner(stock).run(vector,0x00400000);new=Runner(negative).run(vector,0x00400000)
  assert old['state']==new['state'] and old['acq']==new['acq'] and old['pwm']==new['pwm']
  assert old['fpscr']&4 and not new['fpscr']&4,'missing eager-overflow control was not detected'
  control=dict(source_sha256=sha(mutant.encode()),elf_sha256=sha(elf.read_bytes()),candidate_sha256=sha(negative),
   actual_size=len(negative),stock_fpscr=old['fpscr'],negative_fpscr=new['fpscr'],
   explanation='Negating the selected forward result drops overflow from the independently evaluated reverse subtraction; final caller state is otherwise equal.')
 tests.append('missing eager FP operation source control')
 provenance.update(scope='loop B provenance/decoder/lazy-FP/negative-source self-tests',tests=tests,negative_control=control)
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(provenance,indent=2)+'\n')
 print(f'{len(tests)}/{len(tests)} provenance/extent/IT/lazy-FP/negative-source self-tests PASS.')
 return 0
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--isolated-report',type=Path,default=ROOT/'work/mainBoardGD-motor/results.json')
 parser.add_argument('--out',type=Path,default=ROOT/'work/mainBoardGD-loop-b-model.json')
 parser.add_argument('--self-test',action='store_true');args=parser.parse_args();path=args.isolated_report.resolve()
 if args.self_test:return self_test(path,args.out.with_name(args.out.stem+'-selftest.json'))
 code,report=inputs(path);a,b=Runner(stock),Runner(code);vectors=cases();count=0;digest=hashlib.sha256()
 assert len(vectors)==2368
 for mode in range(16):
  fpscr=(mode&3)<<22|(mode>>2)<<24
  for index,case in enumerate(vectors):
   old,new=a.run(case,fpscr),b.run(case,fpscr)
   if old!=new:
    failed=[key for key in old if old[key]!=new[key]]
    raise ValueError('loop B mismatch: '+repr((index,hex(fpscr),failed,old,new)))
   before,sample,values=case;digest.update(before+struct.pack('<17I',sample,*values)+struct.pack('<I',fpscr))
   digest.update(json.dumps(new,separators=(',',':')).encode());count+=1
 report.update(scope='bounded complete loop-B caller state/ordered-access/call/FPSCR/ABI model',whole_image_verified=False,
  results=[dict(name=NAME,cases=count,passed=count,stock_entry=ENTRY,candidate_entry=ENTRY,
    expected_size=SIZE,actual_size=len(code),byte_exact=stock==code,result_sha256=digest.hexdigest())],
  limitations=[
   'Actual caller ARM/FP instructions execute; all11 external call sites use explicit deterministic acquisition/observer/trig/PI/voltage/PWM mocks, not callee equivalence or a full motor oracle.',
   'Compares all792 motor bytes,48 acquisition bytes,12 PWM bytes, combined ordered state/timer accesses and call arguments; guarded literal/stack reads are excluded from the trace.',
   'Mocks clobber r0-r3/r12/s0-s15 and APSR NZCV, preserve FPSCR, validate aligned callSP and pointer contracts, and make specified deterministic output writes.',
   'Static Thumb decoding ends at the ELF literal-pool mapping and rejects calls inside IT. Mocked BL/return boundaries clear stale emulator ITSTATE; this does not validate physical interrupt or exception timing.',
   'A real stock VLDR warms the emulator lazy FP context before test state; requested FPSCR is asserted before/at entry and at the first pre-arithmetic call boundaries for every case.',
   'Compares complete final FPSCR and FPSCR at every call; four rounding modes crossed with FZ/DN, not every initial sticky flag setting.',
   'Zero intervals and invalid/out-of-range float-to-int inputs are target VDIV/VCVT diagnostics, not portable-C defined-behavior claims.',
   'Finite deterministic vectors with synchronous RAM/timer latches; not exhaustive inputs, asynchronous state mutation, hardware or whole-firmware verification.'])
 args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(report,indent=2)+'\n')
 print(f'{NAME}: {count}/{count} complete state/ordered-access/call/FPSCR/ABI cases PASS.')
 return 0
if __name__=='__main__':raise SystemExit(main())
