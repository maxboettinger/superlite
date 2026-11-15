# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:27:01 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              11.8       0.8  -11.1 (-94%)
agent cost (USD, +rework)      0.17      0.25  +0.09 (+52%)
task-minutes                  11.8       0.8  -11.1 (-94%)
agents                           1         3  +2 (+200%)
cost split: agents $0.25, rework $0.00, coordinator n/a, total $0.25
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (11.8 min)
model mix: sonnet 1 tasks $0.25
quality: tests 10164 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     11.8     0.8  -11.1 (-94%)    $0.251

takeaway: ran 94% faster than projected; cost 52% over; biggest miss T1
