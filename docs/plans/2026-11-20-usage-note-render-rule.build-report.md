# superlite build report

projection: fixed forecast saved at lint 2026-11-20T15:35:37 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               3.7       2.0  -1.7 (-45%)
agent cost (USD, +rework)      0.09      0.17  +0.07 (+80%)
task-minutes                   6.8       2.5  -4.2 (-63%)
agents                           2         5  +3 (+150%)
cost split: agents $0.17, rework $0.00, coordinator n/a, total $0.17
concurrency: peak 2 at once (projected 2); critical path actual T2; projected T1 (3.7 min)
model mix: haiku 1 tasks $0.02, sonnet 1 tasks $0.15
quality: tests 13471 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T1    sonnet      3.7     0.7  -3.0 (-81%)     $0.147
T2    haiku       3.1     1.8  -1.2 (-40%)     $0.018

takeaway: ran 45% faster than projected; cost 80% over; biggest miss T1
