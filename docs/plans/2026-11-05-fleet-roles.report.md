# superlite build report

projection: fixed forecast saved at lint 2026-11-05T20:05:40

                         Projected    Actual  Delta
wall-clock (min)               6.0      14.0  +8.1 (+134%)
agent cost (USD, +rework)      1.02      4.50  +3.49 (+343%)
task-minutes                  28.8      17.4  -11.4 (-40%)
agents                          11        31  +20 (+182%)
cost split: agents $4.38, rework $0.12, coordinator $0.57 (19 turns, context median 75.8k, peak 90.0k; session $0.57), coordinator per task $0.05 (target $1.00), total $5.07
concurrency: peak 6 at once (projected 9); critical path actual T1; projected T2 > T5 (6.0 min)
model mix: sonnet 11 tasks $4.50, coordinator sonnet $0.57
quality: tests 4 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 6

task  model      pred  actual  delta             cost
T6    sonnet      3.0     1.0  -2.1 (-68%)     $0.283
T4    sonnet      3.0     1.1  -1.9 (-65%)     $0.285
T1    sonnet      2.4     1.1  -1.3 (-56%)     $0.454
T11   sonnet      2.3     1.1  -1.2 (-53%)     $0.333
T5    sonnet      3.3     2.2  -1.1 (-34%)     $0.714
(+6 smaller misses; `sl report --json` lists all)

takeaway: ran 134% slower than projected; cost 343% over; biggest miss T6
