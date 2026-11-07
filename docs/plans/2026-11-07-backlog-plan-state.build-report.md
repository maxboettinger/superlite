# superlite build report

projection: fixed forecast saved at lint 2026-11-07T23:50:24 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.6       1.7  -0.8 (-32%)
agent cost (USD, +rework)      0.24      0.55  +0.31 (+129%)
task-minutes                   2.6       1.5  -1.1 (-42%)
agents                           2         4  +2 (+100%)
cost split: agents $0.55, rework $0.00, coordinator n/a, total $0.55
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (2.6 min)
model mix: sonnet 2 tasks $0.55
quality: tests 4226 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 2

task  model      pred  actual  delta             cost
T2    sonnet      1.3     0.7  -0.6 (-46%)     $0.271
T1    sonnet      1.3     0.8  -0.5 (-38%)     $0.277

takeaway: ran 32% faster than projected; cost 129% over; biggest miss T2
