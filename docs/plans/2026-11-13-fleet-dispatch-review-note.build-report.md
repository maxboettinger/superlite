# superlite build report

projection: fixed forecast saved at lint 2026-11-13T10:19:14

                         Projected    Actual  Delta
wall-clock (min)               4.7      10.2  +5.5 (+118%)
agent cost (USD, +rework)      0.33      0.98  +0.65 (+196%)
task-minutes                  10.9       4.6  -6.2 (-57%)
agents                           3         6  +3 (+100%)
cost split: agents $0.83, rework $0.14, coordinator n/a, total $0.98
concurrency: peak 3 at once (projected 3); critical path actual T1; projected T2 (4.7 min)
model mix: sonnet 3 tasks $0.98
quality: tests 9651 passed, 0 failed; first-time pass 2/3 (66%); rework dispatches 1; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet      4.7     2.4  -2.2 (-48%)     $0.410
T1    sonnet      3.2     1.1  -2.1 (-66%)     $0.354  first-time miss
T3    sonnet      3.0     1.1  -1.9 (-63%)     $0.212

takeaway: ran 118% slower than projected; cost 196% over; biggest miss T2
