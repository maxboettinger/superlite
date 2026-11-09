# superlite build report

projection: fixed forecast saved at lint 2026-11-09T08:45:04 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.5      16.7  +15.2 (+984%)
agent cost (USD, +rework)      0.30      1.52  +1.21 (+400%)
task-minutes                   4.9       3.9  -0.9 (-19%)
agents                           4        10  +6 (+150%)
cost split: agents $1.15, rework $0.36, coordinator n/a, total $1.52
concurrency: peak 3 at once (projected 4); critical path actual T2; projected T3 (1.5 min)
model mix: sonnet 4 tasks $1.52
quality: tests 4531 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      1.5     0.8  -0.8 (-49%)     $0.281
T1    sonnet      1.3     1.2  -0.2 (-13%)     $0.498
T4    sonnet      1.0     1.2  +0.2 (+16%)     $0.300
T2    sonnet      1.0     0.8  -0.2 (-15%)     $0.436

takeaway: ran 984% slower than projected; cost 400% over; biggest miss T3
