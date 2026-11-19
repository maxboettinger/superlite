# superlite build report

projection: fixed forecast saved at lint 2026-11-19T09:58:07

                         Projected    Actual  Delta
wall-clock (min)              10.8       4.5  -6.3 (-58%)
agent cost (USD, +rework)      0.22      0.80  +0.58 (+267%)
task-minutes                  10.8       3.7  -7.1 (-66%)
agents                           2         4  +2 (+100%)
cost split: agents $0.80, rework $0.00, coordinator n/a, total $0.80
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (10.8 min)
model mix: sonnet 2 tasks $0.80
quality: tests 12049 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      5.7     1.8  -3.9 (-68%)     $0.285
T1    sonnet      5.2     1.9  -3.2 (-63%)     $0.516

takeaway: ran 58% faster than projected; cost 267% over; biggest miss T2
