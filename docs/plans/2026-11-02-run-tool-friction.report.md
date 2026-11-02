# superlite build report

projection: fixed forecast saved at lint 2026-11-02T13:56:24 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)               2.2      48.4  +46.2 (+2103%)
agent cost (USD, +rework)      0.31      5.70  +5.39 (+1725%)
task-minutes                   9.1      46.3  +37.2 (+407%)
agents                           5        18  +13 (+260%)
cost split: agents $4.88, rework $0.82, coordinator $6.62, total $12.32
concurrency: peak 4 at once (projected 5); critical path actual T2; projected T3 (2.2 min)
model mix: haiku 2 tasks $0.20, sonnet 6 tasks $5.50, coordinator opus $6.62
quality: tests 1527 passed, 0 failed; first-time pass n/a; rework dispatches 4; open incidents 3

task  model      pred  actual  delta             cost
T3    sonnet      2.2     6.4  +4.2 (+191%)    $0.753
T1    sonnet      2.2     5.8  +3.6 (+167%)    $0.904
T4    haiku       1.5     2.7  +1.1 (+74%)     $0.136
T5    haiku       1.5     1.6  +0.1 (+7%)      $0.064
T2    sonnet      1.7     1.7  +0.1 (+3%)      $0.437
(+3 smaller misses; `sl report --json` lists all)

takeaway: ran 2103% slower than projected; cost 1725% over; biggest miss T3
