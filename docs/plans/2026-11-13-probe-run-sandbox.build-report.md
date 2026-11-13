# superlite build report

projection: fixed forecast saved at lint 2026-11-13T07:09:35 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               7.7       4.0  -3.7 (-48%)
agent cost (USD, +rework)      0.48      0.81  +0.33 (+70%)
task-minutes                  14.9       3.9  -11.0 (-74%)
agents                           4         6  +2 (+50%)
cost split: agents $0.70, rework $0.11, coordinator n/a, total $0.81
concurrency: peak 2 at once (projected 3); critical path actual T1; projected T3 > T4 (7.7 min)
model mix: sonnet 4 tasks $0.81
quality: tests 9145 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 3/4 (75%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      3.9     0.9  -3.0 (-76%)     $0.163
T4    sonnet      3.8     0.9  -2.9 (-76%)     $0.139
T3    sonnet      4.0     1.2  -2.8 (-70%)     $0.236
T1    sonnet      3.3     0.9  -2.4 (-72%)     $0.276  first-time miss

takeaway: ran 48% faster than projected; cost 70% over; biggest miss T2
