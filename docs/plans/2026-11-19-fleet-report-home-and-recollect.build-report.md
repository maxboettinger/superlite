# superlite build report

projection: fixed forecast saved at lint 2026-11-19T18:33:03 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              19.7       3.6  -16.0 (-82%)
agent cost (USD, +rework)      0.38      0.85  +0.47 (+125%)
task-minutes                  28.9       4.2  -24.7 (-86%)
agents                           3         8  +5 (+167%)
cost split: agents $0.85, rework $0.00, coordinator n/a, total $0.85
concurrency: peak 2 at once (projected 2); critical path actual T2 T3; projected T1 > T3 (19.7 min)
model mix: sonnet 3 tasks $0.85
quality: tests 12954 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      9.8     1.1  -8.7 (-89%)     $0.223
T2    sonnet      9.2     1.2  -8.0 (-87%)     $0.235
T3    sonnet      9.9     1.9  -8.0 (-81%)     $0.393  first-time miss

takeaway: ran 82% faster than projected; cost 125% over; biggest miss T1
