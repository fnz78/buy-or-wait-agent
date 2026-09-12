# Known Limitations

## amount_safe_to_pay Precision: 16%

The reserve calculation for non-affordable_now requests does not match ground truth. Deltas range from hundreds to millions of currency units.

Evidence:
- 13 of 25 sample requests have deltas > 1000 units
- Reverse-engineering the reserve rule across three no-income users (request_03, request_05, request_10) yielded implied historical windows of 25, 79, and 82 days — inconsistent, confirming no single historical formula reproduces the GT reserve

Decision:
Kept the principled 90-day trajectory simulation with volatility-adaptive variable rates. Chose generalization over sample-fitting.

## Other Metrics

All other metrics are verified:
- Affordability status: 84%
- Payment method: 88%
- Spending changes: 88%
- Payment plan: 72%
- Earliest full payment date: 72%
