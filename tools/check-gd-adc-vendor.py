#!/usr/bin/env python3
"""Complete ADC SDK C bodies at their stock ITCM addresses.

Excludes already-owned IRQ flag clear/get at04d8/04e0 and fault/reset entries
at0280/0288. Function bounds exclude inter-function zero alignment; calibration
includes its real NOP. All register/selector behaviors are in adc_vendor.c.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
from gd_function_gate import main, ROOT

# Retired 2026-09-11: every span is GigaDevice's gd32h7xx_adc.c (check-gd-sdk.py).
PROFILE = []
UNITS = {'adc_' + define.lower(): ('adc_vendor.c', ['GD_ADC_' + define])
         for _, _, _, define in PROFILE}
CASES = [(name, address, size) for name, address, size, _ in PROFILE]
CASE_UNITS = {name: 'adc_' + define.lower() for name, _, _, define in PROFILE}
SYMBOLS = {'rcu_periph_reset_enable': 0x5b31,
           'rcu_periph_reset_disable': 0x5b3b}

def self_test():
    """Native actual-C channel arithmetic tests, not a hardware bus emulator.

    ARM compilation separately checks target ABI. Native test suppresses only
    target-pointer layout declarations and maps registers below2^32, retaining
    unchanged C bodies. It does not test MMIO ordering or calibration polling.
    """
    harness = r'''
#define _GNU_SOURCE
#include <stdint.h>
#include <sys/mman.h>
#include <stdio.h>
void adc_inserted_channel_config(uint32_t,uint32_t,uint32_t,uint32_t);
void adc_regular_channel_config(uint32_t,uint32_t,uint32_t,uint32_t);
void adc_channel_length_config(uint32_t,uint32_t,uint32_t);
void adc_resolution_config(uint32_t,uint32_t);
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"failed line %d\n",__LINE__); return 1; } } while(0)
int main(void) {
    void *map=mmap((void*)0x40012000,0x1000,PROT_READ|PROT_WRITE,
                   MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    CHECK(map != MAP_FAILED);
    const uint32_t adc=0x40012400;
    uint32_t *p=(uint32_t *)(uintptr_t)adc, before[32], expected[32];
    const uint32_t values[]={0,1,2,3,4,15,16,255,256,0x100,0x400,0x800,
                            0x08000000,0x7fff,0x8000,0x80000000,0xffffffff};
    /* Independent rank-to-offset model, including raw channel overflow. */
    for(unsigned which=0;which<2;++which)
      for(unsigned rank=0;rank<520;++rank)
       for(unsigned v=0;v<17;++v) {
        for(unsigned i=0;i<32;++i) p[i]=before[i]=expected[i]=0xa5c38000u+i*0x31415u;
        p[18]=before[18]=expected[18]=(before[18]&~0x300000u)|((v&3)<<20);
        uint32_t channel=values[v],sample=values[(v+7)%17];
        uint32_t packed=((sample&0x3ff)<<5)|channel;
        unsigned slot=which?(uint8_t)(rank+3-((before[18]>>20)&3)):rank;
        if((which&&slot<4)||(!which&&slot<16)) {
          unsigned offset,shift=0; int add=0;
          if(which) {
            if(slot==0) { offset=0x50; add=1; }
            else if(slot==3) { offset=0x48; add=1; }
            else { offset=0x4c; shift=(slot-1)*16; }
          } else {
            if(slot==0) { offset=0x44; add=1; }
            else if(slot==15) { offset=0x24; add=1; }
            else { offset=0x40-((slot-1)/2)*4; shift=((slot-1)%2)*16; }
          }
          uint32_t old=before[offset/4]&~(0x7fffu<<shift);
          expected[offset/4]=add?old+packed:old|(packed<<shift);
        }
        if(which) adc_inserted_channel_config(adc,rank,channel,sample);
        else adc_regular_channel_config(adc,rank,channel,sample);
        for(unsigned i=0;i<32;++i) CHECK(p[i]==expected[i]);
       }
    /* These invalid selectors return before ANY access to null address. */
    adc_regular_channel_config(0,0xffffffff,0xffffffff,0xffffffff);
    adc_channel_length_config(0,0,1); adc_channel_length_config(0,1,0);
    adc_channel_length_config(0,1,17); adc_channel_length_config(0,2,5);
    for(unsigned group=0;group<4;++group) for(unsigned n=0;n<19;++n) {
      p[9]=p[18]=0xffffffff;
      adc_channel_length_config(adc,group,n);
      CHECK(p[9]==((group==1&&n>=1&&n<=16)?
                   (0xff0fffffu|((n-1)<<20)):0xffffffff));
      CHECK(p[18]==((group==2&&n>=1&&n<=4)?
                    (0xffcfffffu|((n-1)<<20)):0xffffffff));
    }
    for(unsigned a=0;a<3;++a) for(unsigned v=0;v<17;++v) {
      uint32_t base=adc+a*0x400,x=values[v];
      uint32_t *q=(uint32_t *)(uintptr_t)base;
      q[1]=0xffffffff; adc_resolution_config(base,x);
      uint32_t field=a==2?(x?((x-1)&3):0):(x==4?0:(x&3));
      CHECK(q[1]==(0xfcffffff|(field<<24)));
    }
    CHECK(munmap(map,0x1000)==0);
    puts("PASS: actual C rank wrap, masks, overflow, invalid lengths/selectors and ADC resolution.");
    return 0;
}
'''
    source = ROOT / 'mcu/mainBoardGD/recovered/adc_vendor.c'
    with tempfile.TemporaryDirectory(prefix='gd-adc-test-') as directory:
        path = Path(directory)
        objects = []
        for define in ('INSERTED', 'REGULAR', 'LENGTH', 'RESOLUTION'):
            obj = path / (define + '.o')
            subprocess.run(['cc', '-O2', '-Wall', '-Wextra', '-Werror',
                            '-DGD_MCLIB_HARDWARE_H', '-include', 'stdint.h',
                            '-DGD_ADC_' + define, '-c', str(source), '-o', str(obj)], check=True)
            objects.append(str(obj))
        test = path / 'test.c'
        test.write_text(harness)
        binary = path / 'test'
        subprocess.run(['cc', '-O2', str(test), *objects, '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    else:
        raise SystemExit(main('adc-vendor', CASES, UNITS, CASE_UNITS, SYMBOLS))
