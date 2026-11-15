# superlite build report

projection: fixed forecast saved at lint 2026-11-15T11:18:16

                         Projected    Actual  Delta
wall-clock (min)              11.2       3.9  -7.3 (-65%)
agent cost (USD, +rework)      0.42      0.99  +0.57 (+136%)
task-minutes                  16.1       4.6  -11.5 (-72%)
agents                           3        20  +17 (+567%)
cost split: agents $0.99, rework $0.00, coordinator n/a, total $0.99
concurrency: peak 2 at once (projected 2); critical path actual T1 T2; projected T1 > T2 (11.2 min)
model mix: sonnet 3 tasks $0.99
quality: tests 11000 passed, 0 failed; first-time pass 3/3 (100%); rework dispatches 0; open incidents 1

task  model      pred  actual  delta             cost
T1    sonnet      5.6     1.6  -4.0 (-72%)     $0.356
T2    sonnet      5.5     1.8  -3.7 (-68%)     $0.460
T3    sonnet      4.9     1.2  -3.7 (-76%)     $0.172

takeaway: ran 65% faster than projected; cost 136% over; biggest miss T1
