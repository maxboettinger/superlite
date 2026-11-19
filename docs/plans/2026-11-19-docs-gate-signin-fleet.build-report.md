# superlite build report

projection: fixed forecast saved at lint 2026-11-19T14:16:33

                         Projected    Actual  Delta
wall-clock (min)              13.7       1.1  -12.6 (-92%)
agent cost (USD, +rework)      0.01      0.12  +0.10 (+734%)
task-minutes                  40.9       1.9  -39.0 (-95%)
agents                           3         9  +6 (+200%)
cost split: agents $0.12, rework $0.00, coordinator n/a, total $0.12
concurrency: peak 3 at once (projected 3); critical path actual D3; projected D1 (13.7 min)
model mix: haiku 2 tasks $0.03, sonnet 1 tasks $0.09
quality: tests 12597 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
D1    sonnet     13.7     0.3  -13.4 (-98%)    $0.092
D2    haiku      13.6     0.8  -12.8 (-94%)    $0.013
D3    haiku      13.6     0.8  -12.8 (-94%)    $0.014

takeaway: ran 92% faster than projected; cost 734% over; biggest miss D1
