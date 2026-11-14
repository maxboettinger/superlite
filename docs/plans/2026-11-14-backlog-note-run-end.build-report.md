# superlite build report

projection: fixed forecast saved at lint 2026-11-14T12:28:27

                         Projected    Actual  Delta
wall-clock (min)               4.6       5.1  +0.5 (+11%)
agent cost (USD, +rework)      0.15      0.46  +0.32 (+217%)
task-minutes                   9.1       1.3  -7.8 (-86%)
agents                           2         4  +2 (+100%)
cost split: agents $0.36, rework $0.10, coordinator n/a, total $0.46
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (4.6 min)
model mix: sonnet 2 tasks $0.46
quality: tests 9740 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.6     0.6  -4.0 (-86%)     $0.170
T2    sonnet      4.5     0.7  -3.8 (-85%)     $0.291  first-time miss

takeaway: ran 11% slower than projected; cost 217% over; biggest miss T1
