# superlite build report

projection: fixed forecast saved at lint 2026-11-15T10:19:34 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               9.0       2.0  -7.1 (-78%)
agent cost (USD, +rework)      0.01      0.16  +0.15 (+2616%)
task-minutes                   9.0       2.0  -7.1 (-78%)
agents                           1         4  +3 (+300%)
cost split: agents $0.16, rework $0.00, coordinator n/a, total $0.16
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.0 min)
model mix: sonnet 1 tasks $0.16
quality: tests 10123 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.0     2.0  -7.1 (-78%)     $0.158

takeaway: ran 78% faster than projected; cost 2616% over; biggest miss T1
