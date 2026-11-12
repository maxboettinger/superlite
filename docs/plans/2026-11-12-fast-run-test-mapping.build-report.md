# superlite build report

projection: fixed forecast saved at lint 2026-11-12T12:06:07

                         Projected    Actual  Delta
wall-clock (min)              12.2     148.9  +136.8 (+1124%)
agent cost (USD, +rework)      1.05      2.96  +1.92 (+184%)
task-minutes                  16.6      13.3  -3.3 (-20%)
agents                           8        19  +11 (+138%)
cost split: agents $2.37, rework $0.59, coordinator n/a, total $2.96
concurrency: peak 6 at once (projected 2); critical path actual T1 T3 T4; projected T1 > T2 > T3 > T4 > T6 > T8 (12.2 min)
model mix: sonnet 8 tasks $2.96
quality: tests 7333 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/8 (12%); rework dispatches 6; open incidents 0

task  model      pred  actual  delta             cost
T7    sonnet      2.4     1.0  -1.4 (-57%)     $0.211  first-time miss
T1    sonnet      2.6     1.3  -1.3 (-49%)     $0.375  first-time miss
T8    sonnet      1.6     0.7  -0.9 (-54%)     $0.223  first-time miss
T6    sonnet      2.0     2.5  +0.4 (+22%)     $0.528  first-time miss
T4    sonnet      1.9     1.7  -0.2 (-12%)     $0.444  first-time miss
(+3 smaller misses; `sl report --json` lists all)

takeaway: ran 1124% slower than projected; cost 184% over; biggest miss T7
