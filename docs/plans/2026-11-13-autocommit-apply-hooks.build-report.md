# superlite build report

projection: fixed forecast saved at lint 2026-11-13T07:51:25 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              16.2       2.5  -13.7 (-84%)
agent cost (USD, +rework)      0.23      0.47  +0.25 (+109%)
task-minutes                  16.2       4.0  -12.3 (-76%)
agents                           2         5  +3 (+150%)
cost split: agents $0.47, rework $0.00, coordinator n/a, total $0.47
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (16.2 min)
model mix: sonnet 2 tasks $0.47
quality: tests 9220 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      8.8     2.5  -6.3 (-71%)     $0.290
T2    sonnet      7.4     1.5  -6.0 (-80%)     $0.181

takeaway: ran 84% faster than projected; cost 109% over; biggest miss T1
