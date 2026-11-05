# superlite build report

projection: fixed forecast saved at lint 2026-11-05T10:25:23 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.5      57.5  +49.0 (+577%)
agent cost (USD, +rework)      1.42      3.14  +1.72 (+121%)
task-minutes                  25.7      16.7  -9.0 (-35%)
agents                           9        26  +17 (+189%)
cost split: agents $1.77, rework $1.38, coordinator $17.60 (98 turns, context median 390.9k, peak 461.2k; session $28.51), total $20.75
concurrency: peak 7 at once (projected 7); critical path actual T2; projected T4 > T8 > T9 (8.5 min)
model mix: sonnet 9 tasks $3.14, coordinator fable $17.60
quality: tests 4 passed, 0 failed; first-time pass 2/9 (22%); rework dispatches 14; open incidents 1

task  model      pred  actual  delta             cost
T9    sonnet      2.1     0.5  -1.6 (-76%)     $0.040  first-time miss
T3    sonnet      3.2     1.7  -1.5 (-46%)     $0.362  first-time miss
T8    sonnet      3.0     1.6  -1.4 (-46%)     $0.318  first-time miss
T2    sonnet      2.5     1.3  -1.2 (-48%)     $0.473  first-time miss
T1    sonnet      2.5     1.3  -1.2 (-47%)     $0.256  first-time miss
(+4 smaller misses; `sl report --json` lists all)

takeaway: ran 577% slower than projected; cost 121% over; biggest miss T9
