# superlite build report

projection: fixed forecast saved at lint 2026-11-20T11:41:09

                         Projected    Actual  Delta
wall-clock (min)              11.0      26.8  +15.8 (+144%)
agent cost (USD, +rework)      0.17      0.49  +0.32 (+186%)
task-minutes                  11.0      26.8  +15.8 (+144%)
agents                           1         4  +3 (+300%)
cost split: agents $0.49, rework $0.00, coordinator n/a, total $0.49
concurrency: peak 1 at once (projected 1); critical path actual T1; projected T1 (11.0 min)
model mix: sonnet 1 tasks $0.49
quality: tests 13307 passed, 0 failed (last full run; newer fast run: 6 passed, 1 failed); first-time pass 0/1 (0%); rework dispatches 0; open incidents 1

task  model      pred  actual  delta             cost
T1    sonnet     11.0    26.8  +15.8 (+144%)   $0.493  first-time miss

takeaway: ran 144% slower than projected; cost 186% over; biggest miss T1
