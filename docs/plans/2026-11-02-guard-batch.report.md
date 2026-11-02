# superlite build report

projection: fixed forecast saved at lint 2026-11-02T12:51:25 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.4      32.3  +28.9 (+860%)
agent cost (USD, +rework)      0.18      3.04  +2.86 (+1588%)
task-minutes                   6.9      16.2  +9.2 (+133%)
agents                           4         9  +5 (+125%)
cost split: agents $1.46, rework $1.59, coordinator $4.70, total $7.75
concurrency: peak 4 at once (projected 3); critical path actual T1 T2; projected T1 > T2 (3.4 min)
model mix: haiku 2 tasks $0.28, sonnet 2 tasks $2.77, coordinator opus $4.70, coordinator unknown:<synthetic> $0.00
quality: tests 1432 passed, 0 failed; first-time pass n/a; rework dispatches 3; open incidents 1

task  model      pred  actual  delta             cost
T1    sonnet      1.7     7.8  +6.1 (+362%)    $0.933
T3    haiku       2.0     5.4  +3.4 (+169%)    $0.274
T4    haiku       1.5     0.4  -1.2 (-77%)     $0.005
T2    sonnet      1.7     2.6  +0.9 (+55%)     $1.832

takeaway: ran 860% slower than projected; cost 1588% over; biggest miss T1
