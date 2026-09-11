# mainBoardGD motor control

Assembly-based recovery record, 2026-09-09. The seven command handlers
and their consumers are identified in the stock image, MD5
`fb64911bac422a27d7ed7fab3597603f`. This is a semantic account for source
reconstruction, not compiled or byte-matched C. Addresses are execution
addresses; **all structure offsets below are bytes**. Field names are
descriptive working names unless they come from a command declaration.

## Object model and initialization

`command_config_mclib` at ITCM `0x00000e40` calls
`oid_alloc(oid, 0xe41, 8)` at `0x00000e50`. The object contains the
stepper enumeration byte at offset zero and a motor-state pointer at
offset four. The other six handlers validate the OID through
`oid_lookup` at `0x00003fd8`, using the same `0xe41` type tag. Invalid
OID bounds/type cause `Invalid oid type` shutdown at `0x00004002`–`0x00004008`.

The existing pointer table at RAM `0x24002504` selects physical states:

| Enumeration | Value | Motor-state address |
|---|---:|---|
| `stepper_x` | 0 | `0x2400282c` |
| `stepper_y` | 1 | `0x24002514` |
| `stepper_z` | 2 | `0x24002b44` |
| `extruder` | 3 | `0x240021ec` |

The normal state stride is `0x318`, consistent with a last pointer at
offset `0x314`. Configuration indexes this table with the full 32-bit
`args[1]` at `0x00000eac`, without a bounds check. Only the saved enum
byte is truncated, at `0x00000eaa`. Multiple configured OIDs can refer
to the same physical state; configuration does not allocate another motor.

The registered `mclib_init` callback is the ITCM wrapper at
`0x00003d00`, reached from the init runner at `0x000027c8`. It calls
the lower hardware setup at flash `0x08001710` through veneer
`0x00005c02`, then initializes states, default currents and microsteps.
The wrapper gives X/Y microstep exponent 5 and Z/E exponent 4. Ghidra's
name `mclib_init` on the flash routine alone does not identify the entire
callback; see [startup-layout.md](startup-layout.md).

## Command behavior

| Command | ITCM address | Result |
|---|---|---|
| `config_mclib` | `0x00000e40` | binds an OID and derives motor/PI/plant parameters |
| `mclib_config_microstep` | `0x000018a8` | sets the microstep exponent and interpolation flag |
| `mclib_config_stalldetect` | `0x000018d0` | sets the filtered-current stall threshold |
| `mclib_identify_motor` | `0x00001900` | validates the OID, then returns |
| `mclib_set_current` | `0x00001910` | sets run/hold current and recalculates the transition decrement |
| `mclib_set_pid_params` | `0x00001960` | writes both current PI controllers' P/I gains |
| `mclib_set_resonance_damp` | `0x000019a8` | stores harmonic compensation amplitudes/phases |

These handlers update live motor state without masking interrupts in
their bodies. Their writes should not be silently grouped into a new
atomic operation in recovered source.

### Configuration and numeric operations

`config_mclib` uses unsigned-to-float conversions. Its constants are in
the pool at `0x00000eec`–`0x00000f00`. Let `R`, `L` and `Km` denote
the derived values:

| Expression | State offset | Store instruction |
|---|---|---|
| `R = float(args[2]) / 1000` | `+0x00` | `0x00000eca` |
| `L = float(args[3]) / 1000000` | `+0x04` | `0x00000ec2` |
| `Km = (float(args[4]) / 1000000) / 50` | `+0x08` | `0x00000eba` |
| `Kp = L * 6283.186` | `+0x284`, `+0x2b0` | `0x00000ed2`, `0x00000eda` |
| `Ki = (Kp * (R / L)) * 0.00005` | `+0x288`, `+0x2b4` | `0x00000ed6`, `0x00000ede` |
| `a = fmaf(-0.00005 / L, R, 1)` | `+0xf0` | `0x00000ee2` |
| `b = 0.00005 / L` | `+0xf4` | `0x00000ee6` |

