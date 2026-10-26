# superlite build report

projection: fixed forecast saved at lint 2026-10-26T09:15:18

                         Projected    Actual  Delta
wall-clock (min)               6.2       9.4  +3.2 (+51%)
agent cost (USD, +rework)      0.52      2.08  +1.56 (+299%)
task-minutes                  30.4      20.4  -10.0 (-33%)
agents                           6        34  +28 (+467%)
cost split: agents $2.02, rework $0.06, coordinator $4.05, total $6.12
concurrency: peak 6 at once (projected 6); critical path actual T6; projected T3 (6.2 min)
model mix: sonnet 6 tasks $2.08, coordinator sonnet $4.05
quality: tests 644 passed, 0 failed; first-time pass n/a; rework dispatches 1; open incidents 6

task  model      pred  actual  delta             cost
T3    sonnet      6.2     3.1  -3.1 (-50%)     $0.354
T2    sonnet      4.2     2.0  -2.1 (-52%)     $0.206
T4    sonnet      5.8     3.9  -1.9 (-33%)     $0.459
T6    sonnet      5.9     4.3  -1.5 (-26%)     $0.372
T1    sonnet      4.2     3.2  -1.0 (-24%)     $0.360
(+1 smaller misses; `sl report --json` lists all)

takeaway: ran 51% slower than projected; cost 299% over; biggest miss T3
