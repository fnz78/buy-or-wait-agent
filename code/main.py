import pandas as pd
import sys
from datetime import datetime, timedelta
from installments import evaluate_installments, get_projected_recurring_events, forecast_installment_plan, FIXED_RECURRING_CATEGORIES


def find_next_income_date(u_events, req_date):
    future_income = u_events[
        (u_events['direction'] == 'credit') &
        (u_events['status'].isin(['scheduled', 'pending'])) &
        (pd.notnull(u_events['event_date']))
    ]
    
    dates = []
    for _, ev in future_income.iterrows():
        date_str = str(ev['settlement_date']) if pd.notnull(ev['settlement_date']) and str(ev['settlement_date']) != 'nan' else str(ev['event_date'])
        if date_str != 'nan':
            e_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if e_date >= req_date:
                dates.append(e_date)
            
    if dates:
        return min(dates)
        
    salaries = u_events[
        (u_events['direction'] == 'credit') &
        (u_events['category'] == 'salary') &
        (u_events['status'] == 'settled') &
        (pd.notnull(u_events['event_date']))
    ]
    if not salaries.empty:
        latest_sal = salaries.sort_values('event_date', ascending=False).iloc[0]
        sal_date = datetime.strptime(str(latest_sal['event_date']), '%Y-%m-%d').date()
        day = sal_date.day
        
        if req_date.day <= day:
            try:
                next_date = datetime(req_date.year, req_date.month, day).date()
            except ValueError:
                next_date = datetime(req_date.year, req_date.month, 28).date()
        else:
            year = req_date.year + (req_date.month) // 12
            month = req_date.month % 12 + 1
            try:
                next_date = datetime(year, month, day).date()
            except ValueError:
                next_date = datetime(year, month, 28).date()
        if next_date >= req_date:
            return next_date
            
    return req_date + timedelta(days=30)


def compute_daily_variable_rate(history):
    """
    history: settled groceries/transport/dining events in last 60 days
    Returns a daily IDR/EUR/USD rate.
    """
    if len(history) < 3:
        return 0.0

    # Outlier filter
    median = history['amount'].median()
    filtered = history[history['amount'] <= 3 * median]
    if len(filtered) < 2:
        return 0.0

    mean = filtered['amount'].mean()
    std = filtered['amount'].std()
    cv = std / mean if mean > 0 else 0

    if cv < 0.3:
        # Steady pattern: daily rate = total / 60
        return filtered['amount'].sum() / 60
    else:
        # Lumpy pattern: median purchase × purchases per day
        days_between = 60 / len(filtered)
        return median / days_between


