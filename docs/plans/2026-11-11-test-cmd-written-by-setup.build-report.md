# superlite build report

projection: fixed forecast saved at lint 2026-11-11T22:19:55 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.4      38.0  +35.7 (+1508%)
agent cost (USD, +rework)      0.39      0.82  +0.42 (+108%)
task-minutes                   7.9       2.9  -4.9 (-63%)
agents                           4         7  +3 (+75%)
cost split: agents $0.65, rework $0.16, coordinator n/a, total $0.82
concurrency: peak 3 at once (projected 4); critical path actual T3; projected T1 (2.4 min)
model mix: sonnet 4 tasks $0.82
quality: tests 6567 passed, 0 failed; first-time pass 1/4 (25%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      2.3     0.7  -1.7 (-72%)     $0.232  first-time miss
T2    sonnet      1.6     0.5  -1.1 (-69%)     $0.118  first-time miss
T4    sonnet      1.6     0.5  -1.1 (-69%)     $0.197  first-time miss
T1    sonnet      2.4     1.3  -1.1 (-45%)     $0.271

takeaway: ran 1508% slower than projected; cost 108% over; biggest miss T3
