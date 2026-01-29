import streamlit as st
import pandas as pd
import plotly.express as px
from utils import calculate_debts, format_currency, get_display_name, format_expense_display

def render_event_dashboard(current_event, data):
    """Render the main dashboard for an event."""
    st.title(current_event['name'])
    
    # Show demo banner if this is the demo event
    if current_event.get('id') == 'demo_event_001':
        st.info("""
        🎯 **Demo Mode**: This is a sample event with demo data. Feel free to explore all features!
        
        You can:
        - Add/edit/delete expenses
        - Record payments
        - View analytics
        - Try the AI chatbot
        
        💡 When you're ready, create your own event from the dashboard!
        """)
        st.divider()
    
    # Data Prep
    df = pd.DataFrame(current_event['expenses'])
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
    
    # Ensure 'settled' column exists and is boolean
    if not df.empty:
        if 'settled' not in df.columns:
            df['settled'] = False
        # Convert to boolean if needed
        df['settled'] = df['settled'].astype(bool)
        unsettled_df = df[df['settled'] == False]
    else:
        unsettled_df = df

    if df.empty:
        # Empty state with helpful guidance
        st.info("📝 **No expenses yet!** Get started by adding your first expense.")
        st.markdown("""
        ### Quick Start Guide:
        1. Click **"➕ Add Expense"** in the sidebar
        2. Enter the expense details (description, amount, who paid)
        3. Select who should split the cost
        4. Save and you're done!
        
        💡 **Tip:** You can add expenses in different currencies and we'll convert them automatically!
        """)
    else:
        # Use all participants (users + custom names) for debt calculation
        all_participants = current_event.get('all_participants', current_event['members'])
        debts = calculate_debts(current_event['expenses'], all_participants, current_event.get('settlements', []))
        
        col1, col2 = st.columns(2)
        total_outstanding = sum(d['amount'] for d in debts)
        col1.metric("Total Outstanding", format_currency(total_outstanding, current_event.get('currency', 'USD')))
        col2.metric("Pending Settlements", len(debts))
        
        if debts:
            st.subheader("⚠️ Who Owes Who")
            for debt in debts:
                debtor_name = get_display_name(debt['debtor'], data['users'])
                creditor_name = get_display_name(debt['creditor'], data['users'])
                
                st.markdown(f"""
                <div style="
                    background-color: #a6232f; 
                    padding: 0.8rem; 
                    border-radius: 8px; 
                    margin-bottom: 0.5rem; 
                    border-left: 4px solid #ffc107;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                ">
                    <span><strong>{debtor_name}</strong> owes <strong>{creditor_name}</strong></span>
                    <span style="font-weight: bold;">{format_currency(debt['amount'], current_event.get('currency', 'USD'))}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ All settled up!")
            
        st.divider()
        
        # Charts
        c1, c2 = st.columns(2)
        with c1:
            if not unsettled_df.empty:
                fig_pie = px.pie(unsettled_df, values='amount', names='category', hole=0.4, title="Spending by Category")
                st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            if not unsettled_df.empty:
                member_spend = unsettled_df.groupby('payer')['amount'].sum().reset_index()
                fig_bar = px.bar(member_spend, x='payer', y='amount', color='payer', title="Spending by Member")
                st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("Recent Transactions")
        display_df = df.copy()
        # Map payer to display name
        display_df['payer'] = display_df['payer'].apply(lambda x: get_display_name(x, data['users']))
        
        if 'involved' in display_df.columns:
            display_df['involved'] = display_df['involved'].apply(
                lambda x: ", ".join([get_display_name(u, data['users']) for u in x]) if isinstance(x, list) else "All"
            )
        
        # Add formatted amount column
        display_df['display_amount'] = display_df.apply(lambda x: format_expense_display(x, current_event.get('currency', 'USD')), axis=1)
        
        # Mobile-friendly transaction list
        st.markdown("### 📝 Transactions")
        
        sorted_df = display_df.sort_values(by='date', ascending=False)
        
        for _, row in sorted_df.iterrows():
            status_color = "#28a745" if row['settled'] else "#ffc107"
            status_text = "Settled" if row['settled'] else "Pending"
            
            # Get category (with default if missing)
            category = row.get('category', '💰 Other')
            
            # Format created_at timestamp if available
            created_at_display = ""
            if 'created_at' in row and pd.notna(row['created_at']):
                try:
                    created_dt = pd.to_datetime(row['created_at'])
                    created_at_display = f"🕒 Recorded: {created_dt.strftime('%b %d, %Y %I:%M %p')}"
                except:
                    created_at_display = ""
            
            # Format transaction date
            try:
                trans_date = pd.to_datetime(row['date']).strftime('%b %d, %Y')
            except:
                trans_date = str(row['date'])
            
            st.markdown(f"""
            <div style="
                background-color: white;
                padding: 1rem;
                border-radius: 10px;
                margin-bottom: 0.8rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border: 1px solid #e9ecef;
            ">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.5rem;">
                    <div style="flex: 1;">
                        <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 0.3rem;">{row['title']}</div>
                        <div style="font-size: 0.85em; color: #666;">{category}</div>
                    </div>
                    <span style="font-weight: bold; font-size: 1.2em; color: #2c3e50;">{row['display_amount']}</span>
                </div>
                <div style="font-size: 0.9em; color: #666; margin-bottom: 0.3rem;">
                    📅 Transaction Date: {trans_date}
                </div>
                <div style="font-size: 0.85em; color: #888; margin-bottom: 0.5rem;">
                    {created_at_display}
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.9em; color: #666;">
                    <span>👤 Paid by {row['payer']}</span>
                </div>
                <div style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid #f0f0f0; font-size: 0.85em; display: flex; justify-content: space-between;">
                    <span style="color: #888;">Split: {row['involved']}</span>
                    <span style="color: {status_color}; font-weight: 600;">{status_text}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