def calculate_dynamic_amount_safe_to_pay(user_id, req_date_str, requested_amount, profile, events_df):
    avail_balance = float(profile['current_available_balance'])
    min_balance = float(profile['minimum_balance_to_keep'])
    req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date()
    
    u_events = events_df[events_df['user_id'] == user_id]
    
    # Subtract pending/scheduled debits on or before req_date
    pending_today = 0.0
    for _, ev in u_events.iterrows():
        st = str(ev['status']).lower()
        if st in ['cancelled']: continue
        if str(ev['direction']).lower() == 'debit' and st in ['scheduled', 'pending']:
            d_str = str(ev['settlement_date']) if pd.notnull(ev['settlement_date']) and str(ev['settlement_date']) != 'nan' else str(ev['event_date'])
            if d_str != 'nan':
                e_d = datetime.strptime(d_str, '%Y-%m-%d').date()
                if e_d <= req_date:
                    pending_today += float(ev['amount']) if pd.notnull(ev['amount']) else 0.0

    buffer_today = avail_balance - min_balance - pending_today
    if buffer_today <= 0:
        return 0.0
        
    next_inc_date = find_next_income_date(u_events, req_date)
    days_to_income = max(1, (next_inc_date - req_date).days)
    
    # 1. Projected fixed recurring debits between req_date and next_inc_date
    projected_recurring = get_projected_recurring_events(user_id, req_date, events_df, forecast_days=days_to_income)
    fixed_pre_income = sum(-net for d, net in projected_recurring.items() if req_date <= d < next_inc_date and net < 0)
    
    # 2. Reserve explicit pending/scheduled pre-income debits (after req_date)
    pre_income_debits = fixed_pre_income
    for _, ev in u_events.iterrows():
        status = str(ev['status']).lower()
        if status in ['cancelled']:
            continue
        direction = str(ev['direction']).lower()
        if direction == 'debit' and status in ['scheduled', 'pending']:
            date_str = str(ev['settlement_date']) if pd.notnull(ev['settlement_date']) and str(ev['settlement_date']) != 'nan' else str(ev['event_date'])
            if date_str != 'nan':
                e_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if req_date < e_date < next_inc_date:
                    amt = float(ev['amount']) if pd.notnull(ev['amount']) else 0.0
                    pre_income_debits += amt
                    
    # 3. Forecast ESSENTIAL VARIABLE run-rate over last 30 days (groceries, transport, dining, entertainment)
    history_start = req_date - timedelta(days=30)
    variable_categories = ['groceries', 'transport', 'dining', 'entertainment']
    
    u_events_copy = u_events.copy()
    u_events_copy['event_date_dt'] = pd.to_datetime(u_events_copy['event_date'])
    req_date_dt = pd.to_datetime(req_date_str)
    history_start_dt = pd.to_datetime(history_start)
    
    hist_debits = u_events_copy[
        (u_events_copy['category'].isin(variable_categories)) &
        (u_events_copy['direction'] == 'debit') &
        (u_events_copy['status'] == 'settled') &
        (u_events_copy['event_date_dt'] < req_date_dt) &
        (u_events_copy['event_date_dt'] >= history_start_dt)
    ].copy()
    
    daily_rate = hist_debits['amount'].sum() / 30.0 if not hist_debits.empty else 0.0
    variable_reserve = daily_rate * days_to_income
    
    safe = buffer_today - pre_income_debits - variable_reserve
    return max(0.0, round(safe, 2))


def check_full_payment_safety_on_date(user_id, req_date, pay_date, requested_amount, profile, events_df):
    avail_balance = float(profile['current_available_balance'])
    min_balance = float(profile['minimum_balance_to_keep'])
    end_date = req_date + timedelta(days=90)
    
    events_by_date = get_projected_recurring_events(user_id, req_date, events_df, forecast_days=90)
    
    u_events = events_df[events_df['user_id'] == user_id]
    for _, event in u_events.iterrows():
        status = str(event['status']).lower()
        if status in ['cancelled']:
            continue
        if pd.notnull(event['event_date']):
            date_str = str(event['settlement_date']) if pd.notnull(event['settlement_date']) and str(event['settlement_date']) != 'nan' else str(event['event_date'])
            if date_str != 'nan':
                e_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                if req_date <= e_date <= end_date:
                    amount = float(event['amount']) if pd.notnull(event['amount']) else 0.0
                    direction = str(event['direction']).lower()
                    net_change = amount if direction == 'credit' else -amount
                    if status in ['scheduled', 'pending']:
                        events_by_date.setdefault(e_date, 0.0)
                        events_by_date[e_date] += net_change

    if req_date <= pay_date <= end_date:
        events_by_date.setdefault(pay_date, 0.0)
        events_by_date[pay_date] -= requested_amount

    current_bal = avail_balance
    min_bal = current_bal
    
    curr_date = req_date
    while curr_date <= end_date:
        if curr_date in events_by_date:
            current_bal += events_by_date[curr_date]
        if current_bal < min_bal:
            min_bal = current_bal
        curr_date += timedelta(days=1)
        
    return min_bal >= min_balance


