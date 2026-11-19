# superlite build report

projection: fixed forecast saved at lint 2026-11-19T20:06:04 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              15.4       3.0  -12.4 (-80%)
agent cost (USD, +rework)      0.20      0.57  +0.37 (+182%)
task-minutes                  30.7       3.8  -26.9 (-88%)
agents                           2         9  +7 (+350%)
cost split: agents $0.57, rework $0.00, coordinator n/a, total $0.57
concurrency: peak 2 at once (projected 2); critical path actual T1; projected T1 (15.4 min)
model mix: sonnet 2 tasks $0.57
quality: tests 13195 passed, 0 failed; first-time pass 2/2 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T2    sonnet     15.3     0.8  -14.5 (-95%)    $0.147
T1    sonnet     15.4     3.0  -12.4 (-80%)    $0.424

takeaway: ran 80% faster than projected; cost 182% over; biggest miss T2
