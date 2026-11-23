# superlite build report

projection: fixed forecast saved at lint 2026-11-23T19:31:46

                         Projected    Actual  Delta
wall-clock (min)               9.7      17.7  +8.0 (+83%)
agent cost (USD, +rework)      0.01      0.30  +0.29 (+3915%)
task-minutes                   9.7       1.2  -8.4 (-87%)
agents                           1         5  +4 (+400%)
cost split: agents $0.18, rework $0.11, coordinator n/a, total $0.30
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (9.7 min)
model mix: sonnet 1 tasks $0.30
quality: tests 13632 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.7     1.2  -8.4 (-87%)     $0.297  first-time miss

takeaway: ran 83% slower than projected; cost 3915% over; biggest miss T1
