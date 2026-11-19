# superlite build report

projection: fixed forecast saved at lint 2026-11-19T14:10:45 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              16.6       4.4  -12.1 (-73%)
agent cost (USD, +rework)      0.29      0.93  +0.64 (+223%)
task-minutes                  24.2       3.5  -20.6 (-85%)
agents                           3         9  +6 (+200%)
cost split: agents $0.75, rework $0.18, coordinator n/a, total $0.93
concurrency: peak 2 at once (projected 2); critical path actual T1 T2; projected T1 > T2 (16.6 min)
model mix: haiku 1 tasks $0.10, sonnet 2 tasks $0.83
quality: tests 12615 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      8.4     1.1  -7.3 (-87%)     $0.284
T3    haiku       7.6     0.6  -7.0 (-92%)     $0.096  first-time miss
T1    sonnet      8.2     1.9  -6.3 (-77%)     $0.549  first-time miss

takeaway: ran 73% faster than projected; cost 223% over; biggest miss T2
