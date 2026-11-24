# superlite build report

projection: fixed forecast saved at lint 2026-11-24T13:33:35

                         Projected    Actual  Delta
wall-clock (min)               9.4       1.2  -8.2 (-88%)
agent cost (USD, +rework)      0.16      0.24  +0.08 (+49%)
task-minutes                  18.5       1.8  -16.7 (-90%)
agents                           2         6  +4 (+200%)
cost split: agents $0.24, rework $0.00, coordinator n/a, total $0.24
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (9.4 min)
model mix: haiku 1 tasks $0.01, sonnet 1 tasks $0.23
quality: tests 13994 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    haiku       9.1     0.6  -8.5 (-93%)     $0.012
T1    sonnet      9.4     1.2  -8.2 (-88%)     $0.226

takeaway: ran 88% faster than projected; cost 49% over; biggest miss T2
