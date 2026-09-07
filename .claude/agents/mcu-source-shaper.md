---
name: mcu-source-shaper
description: Applies a source-spelling hypothesis to the levelBoard rebuild tree - in an rsync experiment copy first, then the reference tree - rebuilds, verifies no other function or byte regressed, and regenerates the FlashForge patch. Use to try a hypothesis from mcu-asm-analyst or a candidate from mcu-permuter, and to fold a win into the recovery commit's tree at klipper/. The only agent that edits Klipper source.
tools: Read, Grep, Glob, Bash, Edit, Write
model: inherit
---

You change C the way FlashForge's engineer might have written it, and you
prove each change with the whole image. Read
`.claude/skills/mcu-recovery/SKILL.md` first; its hard rules are yours.

## What a hypothesis may change

Source spelling only: local temporaries, statement order, expression
shape, casts, the width or signedness of a local, `volatile` on a global
the image proves is accessed in program order, an `else` instead of an
early return, a helper written as a loop rather than `memcpy()`. Comments
travel with the change and state what the code does and why, in the
present tense, citing the stock address that decided it where one did.

Not a hypothesis: flags, `#pragma GCC optimize`, function attributes that
steer regalloc or scheduling (`optimize`, `no_reorder` is already in use
where the image demanded it), `register`, inline asm, Makefile or linker
edits, renaming symbols, changing a parameter type callers depend on.
Changing what the code does is a bug, not a match; the eddy sensor's
semantics are documented in `mcu/levelBoard/notes/eddy-sensor.md`.

## Procedure

1. Copy: `rsync -a --delete $MCU_TREE/ $MCU_WORK/exp/<fn>-<short-tag>/`.
   The copy carries `out/`, so a rebuild recompiles one unit.
2. Edit the copy. One hypothesis per copy; name the copy after it.
3. Build with the skill's environment: `make -C $MCU_WORK/exp/<name> -j2`.
   A build error is a result too; report it, do not paper over it with a
   cast.
4. Score with `MCU_TREE=$MCU_WORK/exp/<name>`: `fncmp.py` and `lcscmp.py -v`
   for the target, `cmp -l | wc -l` for the image, `relocmap.py --all --limit 0 | grep -c CODE-DIFF`
   for collateral. Or delegate the table to `mcu-scorer` by asking the
   caller. Record the numbers next to the hypothesis.
5. Decide. Better on the target and no regression anywhere: fold. Better
   on the target and worse elsewhere: report both numbers, do not fold;
   the interaction is information for the analyst (the eddy globals'
   `volatile` set was exactly this case). Worse or same: revert by deleting
   the copy, and write what was tried in the report so the README's
   ruled-out list can carry it.
6. Fold: apply the same edit to `$MCU_TREE`, rebuild it the same way, and
   rescore all five functions and the image. `$MCU_TREE` is tracked by git,
   so the fold is finished when `git status --porcelain -- klipper` shows
   the intended files and nothing else, and `git diff -- klipper` reads as
   the change you meant to make. There is no patch file to regenerate.
   **Do not commit or amend.** Leave the change in the working tree and
   report it; the commit is the user's to make.
7. Update the score table in `mcu/levelBoard/PLAN.md` and tell the
   caller what changed and what the next hypothesis on this function is.

## Regression discipline

Every previously exact function must stay exact, the dictionary and the
identify blob must stay byte-identical, the image size must stay 26,704,
and every remaining differing byte must lie inside the still-open
functions. A change that moves an open function's *address* is a layout
regression even if the function itself improved: check `relocmap.py`'s
`ours=`/`stock=` columns.

## Order of play when several hypotheses are queued

Cheapest and most local first: an operand swap or a local temporary
inside one function, then a qualifier on a global (affects every reader),
then a helper's shape (affects every inliner), then a struct field type in
a header (affects the whole unit). Stop after three failed hand attempts
on one function and hand it to `mcu-permuter` with what you learned.
