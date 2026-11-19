# superlite build report

projection: fixed forecast saved at lint 2026-11-19T12:10:54 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              12.3      17.4  +5.1 (+42%)
agent cost (USD, +rework)      0.10      0.28  +0.19 (+191%)
task-minutes                  36.5       2.4  -34.1 (-94%)
agents                           3         7  +4 (+133%)
cost split: agents $0.20, rework $0.08, coordinator n/a, total $0.28
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T1 (12.3 min)
model mix: haiku 2 tasks $0.11, sonnet 1 tasks $0.17
quality: tests 12228 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     12.3     0.8  -11.5 (-94%)    $0.172
T2    haiku      12.2     0.8  -11.4 (-94%)    $0.014
T3    haiku      12.1     0.8  -11.3 (-94%)    $0.097  first-time miss

takeaway: ran 42% slower than projected; cost 191% over; biggest miss T1
