# superlite build report

projection: fixed forecast saved at lint 2026-11-07T11:12:49

                         Projected    Actual  Delta
wall-clock (min)               1.6       1.7  +0.1 (+8%)
agent cost (USD, +rework)      0.25      0.66  +0.40 (+159%)
task-minutes                   3.0       2.9  -0.1 (-3%)
agents                           2         5  +3 (+150%)
cost split: agents $0.66, rework $0.00, coordinator n/a, total $0.66
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T2 (1.6 min)
model mix: sonnet 2 tasks $0.66
quality: tests 3931 passed, 0 failed; first-time pass 1/1 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      1.6     1.4  -0.2 (-12%)     $0.354
T1    sonnet      1.4     1.5  +0.1 (+6%)      $0.303

takeaway: ran 8% slower than projected; cost 159% over; biggest miss T2
