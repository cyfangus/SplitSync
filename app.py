import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime

# --- Configuration & Styling ---
st.set_page_config(
    page_title="SplitPay",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a premium look
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        color: #1e293b;
    }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #3b82f6;
    }
    .metric-label {
        color: #64748b;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Data Management ---
DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        # Default initial data
        default_data = {
            "members": ["Alice", "Bob", "Charlie"],
            "expenses": []
        }
        save_data(default_data)
        return default_data
    
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
        # Schema Migration: Ensure all records have 'involved' and 'settled' fields
        updated = False
        for exp in data['expenses']:
            if 'settled' not in exp:
                exp['settled'] = False
                updated = True
            if 'involved' not in exp:
                exp['involved'] = data['members']
                updated = True
        
        if updated:
            save_data(data)
            
        return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def calculate_debts(expenses, members):
    # Calculate net balances
    balances = {m: 0.0 for m in members}
    for exp in expenses:
        if exp.get('settled', False):
            continue
            
        payer = exp['payer']
        amount = exp['amount']
        involved = exp.get('involved', members)
        
        if not involved: continue
        
        split_amount = amount / len(involved)
        
        # Payer gets credit (+), Involved get debit (-)
        # If payer is in involved, they pay themselves (net 0 change for that portion)
        balances[payer] += amount
        for person in involved:
            balances[person] -= split_amount
            
    # Simplify debts (Who owes whom)
    debtors = []
    creditors = []
    for person, amount in balances.items():
        if amount < -0.01: debtors.append([person, amount])
        if amount > 0.01: creditors.append([person, amount])
    
    debtors.sort(key=lambda x: x[1])
    creditors.sort(key=lambda x: x[1], reverse=True)
    
    transactions = []
    i = 0
    j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]
        
        amount = min(abs(debt), credit)
        transactions.append({"debtor": debtor, "creditor": creditor, "amount": amount})
        
        debtors[i][1] += amount
        creditors[j][1] -= amount
        
        if abs(debtors[i][1]) < 0.01: i += 1
        if creditors[j][1] < 0.01: j += 1
        
    return transactions

# Initialize Session State
if 'data' not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data
df = pd.DataFrame(data['expenses'])
if not df.empty:
    df['date'] = pd.to_datetime(df['date'])

# --- Sidebar ---
with st.sidebar:
    st.title("💸 SplitPay")
    st.markdown("Manage shared expenses easily.")
    
    menu = st.radio("Navigation", ["Dashboard", "Add Expense", "Settle Expenses", "Manage Members", "Data View"])
    
    st.divider()
    if st.button("Reset All Expenses", type="primary", use_container_width=True):
        data['expenses'] = []
        save_data(data)
        st.session_state.data = data
        st.rerun()

    st.divider()
    st.caption("Current Members")
    for member in data['members']:
        st.markdown(f"- {member}")

