# superlite build report

projection: fixed forecast saved at lint 2026-11-12T15:02:15

                         Projected    Actual  Delta
wall-clock (min)              13.5       3.5  -10.0 (-74%)
agent cost (USD, +rework)      0.39      0.90  +0.51 (+130%)
task-minutes                  26.7       6.2  -20.5 (-77%)
agents                           4         5  +1 (+25%)
cost split: agents $0.90, rework $0.00, coordinator n/a, total $0.90
concurrency: peak 2 at once (projected 3); critical path actual T1 T2; projected T1 > T2 (13.5 min)
model mix: sonnet 4 tasks $0.90
quality: tests 7433 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      7.2     1.6  -5.6 (-78%)     $0.247
T2    sonnet      7.1     1.7  -5.4 (-76%)     $0.259
T1    sonnet      6.3     1.2  -5.1 (-81%)     $0.146
T4    sonnet      6.0     1.6  -4.4 (-73%)     $0.247

takeaway: ran 74% faster than projected; cost 130% over; biggest miss T3