The `a` expression uses `vfma` at `0x00000eb6`: separating multiply
and add changes rounding. Keep operation order and single precision when
reconstructing it. No range checks protect zero `L` or the other inputs.
The R/L scalings are consistent with milliohms and microhenries. The
host-side unit of `Km` is not established. The constants are consistent
with a 50 microsecond control period and 1 kHz current-loop tuning;
verifying the actual interrupt period still requires the timer setup.

### Microsteps and interpolation

At `0x000018bc`, `ldrh` reads the microstep argument as 16 bits. The
interpolation argument truncates to byte `+0x72` at `0x000018c0`;
consumers treat any nonzero value as enabled. The tail call at
`0x000018c8` reaches flash `0x080015b8` through veneer `0x00005b62`.
That helper stores:

| Offset | Value | Store instruction |
|---|---|---|
| `+0x6a` | low 16 bits of `1 << (14 - mstep)` | `0x080015c2` |
| `+0x70` | 16-bit `mstep` | `0x080015ca` |
| `+0x8c` | `0x007f2815 << (8 - mstep)` | `0x080015da` |

Normal `mstep` is an exponent: 0 means full step, 4 means 16
microsteps, 5 means 32, and 8 means 256. The implementation uses ARM
register shifts without range checks. The expressions above describe
normal inputs; naive C shifts with negative or excessive counts would
introduce undefined behavior for other inputs and would not model stock.

Loop A at `0x08000e0a` onward uses elapsed time divided by the step
interval, multiplied by the increment, to update angle `+0x4c` when
interpolation is enabled. Loop B contains the corresponding path.

### Stall detection and the endstop path

`mclib_config_stalldetect` converts unsigned `stallthrs` to float, divides
by 1000 and stores the threshold at `+0xa4`, at `0x000018f4`.

Loop A at `0x08000cda`–`0x08000d4e` computes a signed projection:

```text
projection = current_alpha(+0x28) * observer_cos(+0x128)
           - current_beta(+0x2c)  * observer_sin(+0x124)
filtered(+0xa0) += (projection - filtered) * 0.005
magnitude(+0x9c) = abs(filtered)
raw_stall(+0xce) = magnitude < threshold(+0xa4)
```

At `0x08000d52`–`0x08000d74`, output byte `+0xd2` is gated by
`+0xd1 == 0`, `+0xd0 == 0`, and byte `+0x98 >= 17`. Loop B contains
the equivalent sequence ending at `0x080013a8`. The exact meanings of
the mode/gating bytes remain open; the measured threshold is on filtered
current projection, not position error.

GPIO input helper `0x000030a8` substitutes this output for three pins:

| Pin value | Motor | Load instruction |
|---|---|---|
| 147 / `0x93` | Y | `0x000030be` |
| 151 / `0x97` | X | `0x000030da` |
| 155 / `0x9b` | Z | `0x000030cc` |

Each reads motor byte `+0xd2`. Other values reach ordinary GPIO handling
at `0x000030e0`; no extruder override appears. This connects the stall
calculation to Klipper's endstop reads.

### Identify stub

`mclib_identify_motor` occupies `0x00001900`–`0x0000190d` inclusive
and tail-branches to `oid_lookup` at `0x0000190a`. It never loads
`umax` or `umin`, modifies no motor state, and sends no response. It is
an OID-validation stub, not an identification algorithm.

### Current setting and hold transition

`mclib_set_current` converts both unsigned arguments to float and divides
by 1000. The run-current call at `0x0000193a` reaches flash
`0x08001220` through veneer `0x00005b6c`. The hold-current tail call
at `0x00001954` reaches `0x08001178` through `0x00005b76`.

The actual ABI passes the state pointer in `r0` and current in `s0`.
Ghidra's apparent integer argument values/order are wrong here. The
run setter stores `+0x10`. The hold setter uses `vminnm.f32` at
`0x08001180` to clamp hold against run and stores `+0x14`. Both compute:

