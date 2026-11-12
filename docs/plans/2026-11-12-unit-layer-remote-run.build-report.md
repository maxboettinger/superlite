# superlite build report

projection: fixed forecast saved at lint 2026-11-12T13:43:16

                         Projected    Actual  Delta
wall-clock (min)               7.2       2.2  -5.1 (-70%)
agent cost (USD, +rework)      0.20      0.44  +0.25 (+125%)
task-minutes                  25.2       3.6  -21.6 (-86%)
agents                           4         5  +1 (+25%)
cost split: agents $0.44, rework $0.00, coordinator n/a, total $0.44
concurrency: peak 3 at once (projected 4); critical path actual T1; projected T1 (7.2 min)
model mix: sonnet 4 tasks $0.44
quality: tests 7254 passed, 0 failed; first-time pass 2/4 (50%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      6.0     0.4  -5.6 (-93%)     $0.080
T3    sonnet      6.0     0.7  -5.4 (-89%)     $0.066  first-time miss
T1    sonnet      7.2     1.9  -5.3 (-74%)     $0.232
T2    sonnet      6.0     0.7  -5.3 (-89%)     $0.066  first-time miss

takeaway: ran 70% faster than projected; cost 125% over; biggest miss T4
