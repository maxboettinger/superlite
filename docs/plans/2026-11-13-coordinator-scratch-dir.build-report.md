# superlite build report

projection: fixed forecast saved at lint 2026-11-13T03:01:10

                         Projected    Actual  Delta
wall-clock (min)               5.6      26.7  +21.2 (+380%)
agent cost (USD, +rework)      0.15      1.36  +1.21 (+821%)
task-minutes                  10.0       3.9  -6.2 (-62%)
agents                           2         8  +6 (+300%)
cost split: agents $0.53, rework $0.83, coordinator n/a, total $1.36
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (5.6 min)
model mix: haiku 1 tasks $0.01, sonnet 1 tasks $1.35
quality: tests 8693 passed, 0 failed; first-time pass 0/2 (0%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    haiku       4.4     0.9  -3.6 (-81%)     $0.012  first-time miss
T1    sonnet      5.6     3.0  -2.6 (-46%)     $1.345  first-time miss

takeaway: ran 380% slower than projected; cost 821% over; biggest miss T2
