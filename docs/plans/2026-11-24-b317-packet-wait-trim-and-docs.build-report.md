# superlite build report

projection: fixed forecast saved at lint 2026-11-24T14:17:38

                         Projected    Actual  Delta
wall-clock (min)               3.7      14.4  +10.6 (+285%)
agent cost (USD, +rework)      0.16      0.36  +0.20 (+122%)
task-minutes                  13.1      21.3  +8.2 (+62%)
agents                           4        10  +6 (+150%)
cost split: agents $0.36, rework $0.00, coordinator n/a, total $0.36
concurrency: peak 4 at once (projected 4); critical path actual T3; projected T2 (3.7 min)
model mix: haiku 2 tasks $0.02, sonnet 2 tasks $0.34
quality: tests 14030 passed, 0 failed; first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    haiku       3.1    14.1  +11.0 (+355%)   $0.015
T4    haiku       3.1     0.4  -2.7 (-86%)     $0.007
T1    sonnet      3.2     2.5  -0.7 (-22%)     $0.120
T2    sonnet      3.7     4.3  +0.5 (+14%)     $0.220

takeaway: ran 285% slower than projected; cost 122% over; biggest miss T3
