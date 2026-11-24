# superlite build report

projection: fixed forecast saved at lint 2026-11-24T11:36:58

                         Projected    Actual  Delta
wall-clock (min)               6.8       3.2  -3.7 (-54%)
agent cost (USD, +rework)      0.21      0.55  +0.34 (+158%)
task-minutes                  13.6       1.8  -11.9 (-87%)
agents                           2         8  +6 (+300%)
cost split: agents $0.46, rework $0.09, coordinator n/a, total $0.55
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (6.8 min)
model mix: sonnet 2 tasks $0.55
quality: tests 13917 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.8     0.6  -6.2 (-92%)     $0.163
T2    sonnet      6.8     1.2  -5.6 (-82%)     $0.390  first-time miss

takeaway: ran 54% faster than projected; cost 158% over; biggest miss T1
