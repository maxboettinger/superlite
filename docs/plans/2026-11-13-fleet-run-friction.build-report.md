# superlite build report

projection: fixed forecast saved at lint 2026-11-13T00:13:37

                         Projected    Actual  Delta
wall-clock (min)               3.3       2.1  -1.2 (-36%)
agent cost (USD, +rework)      0.43      0.92  +0.49 (+115%)
task-minutes                  12.7       4.4  -8.3 (-65%)
agents                           4         6  +2 (+50%)
cost split: agents $0.92, rework $0.00, coordinator n/a, total $0.92
concurrency: peak 3 at once (projected 4); critical path actual T1; projected T2 (3.3 min)
model mix: sonnet 4 tasks $0.92
quality: tests 8225 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      3.2     1.0  -2.2 (-68%)     $0.272
T4    sonnet      3.1     1.0  -2.1 (-66%)     $0.210
T1    sonnet      3.1     1.0  -2.0 (-66%)     $0.210
T2    sonnet      3.3     1.3  -2.0 (-61%)     $0.226

takeaway: ran 36% faster than projected; cost 115% over; biggest miss T3
