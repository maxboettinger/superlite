# superlite build report

projection: fixed forecast saved at lint 2026-11-12T18:00:41

                         Projected    Actual  Delta
wall-clock (min)               4.3       8.7  +4.4 (+102%)
agent cost (USD, +rework)      0.33      0.88  +0.56 (+171%)
task-minutes                  11.2       3.9  -7.3 (-65%)
agents                           3         7  +4 (+133%)
cost split: agents $0.69, rework $0.20, coordinator n/a, total $0.88
concurrency: peak 3 at once (projected 3); critical path actual T2; projected T1 (4.3 min)
model mix: sonnet 3 tasks $0.88
quality: tests 7861 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.8     0.7  -3.1 (-80%)     $0.235  first-time miss
T3    sonnet      3.1     0.7  -2.4 (-76%)     $0.138
T1    sonnet      4.3     2.4  -1.9 (-44%)     $0.510  first-time miss

takeaway: ran 102% slower than projected; cost 171% over; biggest miss T2
