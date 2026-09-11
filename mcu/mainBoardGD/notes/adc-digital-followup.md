# ADC and digital-toggle follow-up

This pass uses the unchanged shared ATfE 22.1.0 configuration. Experiments
are retained under `/tmp/gd-adc-next.YZF2y5/`; these temporary files are not
build dependencies. Every reported byte comparison checks the complete
stock span, section address, Thumb symbol, symbol size and ELF entry.

## ADC deinitialization

Stock `gd_motor_adc_deinit` at ITCM `0x390..0x3d8` compares ADC addresses
in order `0x40012400`, `0x40012c00`, `0x40012800`. It selects reset IDs
`0x908`, `0x90a`, `0x909`, respectively, and invokes reset-enable through
`0x5b30`, then tail-calls reset-disable through `0x5b3a`. Every other
32-bit address returns without either call.

The initial C candidate is 72 bytes, with 65/72 bytes matching. Its test
order is ADC0/ADC1/ADC2 instead of stock's ADC0/ADC2/ADC1; constant-block
ordering also differs. Three new hand hypotheses—lossless unsigned-wide
address comparison, an explicit switch in stock test order, and a signed
reset-ID local—each produce the same complete baseline bytes. The earlier
branch-local pair-of-calls spelling was already tested and is not repeated.

A two-worker, 20,000-iteration raw-byte search follows these trials. Its
objective is the full 72-byte span, without instruction normalization.
Self-tests score baseline 7, stock target 0, growth/truncation 1, wrong
entry 1,000,000 and shifted section/symbol/entry 3,000,000. Candidate C
contains no target bytes, assembly body, register constraints or altered
compiler settings. The search finishes 20,000 iterations in 206.12 seconds:
4,846 compile-error iterations, 15,154 non-error iterations (which can
include cached candidates), and zero internal errors. Session 30238 exits
cleanly. Three improving outputs are independently reviewed:

- `output-4-1` selects the ADC2 reset ID before its comparison. It preserves
  meaning and restores stock's ADC0/ADC2/ADC1 test order, matching 68/72.
- `output-6-1` reverses enable/disable calls; rejected by source inspection
  and actual-instruction call-trace checking.
- `output-6-2` swaps reset IDs for ADC1 and ADC2; rejected by the same checks.

The valid idea is simplified to nested default selections, with no empty
branch, and adopted in `recovered/adc_vendor.c`. The full canonical module
emits **68/72 bytes** at the unchanged 72-byte extent. All 15 other ADC
section hashes, including all eleven exact functions, remain unchanged.
The only residual differences are two branch destinations and the order
of the ADC0/ADC2 reset-ID constant blocks. This is matching C control-flow
reconstruction, not a claim to know the original SDK spelling.

An independent forward-label dispatch trial regresses to 64/72 and is
rejected. The independent scratch model in
`/tmp/gd-adc-deinit-review.KL6Iq9/model.py` passes **2,270 cases** for both
the cleaned candidate and fresh canonical ELF: 100 recognized-address
cases and 2,170 invalid-address cases. It checks the three mappings,
ordered calls, no wrapper MMIO/data accesses outside its stack, r4-r11,
SP, return PC and stack canaries; mocked RCU calls deliberately clobber
caller-saved data registers. RCU effects and hardware reset timing are
explicitly not modeled. The two invalid outputs fail with reversed call
order for ADC0 and reset ID `0x909` instead of `0x90a` for ADC2, respectively.

## ADC length: additional hand diagnostics

Three further source-only trials retain independent clear/field masks:

| Form | Candidate extent | Matching bytes out of 70 |
|---|---:|---:|
| Unsigned-wide count-minus-one range check | 76 | 12 |
| Clear-mask local declared/assigned before field mask | 76 | 11 |
| Explicit count-zero or count-above-limit checks | 76 | 12 |

All overrun the 70-byte stock body and are rejected. The first and third
emit the same bytes as the previously rejected independent-mask form.
They neither repair the count-range lowering nor recover the stock
register allocation. No length permutation search was run in this pass;
these are bounded hand diagnostics, not an exhaustion claim. The canonical
ADC source and its native length/channel/resolution behavior tests remain
unchanged by these trials.

## Digital-toggle conditional selection

`digital_toggle_event` at ITCM `0x29f0..0x2a3c` has a 76-byte baseline
with 73/76 matching bytes. Stock selects the duration offset by initially
loading 12, then conditionally replacing it with 16 for an old ON flag at
`0x2a04..0x2a0a`. The candidate uses the complementary default and condition.
All later bytes agree, including flag publication before the comparison,
the end-time reload, calls and return.

Three hand forms emit the exact same baseline bytes: snapshot old flags
and reverse the source arms; select an explicit duration-field pointer;
and use a lossless 64-bit predicate mask. None is adopted. A separate
two-worker search uses the full 76-byte score with the same entry/extent
negative controls (baseline score 3).

A retained 75/76-byte candidate (`digital_search/output-1-1`) is invalid:
it snapshots old flags but still chooses the on-duration for an old ON
bit, before publishing the toggle. This reverses the required duration.
Independent recompilation and the execution oracle reject it. A smaller
byte distance is not semantic recovery.

The scratch `digital_model.py` passes 3,072 cases for the baseline and each
of the three unchanged hand forms. It covers all 256 flag bytes, wrap and
signed timer boundaries, random full-word timing fields, complete object
state, ordered reads/writes, calls, return value, r4-r11/SP/return PC and
stack guards. The six stock `timer_is_before` bytes execute directly;
GPIO toggle is explicitly mocked with ABI-permitted scratch-register
clobbers. An independent integer oracle checks duration selection, wrapped
time addition and end-time handling. This is synchronous model evidence,
not physical GPIO/PWM timing, interrupt-interleaving or whole-image proof.

The digital search completes **20,000 iterations in 311.94 seconds**, with
1,967 compile-error iterations, 18,033 non-error iterations and zero
internal errors. Its only saved improvement is the invalid 75/76 candidate
above. Session 10429 exits cleanly; no digital source change is adopted.
The baseline and minimal typed search input have identical complete bytes.
Three hand attempts plus this finite random search do not prove that no
matching source exists. Search settings preserve the earlier PI mutation
profile; temporary-expression creation can still change meaning, as the
rejected old-flag substitution demonstrates. No iteration count is claimed
to be a count of distinct compiled programs.
