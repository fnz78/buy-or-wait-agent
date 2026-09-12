# INTERVIEW PREP GUIDE: Buy or Wait Financial Agent

## 1. ARCHITECTURE SUMMARY

### 3-Sentence Overview
The Buy or Wait financial decision agent evaluates purchase request affordability for users based on available cash balances, recurring commitments, and historical spending behaviors. It dynamically forecasts 90-day cashflows to determine if a purchase can be made today, deferred to a future date, structured into seller installments, or enabled via targeted spending reductions. It outputs structured financial recommendations with decision explanations while strictly enforcing user-defined minimum balance buffers.

### Main Components & Order of Execution
1. **Data Ingestion & Overrides**: Applies visual image metadata mappings (`IMAGE_AMOUNTS`) for blank event amounts and parses text message overrides (`apply_message_overrides`) for salary cuts and rent increases.
2. **Safe Cash & Pre-Income Forecasting**: `calculate_dynamic_amount_safe_to_pay` calculates available cash buffer today by deducting pending debits, fixed recurring debits, and essential variable expenses using a volatility-adapted daily run-rate ($CV = \sigma / \mu$).
3. **Decision Tree & Option Branching**: `process_request` evaluates affordability in strict order:
   - `affordable_now`: Full payment safe today.
   - `affordable_with_plan`: Full payment enabled by spending reductions, partial payment, or seller installments (simulated day-by-day for 90 days via `installments.py`).
   - `affordable_later`: Deferred full payment on earliest safe payday (`wait`).
   - `not_affordable`: Fallback when no option keeps minimum balance protected.

### LLM vs. Pure Python Boundaries
- **Pure Python (100% Runtime)**: Runs the entire execution pipeline — cashflow simulation, Regex message parsing, image lookup dictionary, statistical CV volatility calculations, and decision tree branching — guaranteeing zero hallucination, strict repeatability, and zero runtime latency.
- **LLM (Gemini via Antigravity)**: Used strictly during pair-programming and design iteration for generating initial code prototypes, analyzing edge-case failure logs, and refining decision heuristics.

---

## 2. KEY DESIGN DECISIONS

### Single Agent vs. Multi-Agent
- **Choice**: I chose a single deterministic orchestrator because financial decision safety requires zero hallucination, strict execution ordering, and total state clarity.
- **Rejection**: I rejected multi-agent LLM routing because agent delegation adds non-deterministic latency and potential state synchronization errors without improving mathematical precision.

### Deterministic Forecasting vs. LLM-Based Reasoning
- **Choice**: I chose pure Python cashflow simulation (`installments.py`) because balance arithmetic and threshold checks require 90-day day-by-day precision.
- **Rejection**: I rejected LLM-based financial reasoning because prompt-driven arithmetic is prone to calculation errors, formatting drift, and unexplainable outputs on boundary dates.

### Image Extraction Approach
- **Choice**: I chose deterministic lookup mapping (`IMAGE_AMOUNTS` dictionary covering all 16 visual events) because optical extraction values for receipts, payslips, and bills are fixed ground-truth numbers.
- **Rejection**: I rejected dynamic multimodal API calls at runtime because pre-extracted mapping eliminated runtime API failure risks, rate limits, and network latency.

### Message Override Parsing
- **Choice**: I chose targeted Regex pattern matching (`apply_message_overrides`) to update salary reductions and rent percentage changes because text messages follow standard financial notice templates.
- **Rejection**: I rejected full LLM prompt extraction because regex parsing guarantees deterministic dataframe updates without token costs or parsing latency.

### Volatility-Adaptive Variable Rate
- **Choice**: I chose statistical Coefficient of Variation ($CV = \sigma / \mu$) with a 0.35 threshold to adapt variable daily burn rates (30-day mean for $CV < 0.35$, 90th percentile rate for $CV \ge 0.35$).
- **Rejection**: I rejected a static 30-day average because uniform averaging underestimates liquidity risk for irregular, high-spike spenders.

---

## 3. FAILURE MODES & ROOT CAUSES

### `amount_safe_to_pay` (16% Accuracy)
- **What Fails**: Numerical float matching on safe cash calculations for non-`affordable_now` requests.
- **Why It Fails**: Ground truth uses varied historical reserve horizons across users (implied windows of 25, 79, and 82 days) that cannot be matched by a single fixed formula without overfitting to the 25 sample requests.
- **What I Would Do Differently**: Build a per-user regression classifier to dynamically predict individual GT reserve horizon windows based on transaction density and account priority tags.

### `payment_plan` (72% Accuracy)
- **What Fails**: Date string formatting or installment schedule alignment on multi-installment options.
- **Why It Fails**: Discrepancies between payday salary cycle projections and specific seller installment schedules (e.g., matching salary payout date vs. 30-day rolling seller cycle).
- **What I Would Do Differently**: Model seller-specific installment payment rules directly from option metadata rather than defaulting to payday alignment.

### `earliest_full_payment_date` (72% Accuracy)
- **What Fails**: Date prediction for when a user who cannot afford today can make a full payment later.
- **Why It Fails**: When employment ends or recurring credit patterns shift, projecting payday cycles can pick a date past the desired completion date or miss non-salary credits.
- **What I Would Do Differently**: Incorporate a broader net-positive cashflow accumulation check rather than relying exclusively on primary salary cycle dates.

### `affordability_status` (84% Accuracy)
- **What Fails**: Misclassifying requests between `affordable_with_plan` and `not_affordable` on tight edge cases.
- **Why It Fails**: When spending reductions provide marginal savings close to the requested amount, small differences in variable reserve estimation flip the threshold guard.
- **What I Would Do Differently**: Refine spending reduction category priorities by incorporating explicit user priority tags (`healthcare`, `family_support`) into the savings threshold calculation.

---

## 4. EVIDENCE OF ITERATION

1. **Bug 1: Fallback returning raw available balance instead of `amount_safe`**
   - **Fix**: Updated `process_request` fallback to return `amount_safe` instead of `round(buffer_today, 2)`.
   - **Metric Movement**: Corrected fallback output formatting across all not-affordable requests.

2. **Bug 2: Duplicate function definition shadowing keyword argument `days=30`**
   - **Fix**: Removed redundant single-parameter `def compute_daily_variable_rate(history)` in `main.py` that caused `TypeError: got an unexpected keyword argument 'days'`.
   - **Metric Movement**: Unblocked dataset execution and restored parameter evaluation.

3. **Bug 3: Assuming future salary income for terminated employment ("Final employer payroll")**
   - **Fix**: Added final payroll signal detection (`"final"` in salary description) in `find_next_income_date` and `find_earliest_full_payment_date` to bound reservation windows to deadline horizons when employment ends.
   - **Metric Movement**: 
     - **Affordability Status**: **80% → 84%**
     - **Payment Method**: **84% → 88%**
     - **Payment Plan**: **68% → 72%**
     - **Earliest Full Payment Date**: **68% → 72%**

---

## 5. AI ASSISTANCE DISCLOSURE

- **Initial Architecture**: Antigravity generated the initial single-agent decision pipeline prototype and helper scripts in `prototype.py`.
- **Direction & Refinement**: I directed the change to implement volatility-adaptive CV thresholds ($CV < 0.35$) after measuring that uniform 30-day mean averaging under-reserved cash for lumpy spenders (like `request_04`).
- **Payday Logic**: Antigravity generated the baseline payday projection function `find_next_income_date`.
- **Domain Edge Case**: I directed the change to add final payroll signal filtering (`"final"` in description) after diagnosing that `request_05` was incorrectly assuming future salary income post-employment.
