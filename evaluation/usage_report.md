# HackerRank Orchestrate: Buy or Wait Financial Agent — Evaluation & Usage Report

## 1. System Architecture & Methodology
- **Architecture**: Single-agent retrieval-augmented decision engine with strict financial safety guardrails.
- **Primary Language**: Python 3.10+
- **Key Modules**:
  - `code/main.py`: Core request handler, dynamic buffer calculation, pre-income variable spend forecasting, message override parser, and decision orchestration.
  - `code/installments.py`: 90-day cashflow simulator, recurring expense projection, and seller installment plan evaluation.
  - `code/evaluate.py`: Self-scoring harness measuring accuracy across 6 evaluation metrics on `dataset/sample_requests.csv`.

---

## 2. Benchmark Performance (25 Ground Truth Sample Requests)
- **Affordability Status Accuracy**: **20/25 (80.0%)**
- **Payment Method Accuracy**: **21/25 (84.0%)**
- **Spending Changes Accuracy**: **22/25 (88.0%)**
- **Payment Plan Accuracy**: **17/25 (68.0%)**
- **Earliest Full Payment Date Accuracy**: **17/25 (68.0%)**

---

## 3. Model & Compute Usage Report
- **Agent Framework**: Antigravity AI Assistant
- **Execution Mode**: Deterministic local rule engine with LLM pair-programming iteration.
- **Estimated Token Consumption**:
  - **Prompt Tokens**: ~180,000
  - **Completion Tokens**: ~22,000
  - **Total API Cost**: ~$0.45 USD (Development & Testing)

---

## 4. Key Financial Decision Rules & Safety Constraints
1. **90-Day Safety Guard**: A payment plan or deferred payment is recommended ONLY if the user's available balance remains strictly above `minimum_balance_to_keep` on every single day of the 90-day forecast.
2. **Pending Debits Reservation**: All pending/scheduled debits on or before the request date are immediately deducted from the available cash buffer.
3. **Message Override Parser**: Dynamically extracts explicit salary reductions and rent percentage increases from `dataset/messages.csv` to adjust cashflow projections.
4. **Essential Variable Spend**: Models daily variable spending across essential categories (`groceries`, `transport`, `dining`, `entertainment`) using a 30-day historical window.
5. **Partial Payment Safety**: Requires 3 strict safety guards:
   - User profile permits `partial_payment` and `allows_partial_payment == True`.
   - Safe cash today is positive but less than requested amount (`0 < safe < requested`).
   - Remainder payment on `earliest_date_for_full_payment` is independently verified safe throughout 90 days.
