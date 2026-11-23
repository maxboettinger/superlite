# superlite build report

projection: fixed forecast saved at lint 2026-11-23T19:54:52

                         Projected    Actual  Delta
wall-clock (min)              15.4       2.1  -13.4 (-87%)
agent cost (USD, +rework)      0.18      0.33  +0.15 (+87%)
task-minutes                  15.4       1.8  -13.6 (-88%)
agents                           2         5  +3 (+150%)
cost split: agents $0.33, rework $0.00, coordinator n/a, total $0.33
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (15.4 min)
model mix: sonnet 2 tasks $0.33
quality: tests 13643 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.7     0.8  -6.9 (-89%)     $0.197
T2    sonnet      7.7     1.0  -6.7 (-87%)     $0.132

takeaway: ran 87% faster than projected; cost 87% over; biggest miss T1
