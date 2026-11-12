# superlite build report

projection: fixed forecast saved at lint 2026-11-11T23:59:52

                         Projected    Actual  Delta
wall-clock (min)               4.7      76.1  +71.4 (+1503%)
agent cost (USD, +rework)      0.47      2.08  +1.61 (+340%)
task-minutes                   7.1      19.1  +12.0 (+170%)
agents                           3        11  +8 (+267%)
cost split: agents $1.43, rework $0.65, coordinator n/a, total $2.08
concurrency: peak 3 at once (projected 2); critical path actual T1; projected T1 > T2 (4.7 min)
model mix: sonnet 3 tasks $2.08
quality: tests 6593 passed, 0 failed; first-time pass 0/3 (0%); rework dispatches 4; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      2.4    11.6  +9.2 (+389%)    $0.595  first-time miss
T1    sonnet      2.4     5.9  +3.5 (+149%)    $1.199  first-time miss
T3    sonnet      2.3     1.6  -0.7 (-32%)     $0.289  first-time miss

takeaway: ran 1503% slower than projected; cost 340% over; biggest miss T2
