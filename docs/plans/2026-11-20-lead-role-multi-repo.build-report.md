# superlite build report

projection: fixed forecast saved at lint 2026-11-20T12:38:50

                         Projected    Actual  Delta
wall-clock (min)              13.3       3.9  -9.4 (-71%)
agent cost (USD, +rework)      0.50      1.11  +0.61 (+121%)
task-minutes                  33.2       6.7  -26.5 (-80%)
agents                           5        11  +6 (+120%)
cost split: agents $1.11, rework $0.00, coordinator n/a, total $1.11
concurrency: peak 4 at once (projected 4); critical path actual T1 T5; projected T1 > T5 (13.3 min)
model mix: sonnet 5 tasks $1.11
quality: tests 13385 passed, 0 failed; first-time pass 5/5 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T5    sonnet      6.1     0.5  -5.6 (-91%)     $0.076
T2    sonnet      6.9     1.3  -5.6 (-81%)     $0.301
T4    sonnet      6.7     1.2  -5.6 (-82%)     $0.258
T3    sonnet      6.3     0.9  -5.4 (-86%)     $0.166
T1    sonnet      7.2     2.8  -4.4 (-61%)     $0.311

takeaway: ran 71% faster than projected; cost 121% over; biggest miss T5
