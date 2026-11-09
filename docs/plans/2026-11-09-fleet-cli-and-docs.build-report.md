# superlite build report

projection: fixed forecast saved at lint 2026-11-09T16:52:12

                         Projected    Actual  Delta
wall-clock (min)               1.8       1.0  -0.7 (-42%)
agent cost (USD, +rework)      0.13      0.82  +0.69 (+521%)
task-minutes                   5.1       2.5  -2.6 (-52%)
agents                           4         6  +2 (+50%)
cost split: agents $0.82, rework $0.00, coordinator n/a, total $0.82
concurrency: peak 3 at once (projected 4); critical path actual T2; projected T1 (1.8 min)
model mix: sonnet 4 tasks $0.82
quality: tests 4861 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.8     0.8  -1.0 (-54%)     $0.283
T2    sonnet      1.3     0.7  -0.6 (-46%)     $0.200
T3    sonnet      1.0     0.5  -0.5 (-54%)     $0.167
T4    sonnet      1.0     0.5  -0.5 (-53%)     $0.167

takeaway: ran 42% faster than projected; cost 521% over; biggest miss T1
