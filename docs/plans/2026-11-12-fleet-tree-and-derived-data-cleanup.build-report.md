# superlite build report

projection: fixed forecast saved at lint 2026-11-12T00:25:41

                         Projected    Actual  Delta
wall-clock (min)               4.7       7.2  +2.4 (+51%)
agent cost (USD, +rework)      0.58      1.41  +0.83 (+144%)
task-minutes                   7.9      12.5  +4.6 (+58%)
agents                           4         7  +3 (+75%)
cost split: agents $1.41, rework $0.00, coordinator n/a, total $1.41
concurrency: peak 3 at once (projected 2); critical path actual T1 T2; projected T1 > T2 (4.7 min)
model mix: sonnet 4 tasks $1.41
quality: tests 6624 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      1.6     3.8  +2.2 (+136%)    $0.313
T2    sonnet      2.4     4.3  +2.0 (+83%)     $0.512
T3    sonnet      1.6     2.0  +0.4 (+22%)     $0.288
T1    sonnet      2.4     2.5  +0.1 (+4%)      $0.296

takeaway: ran 51% slower than projected; cost 144% over; biggest miss T4
