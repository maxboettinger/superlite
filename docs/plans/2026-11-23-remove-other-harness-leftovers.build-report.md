# superlite build report

projection: fixed forecast saved at lint 2026-11-23T19:27:21

                         Projected    Actual  Delta
wall-clock (min)               3.8       4.5  +0.7 (+19%)
agent cost (USD, +rework)      0.12      0.42  +0.30 (+247%)
task-minutes                   7.4       5.2  -2.2 (-30%)
agents                           2         4  +2 (+100%)
cost split: agents $0.42, rework $0.00, coordinator n/a, total $0.42
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (3.8 min)
model mix: sonnet 2 tasks $0.42
quality: tests 13636 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.6     0.7  -2.9 (-81%)     $0.167
T1    sonnet      3.8     4.5  +0.7 (+19%)     $0.249

takeaway: ran 19% slower than projected; cost 247% over; biggest miss T2
