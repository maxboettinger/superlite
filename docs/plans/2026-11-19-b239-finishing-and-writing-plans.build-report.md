# superlite build report

projection: fixed forecast saved at lint 2026-11-19T10:00:08

                         Projected    Actual  Delta
wall-clock (min)               6.7       2.9  -3.8 (-57%)
agent cost (USD, +rework)      0.23      0.53  +0.30 (+132%)
task-minutes                  25.6       3.8  -21.8 (-85%)
agents                           4         9  +5 (+125%)
cost split: agents $0.53, rework $0.00, coordinator n/a, total $0.53
concurrency: peak 3 at once (projected 4); critical path actual T3; projected T4 (6.7 min)
model mix: haiku 1 tasks $0.01, sonnet 3 tasks $0.52
quality: tests 12054 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      6.7     0.6  -6.0 (-90%)     $0.155
T1    haiku       6.1     0.3  -5.8 (-95%)     $0.007
T2    sonnet      6.6     1.4  -5.1 (-78%)     $0.184
T3    sonnet      6.2     1.4  -4.8 (-77%)     $0.184

takeaway: ran 57% faster than projected; cost 132% over; biggest miss T4
