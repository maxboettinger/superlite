# superlite build report

projection: fixed forecast saved at lint 2026-11-24T15:03:11 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              18.9      14.8  -4.1 (-22%)
agent cost (USD, +rework)      0.32      0.80  +0.48 (+152%)
task-minutes                  46.9       3.7  -43.2 (-92%)
agents                           5        10  +5 (+100%)
cost split: agents $0.69, rework $0.10, coordinator n/a, total $0.80
concurrency: peak 3 at once (projected 4); critical path actual T4 T5; projected T4 > T5 (18.9 min)
model mix: haiku 1 tasks $0.01, sonnet 4 tasks $0.78
quality: tests 14100 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 4/5 (80%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      9.7     0.6  -9.2 (-94%)     $0.134
T4    sonnet      9.7     0.8  -8.9 (-91%)     $0.205
T2    sonnet      9.2     0.6  -8.6 (-94%)     $0.134
T1    haiku       9.1     0.7  -8.4 (-92%)     $0.013
T5    sonnet      9.2     1.0  -8.1 (-89%)     $0.309  first-time miss

takeaway: ran 22% faster than projected; cost 152% over; biggest miss T3