```text
delta = run(+0x10) - hold(+0x14)
decrement(+0x18) = transition_ticks(+0x94) != 0
                ? (delta / float(transition_ticks)) * 5000
                : delta
```

`transition_ticks` is a provisional name for the unsigned word at
`+0x94`; its time unit is not established. The constant 5000 is at
`0x080011ac` / `0x08001250`. `vseleq.f32` at `0x080011a2` and
`0x08001246` selects the zero-duration case. These VFPv5 operations
are not faithfully represented by the current Ghidra export. Preserve
the numeric-min instruction's NaN behavior as well as the ordinary clamp.

Loop A at `0x08000e8e` onward subtracts the decrement from active
current `+0x1c` toward hold after an idle condition; loop B has the
equivalent path. The setters do not directly write active current and do
not clamp run current to a maximum.

### PI gains

`mclib_set_pid_params` divides unsigned `kp` and `ki` by 1000 and writes both
pairs at `+0x284/+0x288` and `+0x2b0/+0x2b4`, at
`0x00001990`–`0x0000199c`. No derivative term or additional sample-time
factor is introduced, and the command does not reset accumulated error.

The PI consumer at flash `0x080020d0` computes setpoint minus feedback,
adds `Ki * error` to the integrator, clamps it, computes
`Kp * error + integrator`, and clamps the output. Controller blocks have
stride `0x2c`, beginning at `+0x284`, `+0x2b0`, and `+0x2dc`; this
command leaves the third block untouched.

### Resonance compensation

At `0x000019bc`, `ubfx` extracts
`index = (args[1] >> 1) & 255`. Indices greater than two return after
OID validation. For ordinary byte-sized `tdx`, 0/1 select slot zero,
2/3 select one, 4/5 select two, and values of six or greater do nothing.

The unsigned amplitude and two phase arguments are converted to float
and divided by 1000. Stores at `0x000019f0`, `0x000019f8`, and
`0x000019fc` fill the selected elements of:

| Array | Element offsets |
|---|---|
| amplitudes | `+0xa8`, `+0xac`, `+0xb0` |
| phase set 1 | `+0xb4`, `+0xb8`, `+0xbc` |
| phase set 2 | `+0xc0`, `+0xc4`, `+0xc8` |

Loop A uses harmonics **1, 2 and 4**, with the fourth harmonic explicit
at `0x08001044`–`0x08001054`:

```text
Id_target = -A0*sin(theta + phase0)
            -A1*sin(2*theta + phase1)
            -A2*sin(4*theta + phase2)
```

A nonzero direction byte `+0x5c` selects phase set 1 at
`0x08000fa2` onward; zero selects phase set 2 at `0x08001000`.
The sine helper at `0x08002b50` wraps by `2*pi` and interpolates a
quarter-wave table, establishing radians for these scaled phase values.

The path requires step interval `+0x80 >= 2468`, checked at
`0x08000f92`–`0x08000fa0`, and is bypassed by alternative mode
`+0xcf == 1` at `0x08000f2a`–`0x08000f30`. Only loop A consumes
these arrays. Consequently all four motors accept the command's stored
values, but only X/Y use resonance compensation in this image.

## Interrupt dispatch and remaining uncertainty

| ITCM interrupt handler | Motor | Flash control loop |
|---|---|---|
| IRQ18, `0x00000000` | X | A, `0x08000c30`, through veneer `0x00005b1c` |
| IRQ18, `0x00000000` | extruder | B, `0x08001258` |
| IRQ11, `0x00000080` | Y | A, `0x08000c30` |
| IRQ12, `0x000000c8` | Z | B, `0x08001258` |

The original field names, units for timing words `+0x90` and `+0x94`,
host-side `Km` units, and complete mode semantics at `+0xcc`, `+0xcf`,
`+0xd0` and `+0xd1` remain unresolved. The hard-float argument registers,
VFPv5 min/select operations, fused math, and hardware shifts are source
reconstruction constraints. Ghidra's coprocessor placeholders and inferred
parameter types cannot settle them.
