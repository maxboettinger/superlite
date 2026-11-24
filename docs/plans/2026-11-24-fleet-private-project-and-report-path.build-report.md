# superlite build report

projection: fixed forecast saved at lint 2026-11-24T13:09:33

                         Projected    Actual  Delta
wall-clock (min)              10.5       1.4  -9.1 (-87%)
agent cost (USD, +rework)      0.26      0.37  +0.12 (+45%)
task-minutes                  15.2       1.5  -13.7 (-90%)
agents                           3         4  +1 (+33%)
cost split: agents $0.37, rework $0.00, coordinator n/a, total $0.37
concurrency: peak 2 at once (projected 2); critical path actual T1 T3; projected T1 > T3 (10.5 min)
model mix: sonnet 3 tasks $0.37
quality: tests 13974 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      5.3     0.5  -4.8 (-91%)     $0.106
T1    sonnet      5.3     0.6  -4.7 (-89%)     $0.153
T2    sonnet      4.6     0.4  -4.2 (-90%)     $0.115

takeaway: ran 87% faster than projected; cost 45% over; biggest miss T3
