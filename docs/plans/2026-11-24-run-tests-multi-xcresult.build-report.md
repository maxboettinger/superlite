# superlite build report

projection: fixed forecast saved at lint 2026-11-24T10:31:11 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              14.3       5.7  -8.6 (-60%)
agent cost (USD, +rework)      0.24      0.57  +0.33 (+138%)
task-minutes                  28.1       8.7  -19.4 (-69%)
agents                           2         4  +2 (+100%)
cost split: agents $0.57, rework $0.00, coordinator n/a, total $0.57
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T2 (14.3 min)
model mix: sonnet 2 tasks $0.57
quality: tests 13751 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet     13.9     3.0  -10.8 (-78%)    $0.320
T2    sonnet     14.3     5.7  -8.6 (-60%)     $0.251

takeaway: ran 60% faster than projected; cost 138% over; biggest miss T1
