# superlite build report

projection: fixed forecast saved at lint 2026-11-10T10:13:30

                         Projected    Actual  Delta
wall-clock (min)               1.7      13.9  +12.2 (+704%)
agent cost (USD, +rework)      0.32      1.30  +0.98 (+311%)
task-minutes                   3.1       5.1  +2.0 (+66%)
agents                           2         5  +3 (+150%)
cost split: agents $0.81, rework $0.49, coordinator n/a, total $1.30
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (1.7 min)
model mix: sonnet 2 tasks $1.30
quality: tests 5363 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.7     3.9  +2.2 (+125%)    $0.651
T2    sonnet      1.3     1.2  -0.1 (-10%)     $0.649

takeaway: ran 704% slower than projected; cost 311% over; biggest miss T1
