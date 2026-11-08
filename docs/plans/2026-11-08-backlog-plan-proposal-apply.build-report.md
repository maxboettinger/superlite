# superlite build report

projection: fixed forecast saved at lint 2026-11-08T13:26:00 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.2      18.6  +17.3 (+1388%)
agent cost (USD, +rework)      0.21      0.84  +0.63 (+305%)
task-minutes                   2.4       1.1  -1.3 (-55%)
agents                           2         7  +5 (+250%)
cost split: agents $0.46, rework $0.37, coordinator $0.24 (9 turns, context median 52.8k, peak 58.2k; session $0.24), coordinator per task $0.12 (target $1.00), total $1.08
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (1.2 min)
model mix: sonnet 2 tasks $0.84, coordinator sonnet $0.24
quality: tests 4419 passed, 0 failed; first-time pass n/a; rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.1     0.5  -0.7 (-60%)     $0.221
T2    sonnet      1.2     0.6  -0.6 (-50%)     $0.614

takeaway: ran 1388% slower than projected; cost 305% over; biggest miss T1