def find_earliest_full_payment_date(user_id, req_date_str, requested_amount, desired_completion_date_str, profile, events_df):
    req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date()
    desired_date = datetime.strptime(desired_completion_date_str, '%Y-%m-%d').date()
    
    u_events = events_df[events_df['user_id'] == user_id]
    
    salaries = u_events[
        (u_events['direction'] == 'credit') &
        (u_events['category'] == 'salary') &
        (u_events['status'] == 'settled') &
        (pd.notnull(u_events['event_date']))
    ]
    if not salaries.empty:
        days = [datetime.strptime(str(d), '%Y-%m-%d').day for d in salaries['event_date']]
        day = max(set(days), key=days.count)
    else:
        day = 15
        
    try:
        candidate = datetime(desired_date.year, desired_date.month, day).date()
    except ValueError:
        candidate = datetime(desired_date.year, desired_date.month, 28).date()
        
    if candidate > desired_date:
        m = desired_date.month - 1 if desired_date.month > 1 else 12
        y = desired_date.year if desired_date.month > 1 else desired_date.year - 1
        try:
            candidate = datetime(y, m, day).date()
        except ValueError:
            candidate = datetime(y, m, 28).date()
            
    if candidate >= req_date:
        if check_full_payment_safety_on_date(user_id, req_date, candidate, requested_amount, profile, events_df):
            return candidate
        
    return None


def process_request(row, profiles_df, events_df, options_df):
    user_id = row['user_id']
    req_id = row['request_id']
    req_date = row['request_date']
    desired_completion_date = row['desired_completion_date']
    requested_amount = float(row['requested_amount'])
    allows_partial = str(row['allows_partial_payment']).lower() == 'true'
    
    profile = profiles_df[profiles_df['user_id'] == user_id].iloc[0]
    user_methods = str(profile['payment_methods_user_will_consider']).split('|')
    
    # Compute precision amount_safe_to_pay
    amount_safe = calculate_dynamic_amount_safe_to_pay(
        user_id, req_date, requested_amount, profile, events_df
    )
    
    amt_str = f"{requested_amount:.2f}".rstrip('0').rstrip('.')
    
    # 1. Check Full Payment Today (affordable_now)
    full_payment_safe = (requested_amount <= amount_safe)
    if full_payment_safe and 'full_payment' in user_methods:
        return {
            'request_id': req_id,
            'amount_safe_to_pay': requested_amount,
            'affordability_status': 'affordable_now',
            'recommended_payment_method': 'full_payment',
            'payment_plan': f"{req_date}:{amt_str}",
            'earliest_date_for_full_payment': req_date,
            'spending_changes_needed': 'none',
            'decision_explanation': f"Pay {amt_str} today. Balance remains safe throughout 90-day forecast."
        }
        
    # 2. Check Partial Payment Option (affordable_with_plan)
    # Guard 1: allows_partial is True AND 'partial_payment' in user_methods
    # Guard 2: 0 < amount_safe < requested_amount
    # Guard 3: earliest_date is not None and safe
    if allows_partial and 'partial_payment' in user_methods and 0 < amount_safe < requested_amount:
        earliest_date = find_earliest_full_payment_date(
            user_id, req_date, requested_amount, desired_completion_date, profile, events_df
        )
        if earliest_date is not None:
            earliest_str = earliest_date.strftime('%Y-%m-%d')
            remainder = requested_amount - amount_safe
            safe_str = f"{amount_safe:.2f}".rstrip('0').rstrip('.')
            rem_str = f"{remainder:.2f}".rstrip('0').rstrip('.')
            return {
                'request_id': req_id,
                'amount_safe_to_pay': amount_safe,
                'affordability_status': 'affordable_with_plan',
                'recommended_payment_method': 'partial_payment',
                'payment_plan': f"{req_date}:{safe_str}|{earliest_str}:{rem_str}",
                'earliest_date_for_full_payment': earliest_str,
                'spending_changes_needed': 'none',
                'decision_explanation': f"Pay {safe_str} today and remaining {rem_str} on {earliest_str}."
            }

    # 3. Check Installment Payment Options (affordable_with_plan)
    best_installment = evaluate_installments(row, profile, options_df, events_df, amount_safe)
    if best_installment is not None:
        earliest_sal_date = find_earliest_full_payment_date(
            user_id, req_date, requested_amount, desired_completion_date, profile, events_df
        )
        earliest_sal_str = earliest_sal_date.strftime('%Y-%m-%d') if earliest_sal_date else req_date
        return {
            'request_id': req_id,
            'amount_safe_to_pay': min(amount_safe, requested_amount),
            'affordability_status': 'affordable_with_plan',
            'recommended_payment_method': best_installment['method'],
            'payment_plan': best_installment['plan_str'],
            'earliest_date_for_full_payment': earliest_sal_str,
            'spending_changes_needed': 'none',
            'decision_explanation': f"Use {best_installment['num_payments']} payments starting {best_installment['first_date']}."
        }
            
    # 3. Check Affordable Later / Wait Branch
    if 'full_payment' in user_methods:
        earliest_date = find_earliest_full_payment_date(
            user_id, req_date, requested_amount, desired_completion_date, profile, events_df
        )
        if earliest_date is not None:
            earliest_str = earliest_date.strftime('%Y-%m-%d')
            return {
                'request_id': req_id,
                'amount_safe_to_pay': amount_safe,
                'affordability_status': 'affordable_later',
                'recommended_payment_method': 'wait',
                'payment_plan': f"{earliest_str}:{amt_str}",
                'earliest_date_for_full_payment': earliest_str,
                'spending_changes_needed': 'none',
                'decision_explanation': f"Wait until {earliest_str}, then pay {amt_str} in full."
            }
            
    # 4. Fallback (Not Affordable)
    buffer_today = max(0.0, float(profile['current_available_balance']) - float(profile['minimum_balance_to_keep']))
    return {
        'request_id': req_id,
        'amount_safe_to_pay': round(buffer_today, 2),
        'affordability_status': 'not_affordable',
        'recommended_payment_method': 'not_recommended',
        'payment_plan': 'none',
        'earliest_date_for_full_payment': '',
        'spending_changes_needed': 'none',
        'decision_explanation': 'Do not make this payment. No safe option available.'
    }


