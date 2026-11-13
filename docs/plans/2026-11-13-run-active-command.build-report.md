# superlite build report

projection: fixed forecast saved at lint 2026-11-13T01:22:09 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               4.1       7.0  +3.0 (+72%)
agent cost (USD, +rework)      0.40      0.67  +0.27 (+69%)
task-minutes                  11.2       2.4  -8.8 (-79%)
agents                           3         7  +4 (+133%)
cost split: agents $0.60, rework $0.07, coordinator n/a, total $0.67
concurrency: peak 2 at once (projected 3); critical path actual T2 T3; projected T2 (4.1 min)
model mix: sonnet 3 tasks $0.67
quality: tests 8478 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 1; open incidents 2

task  model      pred  actual  delta             cost
T3    sonnet      4.0     0.7  -3.3 (-83%)     $0.237  first-time miss
T2    sonnet      4.1     1.2  -2.8 (-70%)     $0.304  first-time miss
T1    sonnet      3.1     0.5  -2.6 (-85%)     $0.132

takeaway: ran 72% slower than projected; cost 69% over; biggest miss T3
