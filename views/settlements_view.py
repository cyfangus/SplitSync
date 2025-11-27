import streamlit as st
import pandas as pd
from datetime import datetime
from utils import calculate_debts, format_currency, send_email, get_exchange_rate
from database import add_settlement

def render_settle_expenses(current_event, data):
    """Render the Settle Expenses page."""
    st.title("Record Payment")
    
    # Initialize settlements list if not exists
    if 'settlements' not in current_event:
        current_event['settlements'] = []
    
    # Calculate current debts
    debts = calculate_debts(current_event['expenses'], current_event['members'])
    
    # Apply existing settlements to reduce debts
    for settlement in current_event.get('settlements', []):
        # Find and reduce the corresponding debt
        for debt in debts:
            if (debt['debtor'] == settlement['from_user'] and 
                debt['creditor'] == settlement['to_user']):
                debt['amount'] -= settlement['amount']
                if debt['amount'] <= 0:
                    debts.remove(debt)
                break
    
    # Remove zero or negative debts
    debts = [d for d in debts if d['amount'] > 0.01]
    
    # Display current outstanding debts
    st.subheader("💰 Outstanding Balances")
    
    if not debts:
        st.success("✅ All settled up! No outstanding payments.")
        st.markdown("""
        ### 🎉 Great job!
        Everyone in this event is square. When new expenses are added, any outstanding balances will appear here.
        
        💡 **Tip:** You can view payment history at the bottom of this page.
        """)
    else:
        st.info("The following payments are pending:")
        for debt in debts:
            st.write(f"• **{debt['debtor']}** owes **{debt['creditor']}**: {format_currency(debt['amount'], current_event.get('currency', 'USD'))}")
    
    
    st.divider()
    
    # Payment Reminder Feature
    st.subheader("📧 Send Payment Reminder")
    
    # Helper function to check if current user is admin
    def is_admin():
        roles = current_event.get('roles', {})
        return roles.get(st.session_state.current_user) == 'admin'

    # Check permissions
    user_is_admin = is_admin()
    
    # Find who owes the current user money
    current_user_credits = [d for d in debts if d['creditor'] == st.session_state.current_user]
    
    # Admins can send reminders for any debt
    if user_is_admin:
        available_debts = debts
        if not available_debts:
            st.info("💡 No outstanding debts in this event.")
        else:
            st.caption("👑 Admin Mode: You can send reminders for any outstanding debt.")
    else:
        available_debts = current_user_credits
        if not available_debts:
            st.info("💡 No one owes you money in this event.")
    
    if available_debts:
        if not user_is_admin:
            st.write("You can send a friendly reminder to people who owe you money:")
        
        # Initialize session state for reminder
        if 'reminder_sent' not in st.session_state:
            st.session_state.reminder_sent = False
        
        if st.session_state.reminder_sent:
            st.success("✅ Reminder email sent successfully!")
            st.session_state.reminder_sent = False
        
        with st.expander("💌 Send Reminder Email", expanded=False):
            # Select which debt to remind about
            debt_options = {}
            for debt in available_debts:
                debtor_name = debt['debtor']
                creditor_name = debt['creditor']
                amount = debt['amount']
                if user_is_admin:
                    # Show both parties for admin
                    debt_key = f"{debtor_name}→{creditor_name}"
                    debt_options[debt_key] = f"{debtor_name} owes {creditor_name}: {format_currency(amount, current_event.get('currency', 'USD'))}"
                else:
                    # Show only debtor for regular users
                    debt_key = debtor_name
                    debt_options[debt_key] = f"{debtor_name} owes you {format_currency(amount, current_event.get('currency', 'USD'))}"
            
            selected_debt_key = st.selectbox(
                "Send reminder about:",
                options=list(debt_options.keys()),
                format_func=lambda x: debt_options[x]
            )
            
            # Find the selected debt
            if user_is_admin:
                debtor_name, creditor_name = selected_debt_key.split('→')
                selected_debt = next((d for d in available_debts if d['debtor'] == debtor_name and d['creditor'] == creditor_name), None)
            else:
                selected_debt = next((d for d in available_debts if d['debtor'] == selected_debt_key), None)
            
            if selected_debt:
                debtor_name = selected_debt['debtor']
                creditor_name = selected_debt['creditor']
                
                # Get debtor's email
                debtor_user = next((u for u in data['users'] if u['username'] == debtor_name), None)
                
                if debtor_user and debtor_user.get('email'):
                    st.info(f"📧 Will send to: {debtor_user['email']}")
                    
                    # Default message (different for admin vs regular user)
                    if user_is_admin:
                        default_message = f"""Hi {debtor_name},

This is a reminder about the outstanding balance in the "{current_event['name']}" event.

You owe {creditor_name}: {format_currency(selected_debt['amount'], current_event.get('currency', 'USD'))}

Please settle this at your earliest convenience. You can record the payment in the app once done.

Best regards,
{st.session_state.current_user} (Event Admin)"""
                    else:
                        default_message = f"""Hi {debtor_name},

This is a friendly reminder about the outstanding balance in our "{current_event['name']}" event.

Amount owed: {format_currency(selected_debt['amount'], current_event.get('currency', 'USD'))}

Please settle this at your earliest convenience. You can record the payment in the app once done.

Thanks!
{st.session_state.current_user}"""
                    
                    # Custom message input
                    custom_message = st.text_area(
                        "Customize your message:",
                        value=default_message,
                        height=200,
                        help="Edit the message above to personalize your reminder"
                    )
                    
                    # Preview
                    with st.expander("📄 Email Preview", expanded=False):
                        st.markdown("**Subject:** Payment Reminder - " + current_event['name'])
                        st.markdown("**To:** " + debtor_user['email'])
                        st.markdown("---")
                        st.text(custom_message)
                    
                    # Send button
                    if st.button("📤 Send Reminder Email", type="primary"):
                        with st.spinner("📧 Sending reminder..."):
                            subject = f"Payment Reminder - {current_event['name']}"
                            if send_email(debtor_user['email'], subject, custom_message):
                                st.session_state.reminder_sent = True
                                st.rerun()
                            else:
                                st.error("Failed to send email. Please check your email configuration.")
                else:
                    st.warning(f"⚠️ {debtor_name} doesn't have an email address registered.")
                    st.caption("Ask them to add their email in Account Settings.")
    
    st.divider()
    
    # Payment recording form
    st.subheader("💸 Record a Payment")
    
    payer = st.session_state.current_user
    if is_admin():
        st.caption("👑 Admin Mode: You can record payments for any member.")
        payer = st.selectbox("From (Payer):", current_event['members'], index=current_event['members'].index(payer))
    else:
        st.caption("Use this to record when you've paid someone back.")
    
    # Find debts where selected payer is the debtor
    payer_debts = [d for d in debts if d['debtor'] == payer]
    
    # Initialize session state for payment success
    if 'payment_recorded' not in st.session_state:
        st.session_state.payment_recorded = False
    
    if st.session_state.payment_recorded:
        st.success("✅ Payment recorded successfully!")
        st.session_state.payment_recorded = False
    
    with st.form("record_payment"):
        # Select recipient (exclude payer)
        possible_recipients = [m for m in current_event['members'] if m != payer]
        
        if not possible_recipients:
            st.warning("No other members in this event to pay.")
            st.form_submit_button("Record Payment", disabled=True)
        else:
            # Determine default recipient and amount based on debts
            default_index = 0
            default_amount = 0.01
            suggested_debt = None
            
            if payer_debts:
                try:
                    default_recipient_name = payer_debts[0]['creditor']
                    default_index = possible_recipients.index(default_recipient_name)
                    suggested_debt = payer_debts[0]
                    default_amount = suggested_debt['amount']
                except ValueError:
                    default_index = 0
            
            recipient = st.selectbox(
                "To (Recipient):",
                possible_recipients,
                index=default_index
            )
            
            if suggested_debt and recipient == suggested_debt['creditor']:
                    st.info(f"💡 {payer} owes {recipient}: {format_currency(suggested_debt['amount'], current_event.get('currency', 'USD'))}")
            
            amount = st.number_input(
                "Amount paid:",
                min_value=0.01,
                value=float(default_amount),
                step=0.01
            )
            
            # Currency conversion option
            st.divider()
            st.caption("💱 Currency Conversion (Optional)")
            
            event_currency = current_event.get('currency', 'USD')
            
            currencies = {
                "USD": "$ (US Dollar)", "EUR": "€ (Euro)", "GBP": "£ (British Pound)",
                "JPY": "¥ (Japanese Yen)", "CNY": "¥ (Chinese Yuan)", "AUD": "A$ (Australian Dollar)",
                "CAD": "C$ (Canadian Dollar)", "CHF": "Fr (Swiss Franc)", "HKD": "HK$ (Hong Kong Dollar)",
                "SGD": "S$ (Singapore Dollar)", "KRW": "₩ (South Korean Won)", "INR": "₹ (Indian Rupee)",
                "MXN": "Mex$ (Mexican Peso)", "BRL": "R$ (Brazilian Real)", "ZAR": "R (South African Rand)",
                "NZD": "NZ$ (New Zealand Dollar)", "THB": "฿ (Thai Baht)", "MYR": "RM (Malaysian Ringgit)",
                "PHP": "₱ (Philippine Peso)", "IDR": "Rp (Indonesian Rupiah)", "VND": "₫ (Vietnamese Dong)"
            }
            
            use_different_currency = st.checkbox(
                f"I paid in a different currency (Event uses {currencies.get(event_currency, event_currency)})"
            )
            
            payment_currency = event_currency
            converted_amount = amount
            exchange_rate = 1.0
            
            if use_different_currency:
                payment_currency = st.selectbox(
                    "Payment Currency:",
                    options=list(currencies.keys()),
                    format_func=lambda x: currencies[x],
                    index=0
                )
                
                if payment_currency != event_currency:
                    # Fetch exchange rate
                    exchange_rate = get_exchange_rate(payment_currency, event_currency)
                    
                    if exchange_rate:
                        converted_amount = amount * exchange_rate
                        st.success(
                            f"✓ Exchange Rate: 1 {payment_currency} = {exchange_rate:.4f} {event_currency}\n\n"
                            f"{format_currency(amount, payment_currency)} = {format_currency(converted_amount, event_currency)}"
                        )
                    else:
                        st.error("Could not fetch exchange rate. Please try again or use event currency.")
                        use_different_currency = False
            
            st.divider()
            
            payment_date = st.date_input("Payment Date", datetime.today())
            notes = st.text_input("Notes (optional)", placeholder="e.g., Cash payment")
            
            submitted = st.form_submit_button("💾 Record Payment", type="primary")
            
            if submitted:
                with st.spinner("💳 Recording payment..."):
                    # Create settlement record
                    settlement_data = {
                        "payer": payer,
                        "recipient": recipient,
                        "amount": amount,
                        "payment_currency": payment_currency,
                        "converted_amount": converted_amount,
                        "exchange_rate": exchange_rate,
                        "date": str(payment_date),
                        "notes": notes
                    }
                    
                    if add_settlement(current_event['id'], settlement_data):
                        st.session_state.payment_recorded = True
                        st.rerun()
                    else:
                        st.error("Failed to save settlement.")
    
    # Display payment history
    if current_event.get('settlements'):
        st.divider()
        st.subheader("📜 Payment History")
        
        settlements_df = pd.DataFrame(current_event['settlements'])
        settlements_df = settlements_df.sort_values('date', ascending=False)
        
        # Format for display with currency conversion info
        for idx, settlement in enumerate(current_event['settlements'][::-1]):  # Reverse to match sorted order
            with st.expander(
                f"{settlement['date']} - {settlement['from_user']} → {settlement['to_user']}: {format_currency(settlement['amount'], current_event.get('currency', 'USD'))}"
            ):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**From:** {settlement['from_user']}")
                    st.write(f"**To:** {settlement['to_user']}")
                    st.write(f"**Date:** {settlement['date']}")
                with col2:
                    st.write(f"**Amount:** {format_currency(settlement['amount'], current_event.get('currency', 'USD'))}")
                    
                    # Show conversion info if available
                    if settlement.get('original_currency') and settlement.get('original_amount'):
                        st.write(f"**Original:** {format_currency(settlement['original_amount'], settlement['original_currency'])}")
                        st.write(f"**Rate:** 1 {settlement['original_currency']} = {settlement.get('exchange_rate', 0):.4f} {current_event.get('currency', 'USD')}")
                    
                    if settlement.get('notes'):
                        st.write(f"**Notes:** {settlement['notes']}")
