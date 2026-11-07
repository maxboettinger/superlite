# superlite build report

projection: fixed forecast saved at lint 2026-11-08T00:35:51

                         Projected    Actual  Delta
wall-clock (min)               1.6       0.8  -0.9 (-53%)
agent cost (USD, +rework)      0.29      0.49  +0.20 (+68%)
task-minutes                   2.9       1.3  -1.6 (-56%)
agents                           2         4  +2 (+100%)
cost split: agents $0.49, rework $0.00, coordinator n/a, total $0.49
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T2 (1.6 min)
model mix: sonnet 2 tasks $0.49
quality: tests 4289 passed, 0 failed; first-time pass n/a; rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     0.7  -1.0 (-60%)     $0.271
T1    sonnet      1.3     0.6  -0.6 (-51%)     $0.224

takeaway: ran 53% faster than projected; cost 68% over; biggest miss T2
