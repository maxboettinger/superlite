# superlite build report

projection: fixed forecast saved at lint 2026-11-20T12:53:20 (plan edited since)

                         Projected    Actual  Delta
wall-clock (min)              18.7       3.5  -15.2 (-81%)
agent cost (USD, +rework)      0.35      0.62  +0.27 (+78%)
task-minutes                  24.9       3.8  -21.1 (-85%)
agents                           4         9  +5 (+125%)
cost split: agents $0.62, rework $0.00, coordinator n/a, total $0.62
concurrency: peak 2 at once (projected 2); critical path actual T1 T2 T3 T4; projected T1 > T3 > T4 (18.7 min)
model mix: sonnet 4 tasks $0.62
quality: tests 13382 passed, 0 failed (last full run; newer fast run: 4 passed, 0 failed); first-time pass 4/4 (100%); rework dispatches 0; open incidents 0

task  model      pred  actual  delta             cost
T3    sonnet      6.3     0.8  -5.5 (-88%)     $0.152
T2    sonnet      6.2     0.7  -5.5 (-89%)     $0.151
T1    sonnet      6.2     0.7  -5.5 (-89%)     $0.139
T4    sonnet      6.2     1.6  -4.5 (-73%)     $0.175

takeaway: ran 81% faster than projected; cost 78% over; biggest miss T3
