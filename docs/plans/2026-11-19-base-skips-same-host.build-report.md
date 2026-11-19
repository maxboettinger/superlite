# superlite build report

projection: fixed forecast saved at lint 2026-11-19T20:03:51

                         Projected    Actual  Delta
wall-clock (min)              10.9      30.9  +20.0 (+184%)
agent cost (USD, +rework)      0.15      0.43  +0.28 (+181%)
task-minutes                  10.9       2.0  -8.9 (-82%)
agents                           1         6  +5 (+500%)
cost split: agents $0.30, rework $0.13, coordinator n/a, total $0.43
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (10.9 min)
model mix: sonnet 1 tasks $0.43
quality: tests 13149 passed, 0 failed; first-time pass 0/1 (0%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     10.9     2.0  -8.9 (-82%)     $0.433  first-time miss

takeaway: ran 184% slower than projected; cost 181% over; biggest miss T1
