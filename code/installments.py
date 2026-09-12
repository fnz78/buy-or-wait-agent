import pandas as pd
from datetime import datetime, timedelta

"""
=== RECURRING CASHFLOW FORECAST & INSTALLMENT EVALUATION MODULE ===
"""

FIXED_RECURRING_CATEGORIES = {
    'salary', 'rent', 'housing', 'utilities', 'insurance', 'education',
    'healthcare', 'cloud_storage', 'streaming', 'subscription',
    'debt_repayment', 'gym', 'music_subscription', 'delivery_membership', 'family_support'
}


def get_projected_recurring_events(user_id, request_date, events_df, forecast_days=90):
    """
    Identifies fixed recurring income and commitment streams (salary, rent, utilities, tuition, etc.)
    appearing in >= 2 distinct historical months and projects them forward day-by-day for forecast_days.
    """
    end_date = request_date + timedelta(days=forecast_days)
    u_events = events_df[(events_df['user_id'] == user_id) & (events_df['status'] == 'settled')]
    
    # Filter for fixed recurring categories
    u_events_copy = u_events[u_events['category'].isin(FIXED_RECURRING_CATEGORIES)].copy()
    if u_events_copy.empty:
        return {}
        
    u_events_copy['month'] = u_events_copy['event_date'].str.slice(0, 7)
    
    recurring_descriptions = (
        u_events_copy.groupby('description')['month']
        .nunique()
        .loc[lambda x: x >= 2]
        .index.tolist()
    )
    
    projected = {}
    for desc in recurring_descriptions:
        desc_events = u_events_copy[u_events_copy['description'] == desc].sort_values('event_date', ascending=False)
        latest_event = desc_events.iloc[0]
        direction = str(latest_event['direction']).lower()
        if direction == 'credit':
            amount = float(desc_events['amount'].max()) if pd.notnull(desc_events['amount'].max()) else 0.0
        else:
            amount = float(latest_event['amount']) if pd.notnull(latest_event['amount']) else 0.0
        e_date = datetime.strptime(str(latest_event['event_date']), '%Y-%m-%d').date()
        net_change = amount if direction == 'credit' else -amount
        day_of_month = e_date.day
        
        for m_offset in range(1, 4):
            year = e_date.year + (e_date.month + m_offset - 1) // 12
            month = (e_date.month + m_offset - 1) % 12 + 1
            try:
                fut_date = datetime(year, month, day_of_month).date()
            except ValueError:
                fut_date = datetime(year, month, 28).date()
                
            if request_date <= fut_date <= end_date:
                key = (fut_date, desc)
                projected[key] = net_change

    daily_net = {}
    for (fut_date, _), net_change in projected.items():
        daily_net.setdefault(fut_date, 0.0)
        daily_net[fut_date] += net_change
        
    return daily_net


def forecast_installment_plan(user_id, request_date_str, initial_balance, min_balance, schedule, events_df):
    req_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
    end_date = req_date + timedelta(days=90)
    
    events_by_date = get_projected_recurring_events(user_id, req_date, events_df, 90)
    
    # Add scheduled/pending explicit events
    u_events = events_df[events_df['user_id'] == user_id]
    for _, event in u_events.iterrows():
        status = str(event['status']).lower()
        if status in ['cancelled']:
            continue
        if pd.notnull(event['event_date']):
            e_date = datetime.strptime(str(event['event_date']), '%Y-%m-%d').date()
            if req_date <= e_date <= end_date:
                amount = float(event['amount']) if pd.notnull(event['amount']) else 0.0
                direction = str(event['direction']).lower()
                net_change = amount if direction == 'credit' else -amount
                if status in ['scheduled', 'pending']:
                    events_by_date.setdefault(e_date, 0.0)
                    events_by_date[e_date] += net_change

    # Add installment payments
    for pay_date, pay_amt in schedule:
        if req_date <= pay_date <= end_date:
            events_by_date.setdefault(pay_date, 0.0)
            events_by_date[pay_date] -= pay_amt

    current_bal = initial_balance
    min_bal = current_bal
    
    curr_date = req_date
    while curr_date <= end_date:
        if curr_date in events_by_date:
            current_bal += events_by_date[curr_date]
        if current_bal < min_bal:
            min_bal = current_bal
        curr_date += timedelta(days=1)
        
    return min_bal


