# superlite build report

projection: fixed forecast saved at lint 2026-11-12T18:30:57 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.8      13.5  +2.7 (+25%)
agent cost (USD, +rework)      0.59      1.20  +0.61 (+105%)
task-minutes                  17.5       6.4  -11.1 (-63%)
agents                           5         9  +4 (+80%)
cost split: agents $1.10, rework $0.10, coordinator n/a, total $1.20
concurrency: peak 2 at once (projected 3); critical path actual T1; projected T1 > T3 > T5 (10.8 min)
model mix: sonnet 5 tasks $1.20
quality: tests 7885 passed, 0 failed; first-time pass 4/5 (80%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.6     0.8  -2.8 (-78%)     $0.146
T5    sonnet      3.0     0.4  -2.6 (-86%)     $0.107
T4    sonnet      3.1     0.8  -2.3 (-74%)     $0.146
T1    sonnet      4.3     2.3  -2.0 (-46%)     $0.386  first-time miss
T3    sonnet      3.5     2.1  -1.4 (-41%)     $0.416

takeaway: ran 25% slower than projected; cost 105% over; biggest miss T2
