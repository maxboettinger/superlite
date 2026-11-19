# superlite build report

projection: fixed forecast saved at lint 2026-11-19T16:57:39 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.8       5.5  -4.3 (-44%)
agent cost (USD, +rework)      0.15      0.67  +0.53 (+355%)
task-minutes                   9.8       3.8  -6.0 (-61%)
agents                           1         8  +7 (+700%)
cost split: agents $0.67, rework $0.00, coordinator n/a, total $0.67
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.8 min)
model mix: sonnet 1 tasks $0.67
quality: tests 12826 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 5

task  model      pred  actual  delta             cost
T1    sonnet      9.8     3.8  -6.0 (-61%)     $0.674

takeaway: ran 44% faster than projected; cost 355% over; biggest miss T1
