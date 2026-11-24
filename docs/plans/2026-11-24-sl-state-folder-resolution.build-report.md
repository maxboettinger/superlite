# superlite build report

projection: fixed forecast saved at lint 2026-11-24T15:04:46

                         Projected    Actual  Delta
wall-clock (min)              12.4      18.9  +6.5 (+53%)
agent cost (USD, +rework)      0.25      0.66  +0.41 (+167%)
task-minutes                  36.7       2.3  -34.4 (-94%)
agents                           3         8  +5 (+167%)
cost split: agents $0.55, rework $0.11, coordinator n/a, total $0.66
concurrency: peak 2 at once (projected 3); critical path actual T3; projected T1 (12.4 min)
model mix: sonnet 3 tasks $0.66
quality: tests 14096 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 1; open incidents 1

task  model      pred  actual  delta             cost
T2    sonnet     12.2     0.4  -11.8 (-96%)    $0.110
T3    sonnet     12.1     0.4  -11.7 (-96%)    $0.221  first-time miss
T1    sonnet     12.4     1.5  -10.9 (-88%)    $0.332  first-time miss

takeaway: ran 53% slower than projected; cost 167% over; biggest miss T2
