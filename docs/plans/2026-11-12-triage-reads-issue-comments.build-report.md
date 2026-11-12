# superlite build report

projection: fixed forecast saved at lint 2026-11-12T03:54:53 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               1.9      49.9  +48.0 (+2467%)
agent cost (USD, +rework)      0.15      0.63  +0.47 (+308%)
task-minutes                   5.1       1.9  -3.2 (-63%)
agents                           3         8  +5 (+167%)
cost split: agents $0.48, rework $0.15, coordinator n/a, total $0.63
concurrency: peak 3 at once (projected 3); critical path actual T2; projected T1 (1.9 min)
model mix: sonnet 3 tasks $0.63
quality: tests 6778 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      1.9     0.7  -1.2 (-64%)     $0.168
T3    sonnet      1.5     0.4  -1.1 (-72%)     $0.166  first-time miss
T2    sonnet      1.6     0.8  -0.8 (-52%)     $0.295  first-time miss

takeaway: ran 2467% slower than projected; cost 308% over; biggest miss T1
