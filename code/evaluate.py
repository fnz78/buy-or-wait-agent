import pandas as pd
import sys

"""
=== SELF-SCORING EVALUATION HARNESS ===
Compares predictions against ground-truth dataset/sample_requests.csv.
"""


def evaluate_predictions(pred_path, truth_path='dataset/sample_requests.csv'):
    pred_df = pd.read_csv(pred_path)
    truth_df = pd.read_csv(truth_path)
    
    merged = pd.merge(truth_df, pred_df, on='request_id', suffixes=('_gt', '_pred'))
    
    total = len(merged)
    if total == 0:
        print("Error: No matching requests found between predictions and ground truth.")
        return
        
    status_matches = 0
    method_matches = 0
    amount_matches = 0
    plan_matches = 0
    earliest_date_matches = 0
    spending_matches = 0
    
    print(f"\n=======================================================")
    print(f"       EVALUATION REPORT ({total} Sample Requests)      ")
    print(f"=======================================================\n")
    
    failures = []
    
    for idx, row in merged.iterrows():
        req_id = row['request_id']
        u_id = row['user_id']
        
        gt_status = str(row['affordability_status_gt'])
        pred_status = str(row['affordability_status_pred'])
        
        gt_method = str(row['recommended_payment_method_gt'])
        pred_method = str(row['recommended_payment_method_pred'])
        
        gt_amt = float(row['amount_safe_to_pay_gt'])
        pred_amt = float(row['amount_safe_to_pay_pred']) if pd.notnull(row['amount_safe_to_pay_pred']) else 0.0
        
        gt_plan = str(row['payment_plan_gt']) if pd.notnull(row['payment_plan_gt']) else 'none'
        pred_plan = str(row['payment_plan_pred']) if pd.notnull(row['payment_plan_pred']) else 'none'
        
        gt_edate = str(row['earliest_date_for_full_payment_gt']) if pd.notnull(row['earliest_date_for_full_payment_gt']) else ''
        pred_edate = str(row['earliest_date_for_full_payment_pred']) if pd.notnull(row['earliest_date_for_full_payment_pred']) else ''
        
        gt_spend = str(row['spending_changes_needed_gt']) if pd.notnull(row['spending_changes_needed_gt']) else 'none'
        pred_spend = str(row['spending_changes_needed_pred']) if pd.notnull(row['spending_changes_needed_pred']) else 'none'
        
        status_ok = (gt_status == pred_status)
        method_ok = (gt_method == pred_method)
        amount_ok = (abs(gt_amt - pred_amt) <= 1.0)
        plan_ok = (gt_plan == pred_plan)
        edate_ok = (gt_edate == pred_edate)
        spend_ok = (gt_spend == pred_spend)
        
        if status_ok: status_matches += 1
        if method_ok: method_matches += 1
        if amount_ok: amount_matches += 1
        if plan_ok: plan_matches += 1
        if edate_ok: earliest_date_matches += 1
        if spend_ok: spending_matches += 1
        
        if not (status_ok and method_ok and amount_ok):
            failures.append({
                'request_id': req_id,
                'user_id': u_id,
                'gt_status': gt_status,
                'pred_status': pred_status,
                'gt_method': gt_method,
                'pred_method': pred_method,
                'gt_amt': gt_amt,
                'pred_amt': pred_amt,
                'gt_plan': gt_plan,
                'pred_plan': pred_plan,
                'gt_spend': gt_spend,
                'pred_spend': pred_spend
            })
            
    print(f"Accuracy Summary:")
    print(f"  - Affordability Status Accuracy : {status_matches}/{total} ({status_matches/total*100:.1f}%)")
    print(f"  - Payment Method Accuracy       : {method_matches}/{total} ({method_matches/total*100:.1f}%)")
    print(f"  - Amount Safe to Pay Accuracy  : {amount_matches}/{total} ({amount_matches/total*100:.1f}%)")
    print(f"  - Payment Plan Accuracy         : {plan_matches}/{total} ({plan_matches/total*100:.1f}%)")
    print(f"  - Earliest Full Payment Date    : {earliest_date_matches}/{total} ({earliest_date_matches/total*100:.1f}%)")
    print(f"  - Spending Changes Accuracy     : {spending_matches}/{total} ({spending_matches/total*100:.1f}%)")
    
    print(f"\n-------------------------------------------------------")
    print(f"                   FAILURES BREAKDOWN ({len(failures)})")
    print(f"-------------------------------------------------------")
    for f in failures:
        print(f"Req: {f['request_id']} ({f['user_id']})")
        print(f"  GT  : Status={f['gt_status']:20s} Method={f['gt_method']:15s} Amt={f['gt_amt']:12.2f} Plan={f['gt_plan']}")
        print(f"  PRED: Status={f['pred_status']:20s} Method={f['pred_method']:15s} Amt={f['pred_amt']:12.2f} Plan={f['pred_plan']}")
        print()


if __name__ == '__main__':
    pred_file = sys.argv[1] if len(sys.argv) > 1 else 'sample_output.csv'
    evaluate_predictions(pred_file)
