# superlite build report

projection: fixed forecast saved at lint 2026-11-09T18:45:41

                         Projected    Actual  Delta
wall-clock (min)               1.2       1.5  +0.3 (+25%)
agent cost (USD, +rework)      0.40      1.08  +0.68 (+172%)
task-minutes                   3.5       3.8  +0.2 (+7%)
agents                           3         6  +3 (+100%)
cost split: agents $1.08, rework $0.00, coordinator n/a, total $1.08
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T1 (1.2 min)
model mix: sonnet 3 tasks $1.08
quality: tests 4991 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.2     1.5  +0.3 (+25%)     $0.397
T2    sonnet      1.2     1.1  -0.1 (-8%)      $0.345
T3    sonnet      1.1     1.2  +0.0 (+3%)      $0.339

takeaway: ran 25% slower than projected; cost 172% over; biggest miss T1
