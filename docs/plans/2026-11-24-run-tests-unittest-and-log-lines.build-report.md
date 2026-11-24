# superlite build report

projection: fixed forecast saved at lint 2026-11-24T12:14:51

                         Projected    Actual  Delta
wall-clock (min)              22.2       6.1  -16.1 (-73%)
agent cost (USD, +rework)      0.27      0.75  +0.49 (+183%)
task-minutes                  22.2       2.1  -20.1 (-90%)
agents                           2         7  +5 (+250%)
cost split: agents $0.48, rework $0.28, coordinator n/a, total $0.75
concurrency: peak 1 at once (projected 1); critical path actual T1 T2; projected T1 > T2 (22.2 min)
model mix: sonnet 2 tasks $0.75
quality: tests 13943 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     11.3     1.1  -10.3 (-90%)    $0.539  first-time miss
T2    sonnet     10.8     1.1  -9.8 (-90%)     $0.215

takeaway: ran 73% faster than projected; cost 183% over; biggest miss T1
