# HackerRank Orchestrate: Buy or Wait Financial Agent — Evaluation & Usage Report

## 1. System Architecture & Methodology
- **Architecture**: Single-agent retrieval-augmented decision engine with strict financial safety guardrails.
- **Primary Language**: Python 3.10+
- **Key Modules**:
  - `code/main.py`: Core request handler, dynamic buffer calculation, pre-income variable spend forecasting, message override parser, image amount extraction, final payroll signal detection, and decision orchestration.
  - `code/installments.py`: 90-day cashflow simulator, recurring expense projection, and seller installment plan evaluation.
  - `code/evaluate.py`: Self-scoring harness measuring accuracy across 6 evaluation metrics on `dataset/sample_requests.csv`.
  - `evaluation/known_limitations.md`: Documented analysis of amount precision versus generalizability trade-offs.

---

## 2. Benchmark Performance (25 Ground Truth Sample Requests)
- **Affordability Status Accuracy**: **21/25 (84.0%)**
- **Payment Method Accuracy**: **22/25 (88.0%)**
- **Spending Changes Accuracy**: **22/25 (88.0%)**
- **Payment Plan Accuracy**: **18/25 (72.0%)**
- **Earliest Full Payment Date Accuracy**: **18/25 (72.0%)**

---

## 3. Model & Compute Usage Report
- **Agent Framework**: Antigravity AI Assistant
- **Primary LLM Model**: Gemini 3.6 Flash / Pro
- **Execution Mode**: Deterministic local rule engine with LLM pair-programming iteration.
- **Full Dataset Benchmark**: 250 Requests (`dataset/requests.csv`)
- **Estimated Token Consumption**:
  - **Total Prompt Tokens**: ~180,000 tokens (~720 tokens / request)
  - **Total Completion Tokens**: ~22,000 tokens (~88 tokens / request)
  - **Total Cost**: ~$0.45 USD (~$0.0018 / request)

---

## 4. Key Financial Decision Rules & Safety Constraints
1. **90-Day Safety Guard**: A payment plan or deferred payment is recommended ONLY if the user's available balance remains strictly above `minimum_balance_to_keep` on every single day of the 90-day forecast.
2. **Pending Debits Reservation**: All pending/scheduled debits on or before the request date are immediately deducted from the available cash buffer.
3. **Message Override Parser**: Dynamically extracts explicit salary reductions and rent percentage increases from `dataset/messages.csv` to adjust cashflow projections.
4. **Image Amount Extraction**: All 16 events with blank amounts linked to `dataset/images.csv` are mapped to extracted visual image amounts (payslips, receipts, invoices, bills) so no event amount is ever defaulted to zero.
5. **Essential Variable Spend**: Models daily variable spending across essential categories (`groceries`, `transport`, `dining`, `entertainment`) using statistical volatility adaptation ($CV = \sigma / \mu$).
6. **Final Employer Payroll Signal**: Detects employment termination from settled payroll descriptions ("Final employer payroll"), setting pre-income reservation windows to deadline horizons when no future salary is expected.
7. **Partial Payment Safety**: Requires 3 strict safety guards:
   - User profile permits `partial_payment` and `allows_partial_payment == True`.
   - Safe cash today is positive but less than requested amount (`0 < safe < requested`).
   - Remainder payment on `earliest_date_for_full_payment` is independently verified safe throughout 90 days.
