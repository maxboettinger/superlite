# superlite build report

projection: fixed forecast saved at lint 2026-11-19T11:36:45 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               8.3      36.4  +28.1 (+339%)
agent cost (USD, +rework)      0.25      1.22  +0.97 (+384%)
task-minutes                  16.1       4.9  -11.3 (-70%)
agents                           2        10  +8 (+400%)
cost split: agents $0.88, rework $0.34, coordinator n/a, total $1.22
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (8.3 min)
model mix: sonnet 3 tasks $1.22
quality: tests 12316 passed, 0 failed; first-time pass 1/3 (33%); rework dispatches 2; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      7.9     1.1  -6.8 (-86%)     $0.233  first-time miss
T2    sonnet      8.3     2.0  -6.3 (-76%)     $0.685  first-time miss
T3    sonnet      n/a     1.8  n/a             $0.304

takeaway: ran 339% slower than projected; cost 384% over; biggest miss T1
