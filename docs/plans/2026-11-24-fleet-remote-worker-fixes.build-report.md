# superlite build report

projection: fixed forecast saved at lint 2026-11-24T15:26:56

                         Projected    Actual  Delta
wall-clock (min)              12.2       0.9  -11.4 (-93%)
agent cost (USD, +rework)      0.19      0.43  +0.24 (+125%)
task-minutes                  36.5       1.7  -34.8 (-95%)
agents                           3         9  +6 (+200%)
cost split: agents $0.43, rework $0.00, coordinator n/a, total $0.43
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T1 (12.2 min)
model mix: haiku 1 tasks $0.01, sonnet 2 tasks $0.42
quality: tests 14101 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    haiku      12.1     0.3  -11.8 (-98%)    $0.007
T2    sonnet     12.2     0.5  -11.7 (-96%)    $0.159
T1    sonnet     12.2     0.9  -11.4 (-93%)    $0.261

takeaway: ran 93% faster than projected; cost 125% over; biggest miss T3
