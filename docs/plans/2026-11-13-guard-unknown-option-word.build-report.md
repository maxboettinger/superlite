# superlite build report

projection: fixed forecast saved at lint 2026-11-13T07:54:06

                         Projected    Actual  Delta
wall-clock (min)              11.5       5.4  -6.0 (-53%)
agent cost (USD, +rework)      0.14      0.32  +0.18 (+132%)
task-minutes                  11.5       5.4  -6.0 (-53%)
agents                           1         3  +2 (+200%)
cost split: agents $0.32, rework $0.00, coordinator n/a, total $0.32
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (11.5 min)
model mix: sonnet 1 tasks $0.32
quality: tests 9223 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     11.5     5.4  -6.0 (-53%)     $0.323

takeaway: ran 53% faster than projected; cost 132% over; biggest miss T1
