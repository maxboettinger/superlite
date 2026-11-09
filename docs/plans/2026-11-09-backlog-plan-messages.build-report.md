# superlite build report

projection: fixed forecast saved at lint 2026-11-09T16:53:45

                         Projected    Actual  Delta
wall-clock (min)               1.4       1.1  -0.3 (-24%)
agent cost (USD, +rework)      0.21      0.63  +0.42 (+203%)
task-minutes                   3.5       1.8  -1.7 (-49%)
agents                           3         4  +1 (+33%)
cost split: agents $0.63, rework $0.00, coordinator n/a, total $0.63
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T2 (1.4 min)
model mix: sonnet 3 tasks $0.63
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.4     0.7  -0.7 (-51%)     $0.294
T1    sonnet      1.1     0.5  -0.5 (-49%)     $0.168
T3    sonnet      1.0     0.5  -0.5 (-45%)     $0.168

takeaway: ran 24% faster than projected; cost 203% over; biggest miss T2
