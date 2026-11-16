# superlite build report

projection: fixed forecast saved at lint 2026-11-16T19:14:46

                         Projected    Actual  Delta
wall-clock (min)               4.7       1.6  -3.1 (-67%)
agent cost (USD, +rework)      0.15      0.24  +0.08 (+55%)
task-minutes                   4.7       1.6  -3.1 (-67%)
agents                           1         5  +4 (+400%)
cost split: agents $0.24, rework $0.00, coordinator n/a, total $0.24
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (4.7 min)
model mix: sonnet 1 tasks $0.24
quality: tests 11835 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      4.7     1.6  -3.1 (-67%)     $0.236

takeaway: ran 67% faster than projected; cost 55% over; biggest miss T1
