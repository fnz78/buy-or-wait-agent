import pandas as pd
import sys
from datetime import datetime, timedelta

# Load datasets
samples = pd.read_csv('dataset/sample_requests.csv')
output = pd.read_csv('sample_output.csv')
profiles = pd.read_csv('dataset/financial_profiles.csv')
events = pd.read_csv('dataset/financial_events.csv')

merged = samples.merge(output, on='request_id', suffixes=('_gt', '_calc'))

merged['gt_amt'] = merged['amount_safe_to_pay_gt'].astype(float)
merged['calc_amt'] = merged['amount_safe_to_pay_calc'].astype(float)
merged['delta'] = merged['calc_amt'] - merged['gt_amt']
merged['abs_delta'] = merged['delta'].abs()

merged = merged.sort_values('abs_delta', ascending=False)

print("\n=========================================================================")
print("                   AMOUNT SAFE TO PAY AUDIT REPORT                       ")
print("=========================================================================\n")

cols = ['request_id', 'user_id', 'requested_amount', 'gt_amt', 'calc_amt', 'delta', 'affordability_status_gt', 'affordability_status_calc']
print(merged[cols].head(25).to_string(index=False))

print("\n-------------------------------------------------------------------------")
print("               SUMMARY OF FAILURES BY SIGN (DELTA = CALC - GT)          ")
print("-------------------------------------------------------------------------")
too_high = merged[merged['delta'] > 1.0]
too_low = merged[merged['delta'] < -1.0]
exact = merged[merged['abs_delta'] <= 1.0]

print(f"Exact matches (within 1.0) : {len(exact)}")
print(f"Calculated TOO HIGH (delta > 0) : {len(too_high)} (Under-reserving or missing expenses)")
print(f"Calculated TOO LOW  (delta < 0) : {len(too_low)} (Over-reserving or double-counting)")

print("\n--- TOO HIGH FAILURES (Delta > 0) ---")
if not too_high.empty:
    print(too_high[['request_id', 'user_id', 'gt_amt', 'calc_amt', 'delta']].to_string(index=False))

print("\n--- TOO LOW FAILURES (Delta < 0) ---")
if not too_low.empty:
    print(too_low[['request_id', 'user_id', 'gt_amt', 'calc_amt', 'delta']].to_string(index=False))
