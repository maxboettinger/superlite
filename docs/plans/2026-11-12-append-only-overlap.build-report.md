# superlite build report

projection: fixed forecast saved at lint 2026-11-12T18:38:40

                         Projected    Actual  Delta
wall-clock (min)              18.5       2.0  -16.5 (-89%)
agent cost (USD, +rework)      0.37      0.66  +0.28 (+77%)
task-minutes                  34.3       3.4  -30.9 (-90%)
agents                           4         5  +1 (+25%)
cost split: agents $0.66, rework $0.00, coordinator n/a, total $0.66
concurrency: peak 2 at once (projected 3); critical path actual T1 T3 T4; projected T1 > T3 (18.5 min)
model mix: sonnet 4 tasks $0.66
quality: tests 7893 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 1/4 (25%); rework dispatches 0; open incidents 1

task  model      pred  actual  delta             cost
T1    sonnet      9.2     0.6  -8.6 (-94%)     $0.168
T3    sonnet      9.2     0.9  -8.4 (-91%)     $0.217  first-time miss
T2    sonnet      8.4     1.0  -7.4 (-88%)     $0.135  first-time miss
T4    sonnet      7.5     1.0  -6.5 (-87%)     $0.135  first-time miss

takeaway: ran 89% faster than projected; cost 77% over; biggest miss T1
