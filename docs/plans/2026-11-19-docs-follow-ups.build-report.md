# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:36:31

                         Projected    Actual  Delta
wall-clock (min)               6.5      12.9  +6.4 (+99%)
agent cost (USD, +rework)      0.01      0.26  +0.24 (+1742%)
task-minutes                  24.9       6.6  -18.3 (-73%)
agents                           4        12  +8 (+200%)
cost split: agents $0.18, rework $0.08, coordinator n/a, total $0.26
concurrency: peak 3 at once (projected 4); critical path actual P1; projected P1 (6.5 min)
model mix: haiku 3 tasks $0.04, sonnet 1 tasks $0.21
quality: tests 12200 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
P1    sonnet      6.5     0.6  -5.9 (-92%)     $0.213  first-time miss
P2    haiku       6.1     1.1  -5.1 (-83%)     $0.015
S1    haiku       6.1     1.1  -5.1 (-83%)     $0.015
D1    haiku       6.2     4.0  -2.2 (-36%)     $0.014  first-time miss

takeaway: ran 99% slower than projected; cost 1742% over; biggest miss P1
