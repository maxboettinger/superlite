# superlite build report

projection: fixed forecast saved at lint 2026-11-12T03:16:30

                         Projected    Actual  Delta
wall-clock (min)               2.7      70.3  +67.6 (+2538%)
agent cost (USD, +rework)      0.37      1.18  +0.81 (+217%)
task-minutes                   7.0       3.3  -3.7 (-53%)
agents                           3        10  +7 (+233%)
cost split: agents $0.73, rework $0.45, coordinator $5.84 (72 turns, context median 305.9k, peak 337.7k; session $10.10), coordinator per task $1.95 (target $1.00), total $7.01
concurrency: peak 3 at once (projected 3); critical path actual T3; projected T1 (2.7 min)
model mix: sonnet 3 tasks $1.18, coordinator opus $5.84
quality: tests 6715 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 3; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      2.5     1.0  -1.6 (-61%)     $0.323  first-time miss
T1    sonnet      2.7     1.3  -1.4 (-51%)     $0.294
T3    sonnet      1.8     1.0  -0.8 (-46%)     $0.562  first-time miss

takeaway: ran 2538% slower than projected; cost 217% over; biggest miss T2
