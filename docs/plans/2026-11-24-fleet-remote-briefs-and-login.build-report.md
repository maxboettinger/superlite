# superlite build report

projection: fixed forecast saved at lint 2026-11-24T13:14:46

                         Projected    Actual  Delta
wall-clock (min)              16.6      18.1  +1.5 (+9%)
agent cost (USD, +rework)      0.22      1.16  +0.94 (+430%)
task-minutes                  16.6       4.7  -11.9 (-72%)
agents                           2         6  +4 (+200%)
cost split: agents $1.01, rework $0.15, coordinator n/a, total $1.16
concurrency: peak 2 at once (projected 1); critical path actual T1; projected T1 > T2 (16.6 min)
model mix: sonnet 2 tasks $1.16
quality: tests 13974 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      8.3     2.3  -6.1 (-73%)     $0.593  first-time miss
T2    sonnet      8.3     2.5  -5.8 (-70%)     $0.568

takeaway: ran 9% slower than projected; cost 430% over; biggest miss T1
