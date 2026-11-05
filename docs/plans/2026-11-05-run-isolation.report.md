# superlite build report

projection: fixed forecast saved at lint 2026-11-05T10:47:22 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              10.3      64.1  +53.8 (+521%)
agent cost (USD, +rework)      0.82      1.97  +1.15 (+139%)
task-minutes                  20.3      13.7  -6.6 (-32%)
agents                           7        17  +10 (+143%)
cost split: agents $1.48, rework $0.49, coordinator $14.42 (97 turns, context median 319.3k, peak 387.6k; session $25.35), total $16.39
concurrency: peak 3 at once (projected 5); critical path actual T6 T7; projected T1 > T4 > T7 (10.3 min)
model mix: sonnet 7 tasks $1.97, coordinator fable $14.42
quality: tests 2238 passed, 0 failed; first-time pass 4/7 (57%); rework dispatches 6; open incidents 0

task  model      pred  actual  delta             cost
T4    sonnet      3.3     1.4  -2.0 (-59%)     $0.211  first-time miss
T7    sonnet      4.1     2.3  -1.8 (-43%)     $0.710  first-time miss
T1    sonnet      2.9     1.5  -1.4 (-47%)     $0.161
T2    sonnet      2.5     1.3  -1.2 (-48%)     $0.150
T5    sonnet      2.4     1.3  -1.2 (-47%)     $0.150
(+2 smaller misses; `sl report --json` lists all)

takeaway: ran 521% slower than projected; cost 139% over; biggest miss T4
