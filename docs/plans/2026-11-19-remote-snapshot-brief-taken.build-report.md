# superlite build report

projection: fixed forecast saved at lint 2026-11-19T14:09:36 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               6.3      10.3  +4.0 (+64%)
agent cost (USD, +rework)      0.21      0.51  +0.30 (+141%)
task-minutes                  12.6       1.9  -10.7 (-85%)
agents                           2         7  +5 (+250%)
cost split: agents $0.35, rework $0.15, coordinator n/a, total $0.51
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (6.3 min)
model mix: sonnet 2 tasks $0.51
quality: tests 12601 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      6.3     0.8  -5.5 (-88%)     $0.164
T2    sonnet      6.3     1.1  -5.2 (-82%)     $0.342  first-time miss

takeaway: ran 64% slower than projected; cost 141% over; biggest miss T1
