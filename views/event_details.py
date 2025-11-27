import streamlit as st
import pandas as pd
import plotly.express as px
from utils import calculate_debts, format_currency, get_display_name, format_expense_display

def render_event_dashboard(current_event, data):
    """Render the main dashboard for an event."""
    st.title(current_event['name'])
    
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
        debts = calculate_debts(current_event['expenses'], current_event['members'])
        
        col1, col2 = st.columns(2)
        total_unsettled = unsettled_df['amount'].sum() if not unsettled_df.empty else 0
        col1.metric("Total Unsettled", format_currency(total_unsettled, current_event.get('currency', 'USD')))
        col2.metric("Pending Settlements", len(debts))
        
        if debts:
            st.subheader("⚠️ Who Owes Who")
            for debt in debts:
                debtor_name = get_display_name(debt['debtor'], data['users'])
                creditor_name = get_display_name(debt['creditor'], data['users'])
                st.info(f"**{debtor_name}** owes **{creditor_name}**: {format_currency(debt['amount'], current_event.get('currency', 'USD'))}")
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
        
        st.dataframe(
            display_df.sort_values(by='date', ascending=False)[['date', 'title', 'display_amount', 'payer', 'involved', 'settled']],
            column_config={
                "display_amount": st.column_config.TextColumn("Amount"),
                "date": "Date",
                "title": "Description",
                "payer": "Paid By",
                "involved": "Split Among",
                "settled": "Status"
            },
            use_container_width=True,
            hide_index=True
        )
