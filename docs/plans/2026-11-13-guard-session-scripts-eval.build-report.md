# superlite build report

projection: fixed forecast saved at lint 2026-11-13T03:55:05

                         Projected    Actual  Delta
wall-clock (min)              17.9      14.2  -3.7 (-20%)
agent cost (USD, +rework)      0.65      2.69  +2.04 (+315%)
task-minutes                  33.8      13.5  -20.3 (-60%)
agents                           6        13  +7 (+117%)
cost split: agents $2.45, rework $0.24, coordinator n/a, total $2.69
concurrency: peak 3 at once (projected 4); critical path actual T1 T4 T5; projected T1 > T4 > T5 (17.9 min)
model mix: sonnet 6 tasks $2.69
quality: tests 8858 passed, 0 failed; first-time pass 1/6 (16%); rework dispatches 2; open incidents 1

task  model      pred  actual  delta             cost
T2    sonnet      6.1     0.7  -5.4 (-88%)     $0.192
T6    sonnet      5.2     1.1  -4.0 (-78%)     $0.250  first-time miss
T1    sonnet      6.2     2.4  -3.7 (-61%)     $0.582  first-time miss
T3    sonnet      4.6     1.1  -3.5 (-75%)     $0.250  first-time miss
T5    sonnet      6.2     3.6  -2.6 (-42%)     $0.821  first-time miss
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 20% faster than projected; cost 315% over; biggest miss T2
