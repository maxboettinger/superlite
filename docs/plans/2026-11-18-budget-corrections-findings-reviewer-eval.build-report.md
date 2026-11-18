# superlite build report

projection: fixed forecast saved at lint 2026-11-18T13:00:48 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              16.3     100.7  +84.5 (+519%)
agent cost (USD, +rework)      1.55      6.34  +4.78 (+308%)
task-minutes                  72.0      31.3  -40.7 (-56%)
agents                          14        41  +27 (+193%)
cost split: agents $3.27, rework $3.07, coordinator $22.72 (136 turns, context median 182.9k, peak 367.1k, 1 compaction, largest 369.5k tokens; session $25.83), coordinator per task $1.62 (target $1.00), total $29.06
concurrency: peak 9 at once (projected 6); critical path actual BG1; projected FD2 > RE2 > RE3 (16.3 min)
model mix: sonnet 14 tasks $6.34, coordinator fable $22.72
quality: tests 12028 passed, 0 failed; first-time pass 6/14 (42%); rework dispatches 16; open incidents 16

task  model      pred  actual  delta             cost
CR2   sonnet      5.1    12.8  +7.7 (+150%)    $0.270
FD2   sonnet      5.3     0.7  -4.6 (-87%)     $0.154
RE2   sonnet      5.7     1.2  -4.5 (-79%)     $1.580  first-time miss
CR3   sonnet      5.1     0.6  -4.5 (-88%)     $0.162
RE3   sonnet      5.3     0.8  -4.4 (-84%)     $0.288  first-time miss
(+9 smaller misses; `sl report --json` lists all)

takeaway: ran 519% slower than projected; cost 308% over; biggest miss CR2