def generate_installment_schedule(option_row):
    num_payments = int(option_row['number_of_payments'])
    payment_amount = float(option_row['payment_amount'])
    start_date = datetime.strptime(str(option_row['first_payment_date']), '%Y-%m-%d').date()
    freq_days = float(option_row['payment_frequency_days']) if pd.notnull(option_row['payment_frequency_days']) else 30
    
    schedule = []
    for i in range(num_payments):
        pay_date = start_date + timedelta(days=int(i * freq_days))
        schedule.append((pay_date, payment_amount))
    return schedule


def evaluate_installments(request_row, profile_row, options_df, events_df, amount_safe=None):
    user_id = request_row['user_id']
    req_id = request_row['request_id']
    req_date_str = request_row['request_date']
    req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date()
    desired_completion_date = datetime.strptime(request_row['desired_completion_date'], '%Y-%m-%d').date()
    requested_amount = float(request_row['requested_amount'])
    
    avail_balance = float(profile_row['current_available_balance'])
    min_balance = float(profile_row['minimum_balance_to_keep'])
    
    user_methods = str(profile_row['payment_methods_user_will_consider']).split('|')
    max_months = float(profile_row['max_installment_months']) if pd.notnull(profile_row['max_installment_months']) else 0
    
    req_options = options_df[options_df['request_id'] == req_id]
    
    valid_plans = []
    
    for _, opt in req_options.iterrows():
        method = str(opt['payment_method'])
        num_payments = int(opt['number_of_payments'])
        opt_id = str(opt['payment_option_id'])
        total_payable = float(opt['total_payable_amount'])
        
        if method not in user_methods:
            continue
        if method == 'installments' and (max_months > 0 and num_payments > max_months):
            continue
            
        schedule = generate_installment_schedule(opt)
        first_date = schedule[0][0]
        final_payment_date = schedule[-1][0]
        
        if num_payments == 1 and first_date == req_date and abs(total_payable - requested_amount) < 0.01:
            if amount_safe is not None and requested_amount > amount_safe:
                continue
                
        if final_payment_date > desired_completion_date:
            continue
            
        min_proj = forecast_installment_plan(
            user_id, req_date_str, avail_balance, min_balance, schedule, events_df
        )
        
        if min_proj >= min_balance:
            total_payable = float(opt['total_payable_amount'])
            first_date = schedule[0][0]
            
            plan_str_parts = []
            for p_date, p_amt in schedule:
                p_amt_str = f"{p_amt:.2f}".rstrip('0').rstrip('.')
                plan_str_parts.append(f"{p_date}:{p_amt_str}")
            plan_str = "|".join(plan_str_parts)
            
            valid_plans.append({
                'option_id': opt_id,
                'method': method,
                'total_payable': total_payable,
                'first_date': first_date,
                'num_payments': num_payments,
                'payment_amount': float(opt['payment_amount']),
                'plan_str': plan_str,
                'min_proj': min_proj
            })
            
    if not valid_plans:
        return None
        
    valid_plans.sort(key=lambda x: (
        x['total_payable'],
        x['first_date'],
        x['num_payments'],
        x['option_id']
    ))
    
    return valid_plans[0]


def main():
    samples_df = pd.read_csv('dataset/sample_requests.csv')
    profiles_df = pd.read_csv('dataset/financial_profiles.csv')
    events_df = pd.read_csv('dataset/financial_events.csv')
    options_df = pd.read_csv('dataset/request_payment_options.csv')
    
    print("=== TESTING INSTALLMENT EVALUATION FOR REQUEST 02 (user_02) ===")
    req_02 = samples_df[samples_df['request_id'] == 'request_02'].iloc[0]
    prof_02 = profiles_df[profiles_df['user_id'] == 'user_02'].iloc[0]
    
    best_plan = evaluate_installments(req_02, prof_02, options_df, events_df)
    print("Best Installment Plan Found:")
    print(best_plan)


if __name__ == '__main__':
    main()
