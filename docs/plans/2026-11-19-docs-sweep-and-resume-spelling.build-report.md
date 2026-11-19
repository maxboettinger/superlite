# superlite build report

projection: fixed forecast saved at lint 2026-11-19T17:58:06

                         Projected    Actual  Delta
wall-clock (min)              11.0      17.2  +6.2 (+57%)
agent cost (USD, +rework)      0.33      0.92  +0.59 (+180%)
task-minutes                  31.6      21.2  -10.4 (-33%)
agents                           3        11  +8 (+267%)
cost split: agents $0.92, rework $0.00, coordinator n/a, total $0.92
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T2 (11.0 min)
model mix: sonnet 3 tasks $0.92
quality: tests 12926 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 0; open incidents 1

task  model      pred  actual  delta             cost
T2    sonnet     11.0     1.9  -9.1 (-83%)     $0.306  first-time miss
T3    sonnet     11.0     2.5  -8.5 (-77%)     $0.321
T1    sonnet      9.6    16.9  +7.3 (+75%)     $0.295

takeaway: ran 57% slower than projected; cost 180% over; biggest miss T2
