- start f92bb9cf543c9a799fee716734f9905429131aec
- unblocked: dispatched T1 T2 T3 at 10:06:50; waiting on fixes: none
- tests fast passed=2 failed=4 skipped=0 seconds=0.9
- tests fast passed=33 failed=0 skipped=0 seconds=1.1
- tests fast passed=1 failed=11 skipped=0 seconds=0.3
- tests fast passed=0 failed=6 skipped=0 seconds=1.3
- tests fast passed=111 failed=0 skipped=0 seconds=1.5
- tests fast passed=37 failed=0 skipped=0 seconds=7.6
- commit T1 f702df3137 main checkout root passes
- commit T2 9ee6b4329c note copies into briefs ref
- commit T3 8b009b914e remote ships named brief files
Ruling: T2 maps a token below an already copied folder to its copy only when that copy exists on disk, else copies it on its own (a git-ignored file inside a copied repo) - keeps every named file readable - cost if wrong: one extra small copy
- tests fast passed=82 failed=0 skipped=0 seconds=8.9
- tests fast passed=12 failed=1 skipped=0 seconds=1.3
- tests fast passed=105 failed=0 skipped=0 seconds=2.1
- commit T2 39020a4e94 note copies into briefs ref
- tests full passed=13725 failed=0 skipped=12 seconds=795.2
- tests full passed=13726 failed=0 skipped=12 seconds=868.0
Ruling: main_checkout returns None without a commondir file (a submodule's .git file), dropping the plan's gitdir.parent.parent fallback - FR1 finding: a linked worktree always has commondir - cost if wrong: none
- commit T1 1c76c8050e main checkout root passes
- commit T2 af39c6c6b3 note copies into briefs ref
- tests fast passed=15 failed=2 skipped=0 seconds=1.1
- tests fast passed=17 failed=0 skipped=0 seconds=0.8
- commit T2 3ac3bc9e6b note copies into briefs ref
- tests full passed=13729 failed=0 skipped=12 seconds=1014.5
Ruling: no third final-review round - FR2's two findings were narrow (the git listing path of _ref_files) and the fix carries two regression tests - cost if wrong: a gap in the git path ships
- tests full passed=13731 failed=0 skipped=12 seconds=787.0
