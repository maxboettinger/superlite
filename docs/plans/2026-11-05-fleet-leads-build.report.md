# superlite build report

projection: fixed forecast saved at lint 2026-11-05T20:43:52

                         Projected    Actual  Delta
wall-clock (min)               6.6      31.0  +24.4 (+370%)
agent cost (USD, +rework)      1.55      5.52  +3.98 (+257%)
task-minutes                  36.0      15.3  -20.7 (-58%)
agents                          14        23  +9 (+64%)
cost split: agents $3.71, rework $1.81, coordinator $8.67 (83 turns, context median 397.8k, peak 440.0k; session $50.13), coordinator per task $0.62 (target $1.00), total $14.19
concurrency: peak 7 at once (projected 10); critical path actual T5 T10; projected T6 > T11 (6.6 min)
model mix: sonnet 14 tasks $5.52, coordinator opus $8.67
quality: tests 3529 passed, 0 failed; first-time pass n/a; rework dispatches 6; open incidents 8

task  model      pred  actual  delta             cost
T6    sonnet      3.2     0.8  -2.4 (-74%)     $0.263
T5    sonnet      2.8     0.8  -2.0 (-71%)     $0.551
T4    sonnet      2.3     0.6  -1.8 (-76%)     $0.154
T9    sonnet      2.6     0.9  -1.7 (-66%)     $0.232
T12   sonnet      3.3     1.7  -1.7 (-50%)     $0.672
(+9 smaller misses; `sl report --json` lists all)

takeaway: ran 370% slower than projected; cost 257% over; biggest miss T6
