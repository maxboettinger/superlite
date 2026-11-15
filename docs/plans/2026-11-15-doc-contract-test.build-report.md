# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:17:13

                         Projected    Actual  Delta
wall-clock (min)              13.3      12.9  -0.4 (-3%)
agent cost (USD, +rework)      0.32      0.71  +0.39 (+121%)
task-minutes                  13.3       8.5  -4.8 (-36%)
agents                           2         8  +6 (+300%)
cost split: agents $0.71, rework $0.00, coordinator n/a, total $0.71
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (13.3 min)
model mix: sonnet 2 tasks $0.71
quality: tests 10110 passed, 0 failed (last full run; newer fast run: 15 passed, 0 failed); first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      7.0     2.2  -4.8 (-69%)     $0.365
T1    sonnet      6.3     6.3  -0.0 (-0%)      $0.340

takeaway: ran 3% faster than projected; cost 121% over; biggest miss T2
