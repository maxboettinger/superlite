# superlite build report

projection: fixed forecast saved at lint 2026-11-13T07:43:45

                         Projected    Actual  Delta
wall-clock (min)               3.0       6.7  +3.7 (+123%)
agent cost (USD, +rework)      0.08      0.22  +0.14 (+179%)
task-minutes                   5.9       1.1  -4.7 (-81%)
agents                           2         4  +2 (+100%)
cost split: agents $0.14, rework $0.08, coordinator n/a, total $0.22
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (3.0 min)
model mix: haiku 1 tasks $0.01, sonnet 1 tasks $0.21
quality: tests 9218 passed, 0 failed; first-time pass 1/2 (50%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.0     0.5  -2.5 (-84%)     $0.208  first-time miss
T2    haiku       2.9     0.7  -2.2 (-77%)     $0.012

takeaway: ran 123% slower than projected; cost 179% over; biggest miss T1
