# Static lookup permutation search

The generated static-string lookup has a complete 792-byte code span and
140-byte literal pool. Its current source matches 862/932 bytes overall
(722/792 code bytes and 140/140 pool bytes); the encoder lookup remains
640/640 bytes exact.

A bounded source-permutation run used the unchanged ATfE 22.1.0 command,
the complete generated translation unit, fixed entry/extent/relocations,
and a regression set covering 96 other allocated generated sections. It
completed 20,000 iterations with one worker, 1,125 compile errors, zero
internal failures, and no improving output: the best score remained 70
differing bytes. The strict model passed 1,225 stock-versus-candidate lookup
cases, including malformed and near-match strings, actual stock `strcmp`,
ABI/canary checks, and a wrong-ID negative control.

No candidate was adopted. The finite search does not prove that no source
spelling exists; it rules out this mutation family under the fixed
translation-unit and compiler configuration. Scratch provenance and the
terminal summary are retained in `/tmp/gd-static-permuter.6Cicfg8g/`.