# --- Dashboard View ---
if menu == "Dashboard":
    st.title("Dashboard")
    
    # Filter for unsettled expenses for the dashboard metrics
    unsettled_df = df[~df['settled']] if not df.empty and 'settled' in df.columns else df
    if 'settled' not in df.columns and not df.empty:
         df['settled'] = False # Handle case where column might be missing in memory DF
         unsettled_df = df

    if df.empty:
        st.info("No expenses recorded yet. Go to 'Add Expense' to get started!")
    else:
        # Calculate Debts
        debts = calculate_debts(data['expenses'], data['members'])

        # Metrics
        total_unsettled = unsettled_df['amount'].sum() if not unsettled_df.empty else 0
        
        col1, col2 = st.columns(2)
        col1.metric("Total Unsettled Amount", f"${total_unsettled:,.2f}")
        col2.metric("Pending Settlements", len(debts))

        if debts:
            st.subheader("⚠️ Who Owes Who")
            for debt in debts:
                st.info(f"**{debt['debtor']}** owes **{debt['creditor']}**: ${debt['amount']:.2f}")
        else:
            st.success("### ✅ All settled up! No one owes anything.")

        st.markdown("---")

        # Charts Row 1
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("Unsettled Spending by Category")
            if not unsettled_df.empty:
                fig_pie = px.pie(unsettled_df, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No unsettled expenses.")

        with c2:
            st.subheader("Unsettled Spending by Member")
            if not unsettled_df.empty:
                member_spend = unsettled_df.groupby('payer')['amount'].sum().reset_index()
                fig_bar = px.bar(member_spend, x='payer', y='amount', color='payer', text_auto='.2s', color_discrete_sequence=px.colors.qualitative.Vivid)
                fig_bar.update_layout(xaxis_title=None, yaxis_title="Amount ($)", showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("No unsettled expenses.")

        # Recent Transactions
        st.subheader("Recent Transactions")
        
        # Prepare display dataframe
        display_df = df.copy()
        if 'involved' in display_df.columns:
            display_df['involved'] = display_df['involved'].apply(lambda x: ", ".join(x) if isinstance(x, list) else "All")
        else:
            display_df['involved'] = "All"
            
        if 'settled' not in display_df.columns:
            display_df['settled'] = False

        st.dataframe(
            display_df.sort_values(by='date', ascending=False)[['date', 'title', 'category', 'payer', 'involved', 'amount', 'settled']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                "date": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
                "involved": "Split With",
                "settled": st.column_config.CheckboxColumn("Settled", disabled=True)
            }
        )

# --- Add Expense View ---
elif menu == "Add Expense":
    st.title("Add New Expense")
    
    with st.form("add_expense_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Description", placeholder="e.g. Weekly Groceries")
            amount = st.number_input("Amount ($)", min_value=0.01, step=0.01)
        
        with col2:
            payer = st.selectbox("Paid By", data['members'])
            category = st.selectbox("Category", ["Food", "Utilities", "Rent", "Entertainment", "Transport", "Other"])
        
        involved = st.multiselect("Split Among", data['members'], default=data['members'])
            
        date = st.date_input("Date", datetime.today())
        
        submitted = st.form_submit_button("Save Expense", type="primary")
        
        if submitted:
            if not title:
                st.error("Please enter a description.")
            elif not involved:
                st.error("Please select at least one person to split with.")
            else:
                new_expense = {
                    "id": len(data['expenses']) + 1,
                    "title": title,
                    "amount": amount,
                    "payer": payer,
                    "involved": involved,
                    "date": str(date),
                    "category": category,
                    "settled": False
                }
                data['expenses'].append(new_expense)
                save_data(data)
                st.session_state.data = data # Update session state
                st.success("Expense added successfully!")
                st.rerun()

# --- Settle Expenses View ---
elif menu == "Settle Expenses":
    st.title("Settle Expenses")
    
    # Filter only unsettled expenses
    unsettled_expenses = [e for e in data['expenses'] if not e.get('settled', False)]
    
    if not unsettled_expenses:
        st.success("No unsettled expenses! You are all caught up.")
    else:
        st.markdown("Select expenses to mark as settled.")
        
        # Create a DataFrame for the data editor
        unsettled_df = pd.DataFrame(unsettled_expenses)
        
        # Handle 'involved' column for display
        if 'involved' in unsettled_df.columns:
             unsettled_df['involved_display'] = unsettled_df['involved'].apply(lambda x: ", ".join(x) if isinstance(x, list) else "All")
        else:
             unsettled_df['involved_display'] = "All"

        # We use a form to batch process
        with st.form("settle_form"):
            # Use checkboxes for selection. 
            # Since st.data_editor is editable, we can use that.
            
            edited_df = st.data_editor(
                unsettled_df,
                column_config={
                    "settled": st.column_config.CheckboxColumn("Mark Settled", default=False),
                    "id": st.column_config.TextColumn("ID", disabled=True),
                    "title": st.column_config.TextColumn("Title", disabled=True),
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f", disabled=True),
                    "payer": st.column_config.TextColumn("Payer", disabled=True),
                    "involved_display": st.column_config.TextColumn("Split With", disabled=True),
                    "date": st.column_config.DateColumn("Date", disabled=True),
                    "involved": None, # Hide the raw list
                    "category": None # Hide category to save space
                },
                disabled=["id", "title", "amount", "payer", "involved_display", "date"],
                hide_index=True,
                key="settle_editor"
            )
            
            settle_btn = st.form_submit_button("Mark Selected as Settled")
            
            if settle_btn:
                # Find which rows have 'settled' = True in the edited DF
                # Note: The original 'settled' was False. If the user checked it, it became True.
                
                # We need to map back to the original data.
                # The edited_df has the same index as unsettled_df if we didn't sort/filter inside the editor too much,
                # but safer to use IDs.
                
                settled_ids = edited_df[edited_df['settled'] == True]['id'].tolist()
                
                if settled_ids:
                    count = 0
                    for exp in data['expenses']:
                        if exp['id'] in settled_ids:
                            exp['settled'] = True
                            count += 1
                    
                    save_data(data)
                    st.session_state.data = data
                    st.success(f"Successfully settled {count} expenses!")
                    st.rerun()
                else:
                    st.info("No expenses selected.")

# --- Manage Members View ---
elif menu == "Manage Members":
    st.title("Manage Members")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Add Member")
        with st.form("add_member"):
            new_member = st.text_input("Name")
            add_submit = st.form_submit_button("Add")
            if add_submit and new_member:
                if new_member not in data['members']:
                    data['members'].append(new_member)
                    save_data(data)
                    st.session_state.data = data
                    st.success(f"Added {new_member}!")
                    st.rerun()
                else:
                    st.warning("Member already exists.")

    with col2:
        st.subheader("Remove Member")
        member_to_remove = st.selectbox("Select Member", data['members'])
        if st.button("Remove"):
            if len(data['members']) > 1:
                data['members'].remove(member_to_remove)
                save_data(data)
                st.session_state.data = data
                st.success(f"Removed {member_to_remove}.")
                st.rerun()
            else:
                st.error("Cannot remove the last member.")

# --- Data View ---
elif menu == "Data View":
    st.title("Raw Data")
    st.json(data)