import re


def apply_message_overrides(events_df, messages_df):
    events_mod = events_df.copy()
    
    sal_regexes = [
        r'(?:salary is reduced to|monthly pay is|salary will be|salary is|gaji pokok yang dikonfirmasi adalah)\s+(?:[A-Z]{3}\s+)?([\d,]+\.?\d*)',
        r'salary reduced to\s+(?:[A-Z]{3}\s+)?([\d,]+\.?\d*)'
    ]
    rent_regexes = [
        r'rent (?:increases|increased|will increase) by\s+(\d+)%'
    ]
    
    for _, msg in messages_df.iterrows():
        user_id = msg['user_id']
        text = str(msg['message_text'])
        
        for r in sal_regexes:
            match = re.search(r, text, re.IGNORECASE)
            if match:
                val_str = match.group(1).replace(',', '')
                try:
                    new_val = float(val_str)
                    mask = (events_mod['user_id'] == user_id) & (events_mod['category'] == 'salary')
                    if mask.any():
                        events_mod.loc[mask, 'amount'] = new_val
                except ValueError:
                    pass
                    
        for r in rent_regexes:
            match = re.search(r, text, re.IGNORECASE)
            if match:
                try:
                    pct = float(match.group(1))
                    mask = (events_mod['user_id'] == user_id) & (events_mod['category'] == 'rent')
                    if mask.any():
                        events_mod.loc[mask, 'amount'] = events_mod.loc[mask, 'amount'] * (1.0 + pct / 100.0)
                except ValueError:
                    pass
                    
    return events_mod


def main():
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'dataset/requests.csv'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.csv'
    
    requests_df = pd.read_csv(input_file)
    profiles_df = pd.read_csv('dataset/financial_profiles.csv')
    events_df = pd.read_csv('dataset/financial_events.csv')
    options_df = pd.read_csv('dataset/request_payment_options.csv')
    
    try:
        messages_df = pd.read_csv('dataset/messages.csv')
        events_df = apply_message_overrides(events_df, messages_df)
    except Exception as e:
        pass
    
    output_columns = [
        'request_id', 'amount_safe_to_pay', 'affordability_status',
        'recommended_payment_method', 'payment_plan',
        'earliest_date_for_full_payment', 'spending_changes_needed',
        'decision_explanation'
    ]
    
    rows = []
    for _, row in requests_df.iterrows():
        rows.append(process_request(row, profiles_df, events_df, options_df))
        
    output_df = pd.DataFrame(rows, columns=output_columns)
    output_df.to_csv(output_file, index=False)
    print(f"Successfully processed {len(output_df)} requests from {input_file} into {output_file}")


if __name__ == '__main__':
    main()