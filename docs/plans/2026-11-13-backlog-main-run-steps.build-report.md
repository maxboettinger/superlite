# superlite build report

projection: fixed forecast saved at lint 2026-11-13T03:39:39

                         Projected    Actual  Delta
wall-clock (min)               7.4      11.8  +4.4 (+59%)
agent cost (USD, +rework)      0.56      1.43  +0.88 (+158%)
task-minutes                  16.5       3.9  -12.6 (-77%)
agents                           5        12  +7 (+140%)
cost split: agents $0.99, rework $0.44, coordinator n/a, total $1.43
concurrency: peak 4 at once (projected 3); critical path actual T1 T3; projected T1 > T2 (7.4 min)
model mix: sonnet 5 tasks $1.43
quality: tests 8748 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 3/5 (60%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      4.1     1.3  -2.8 (-69%)     $0.312
T1    sonnet      3.3     0.6  -2.7 (-81%)     $0.170
T3    sonnet      3.1     0.7  -2.4 (-78%)     $0.405  first-time miss
T5    sonnet      3.0     0.6  -2.4 (-80%)     $0.383  first-time miss
T4    sonnet      3.0     0.7  -2.4 (-78%)     $0.165

takeaway: ran 59% slower than projected; cost 158% over; biggest miss T2
