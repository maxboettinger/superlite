# superlite build report

projection: fixed forecast saved at lint 2026-11-24T21:35:51 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.3       7.3  +4.0 (+120%)
agent cost (USD, +rework)      0.11      0.42  +0.31 (+272%)
task-minutes                   3.3       7.3  +4.0 (+120%)
agents                           1         4  +3 (+300%)
cost split: agents $0.42, rework $0.00, coordinator n/a, total $0.42
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (3.3 min)
model mix: sonnet 1 tasks $0.42
quality: tests 14456 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.3     7.3  +4.0 (+120%)    $0.422  first-time miss

takeaway: ran 120% slower than projected; cost 272% over; biggest miss T1
