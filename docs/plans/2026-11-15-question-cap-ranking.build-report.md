# superlite build report

projection: fixed forecast saved at lint 2026-11-15T11:09:46 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.0       7.6  +4.6 (+151%)
agent cost (USD, +rework)      0.15      0.38  +0.23 (+150%)
task-minutes                   6.1       1.1  -5.0 (-82%)
agents                           2         5  +3 (+150%)
cost split: agents $0.28, rework $0.10, coordinator n/a, total $0.38
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (3.0 min)
model mix: sonnet 2 tasks $0.38
quality: tests 10967 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.0     0.5  -2.5 (-82%)     $0.126
T2    sonnet      3.0     0.6  -2.5 (-81%)     $0.256  first-time miss

takeaway: ran 151% slower than projected; cost 150% over; biggest miss T1
