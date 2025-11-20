import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime
import random
import string
import hashlib
import gspread
from google.oauth2.service_account import Credentials

# --- Configuration & Styling ---
# --- Configuration & Styling ---
st.set_page_config(
    page_title="SplitSync",
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
# --- Data Management ---
DATA_FILE = "data.json"

# Google Sheets Configuration
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gsheet_client():
    try:
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=SCOPES
            )
            return gspread.authorize(creds)
        return None
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return None

def load_data():
    client = get_gsheet_client()
    
    # Fallback to local if no cloud connection
    if not client:
        if not os.path.exists(DATA_FILE):
            default_data = {"users": [], "events": []}
            save_local_data(default_data)
            return default_data
        with open(DATA_FILE, "r") as f:
            return json.load(f)

    try:
        # Open Spreadsheet (Assumes name 'SplitSync_DB' or uses URL from secrets)
        sheet_url = st.secrets.get("private_gsheets_url")
        if sheet_url:
            sh = client.open_by_url(sheet_url)
        else:
            sh = client.open("SplitSync_DB")

        # Load Users
        try:
            users_ws = sh.worksheet("Users")
            users = users_ws.get_all_records()
        except:
            users = []

        # Load Events
        try:
            events_ws = sh.worksheet("Events")
            events_raw = events_ws.get_all_records()
        except:
            events_raw = []

        # Load Expenses
        try:
            expenses_ws = sh.worksheet("Expenses")
            expenses_raw = expenses_ws.get_all_records()
        except:
            expenses_raw = []

        # Reconstruct Data Structure
        data = {"users": users, "events": []}
        
        # Map expenses to events
        expenses_by_event = {}
        for exp in expenses_raw:
            eid = exp['event_id']
            if eid not in expenses_by_event:
                expenses_by_event[eid] = []
            
            # Parse 'involved' back from string to list
            if isinstance(exp.get('involved'), str):
                try:
                    exp['involved'] = json.loads(exp['involved'])
                except:
                    exp['involved'] = []
            
            # Remove event_id from expense object to match internal schema
            del exp['event_id']
            expenses_by_event[eid].append(exp)

        for evt in events_raw:
            # Parse 'members' back from string
            if isinstance(evt.get('members'), str):
                try:
                    evt['members'] = json.loads(evt['members'])
                except:
                    evt['members'] = []
            
            evt['expenses'] = expenses_by_event.get(evt['id'], [])
            data['events'].append(evt)

        return data

    except Exception as e:
        st.error(f"Failed to load from Cloud: {e}. Using local backup.")
        if not os.path.exists(DATA_FILE):
            return {"users": [], "events": []}
        with open(DATA_FILE, "r") as f:
            return json.load(f)

def save_local_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def save_data(data):
    client = get_gsheet_client()
    
    # Always save local backup
    save_local_data(data)

    if not client:
        return

    try:
        sheet_url = st.secrets.get("private_gsheets_url")
        if sheet_url:
            sh = client.open_by_url(sheet_url)
        else:
            sh = client.open("SplitSync_DB")

        # Prepare Data for Sheets
        users_rows = data['users']
        
        events_rows = []
        expenses_rows = []
        
        for evt in data['events']:
            # Clone event to avoid modifying state
            evt_row = evt.copy()
            evt_row['members'] = json.dumps(evt_row['members']) # Serialize list
            del evt_row['expenses'] # Don't store nested expenses in event row
            events_rows.append(evt_row)
            
            for exp in evt['expenses']:
                exp_row = exp.copy()
                exp_row['event_id'] = evt['id']
                exp_row['involved'] = json.dumps(exp_row['involved']) # Serialize list
                expenses_rows.append(exp_row)

        # Update Users Sheet
        try:
            ws = sh.worksheet("Users")
            ws.clear()
        except:
            ws = sh.add_worksheet("Users", 1000, 10)
        
        if users_rows:
            ws.update(range_name='A1', values=[list(users_rows[0].keys())] + [list(r.values()) for r in users_rows])
        else:
            ws.update(range_name='A1', values=[["username", "password"]]) # Header only

        # Update Events Sheet
        try:
            ws = sh.worksheet("Events")
            ws.clear()
        except:
            ws = sh.add_worksheet("Events", 1000, 10)
            
        if events_rows:
            ws.update(range_name='A1', values=[list(events_rows[0].keys())] + [list(r.values()) for r in events_rows])
        else:
            ws.update(range_name='A1', values=[["id", "name", "members", "access_code"]])

        # Update Expenses Sheet
        try:
            ws = sh.worksheet("Expenses")
            ws.clear()
        except:
            ws = sh.add_worksheet("Expenses", 1000, 10)
            
        if expenses_rows:
            ws.update(range_name='A1', values=[list(expenses_rows[0].keys())] + [list(r.values()) for r in expenses_rows])
        else:
            ws.update(range_name='A1', values=[["id", "title", "amount", "payer", "involved", "date", "category", "settled", "event_id"]])

    except Exception as e:
        st.warning(f"Could not sync to Cloud: {e}")

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
        if payer in balances:
            balances[payer] += amount
        
        for person in involved:
            if person in balances:
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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Session State Initialization ---
if 'data' not in st.session_state:
    st.session_state.data = load_data()
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'current_event' not in st.session_state:
    st.session_state.current_event = None

data = st.session_state.data

# --- Login Screen ---
if not st.session_state.current_user:
    st.title("👋 Welcome to SplitSync")
    st.markdown("Please login to continue.")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            user_found = False
            for user in data.get('users', []):
                if user['username'] == username_input and user['password'] == hash_password(password_input):
                    st.session_state.current_user = user['username']
                    user_found = True
                    st.rerun()
                    break
            
            if not user_found:
                st.error("Invalid username or password.")
            
    st.divider()
    with st.expander("New User? Register here"):
        with st.form("register_form"):
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            if st.form_submit_button("Register"):
                if new_username and new_password:
                    if new_password != confirm_password:
                        st.error("Passwords do not match.")
                    elif any(u['username'] == new_username for u in data['users']):
                        st.warning("Username already exists.")
                    else:
                        new_user = {
                            "username": new_username,
                            "password": hash_password(new_password)
                        }
                        data['users'].append(new_user)
                        save_data(data)
                        st.session_state.data = data
                        st.success(f"User {new_username} registered! Please login.")
                else:
                    st.error("Please fill all fields.")

# --- Event Selection Screen ---
elif not st.session_state.current_event:
    st.sidebar.title(f"👤 {st.session_state.current_user}")
    if st.sidebar.button("Logout"):
        st.session_state.current_user = None
        st.rerun()
        
    st.title("Your Events")
    
    # Filter events where current user is a member
    my_events = [e for e in data.get('events', []) if st.session_state.current_user in e['members']]
    
    if my_events:
        for event in my_events:
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(event['name'])
                    st.caption(f"Members: {', '.join(event['members'])}")
                with c2:
                    if st.button("Open", key=f"open_{event['id']}"):
                        st.session_state.current_event = event
                        st.rerun()
                st.divider()
    else:
        st.info("You are not part of any events yet.")
        
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Create New Event")
        with st.form("new_event"):
            event_name = st.text_input("Event Name", placeholder="e.g. Japan Trip 2024")
            # Only add creator initially to protect user privacy
            # Other members can be added by code or manually by name
            members = [st.session_state.current_user]
            
            if st.form_submit_button("Create Event"):
                if event_name:
                    # Generate unique access code
                    access_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    
                    new_event = {
                        "id": f"event_{len(data['events']) + 1}",
                        "name": event_name,
                        "members": members,
                        "expenses": [],
                        "access_code": access_code
                    }
                    data['events'].append(new_event)
                    save_data(data)
                    st.session_state.data = data
                    st.success(f"Event created! Access Code: {access_code}")
                    st.rerun()
                else:
                    st.error("Please provide a name and select members.")

    with col2:
        st.markdown("### Join Event")
        with st.form("join_event"):
            code_input = st.text_input("Enter Access Code", placeholder="e.g. ABC123")
            if st.form_submit_button("Join"):
                found_event = None
                for event in data['events']:
                    if event.get('access_code') == code_input:
                        found_event = event
                        break
                
                if found_event:
                    if st.session_state.current_user not in found_event['members']:
                        found_event['members'].append(st.session_state.current_user)
                        save_data(data)
                        st.session_state.data = data
                        st.success(f"Joined {found_event['name']}!")
                        st.rerun()
                    else:
                        st.info("You are already a member of this event.")
                else:
                    st.error("Invalid Access Code.")

# --- Main Event Dashboard ---
else:
    # Get current event data (refresh from state)
    event_id = st.session_state.current_event['id']
    # Find the event in the data list to ensure we are editing the live object
    current_event_idx = next((i for i, e in enumerate(data['events']) if e['id'] == event_id), None)
    
    if current_event_idx is None:
        st.error("Event not found.")
        st.session_state.current_event = None
        st.rerun()
        
    current_event = data['events'][current_event_idx]
    
    # Sidebar
    with st.sidebar:
        st.title("💸 SplitSync")
        st.caption(f"Event: {current_event['name']}")
        st.caption(f"User: {st.session_state.current_user}")
        
        # Display Access Code
        code = current_event.get('access_code', 'N/A')
        st.info(f"🔑 Code: **{code}**")
        
        if st.button("⬅️ Back to Events"):
            st.session_state.current_event = None
            st.rerun()
            
        st.divider()
        menu = st.radio("Navigation", ["Dashboard", "Add Expense", "Settle Expenses", "Manage Event"])

    # Data Prep
    df = pd.DataFrame(current_event['expenses'])
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])

    # --- Dashboard ---
    if menu == "Dashboard":
        st.title(current_event['name'])
        
        unsettled_df = df[~df['settled']] if not df.empty and 'settled' in df.columns else df
        if 'settled' not in df.columns and not df.empty:
             df['settled'] = False
             unsettled_df = df

        if df.empty:
            st.info("No expenses recorded yet.")
        else:
            debts = calculate_debts(current_event['expenses'], current_event['members'])
            
            col1, col2 = st.columns(2)
            total_unsettled = unsettled_df['amount'].sum() if not unsettled_df.empty else 0
            col1.metric("Total Unsettled", f"${total_unsettled:,.2f}")
            col2.metric("Pending Settlements", len(debts))
            
            if debts:
                st.subheader("⚠️ Who Owes Who")
                for debt in debts:
                    st.info(f"**{debt['debtor']}** owes **{debt['creditor']}**: ${debt['amount']:.2f}")
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
            if 'involved' in display_df.columns:
                display_df['involved'] = display_df['involved'].apply(lambda x: ", ".join(x) if isinstance(x, list) else "All")
            
            st.dataframe(
                display_df.sort_values(by='date', ascending=False)[['date', 'title', 'amount', 'payer', 'involved', 'settled']],
                use_container_width=True,
                hide_index=True
            )

    # --- Add Expense ---
    elif menu == "Add Expense":
        st.title("Add Expense")
        with st.form("add_expense"):
            title = st.text_input("Description")
            amount = st.number_input("Amount", min_value=0.01)
            payer = st.selectbox("Paid By", current_event['members'], index=current_event['members'].index(st.session_state.current_user) if st.session_state.current_user in current_event['members'] else 0)
            category = st.selectbox("Category", ["Food", "Transport", "Accommodation", "Entertainment", "Utilities", "Other"])
            involved = st.multiselect("Split Among", current_event['members'], default=current_event['members'])
            date = st.date_input("Date", datetime.today())
            
            if st.form_submit_button("Save"):
                if title and involved:
                    new_expense = {
                        "id": len(current_event['expenses']) + 1,
                        "title": title,
                        "amount": amount,
                        "payer": payer,
                        "involved": involved,
                        "date": str(date),
                        "category": category,
                        "settled": False
                    }
                    current_event['expenses'].append(new_expense)
                    save_data(data)
                    st.session_state.data = data
                    st.success("Added!")
                    st.rerun()
                else:
                    st.error("Please fill all fields.")

    # --- Settle Expenses ---
    elif menu == "Settle Expenses":
        st.title("Settle Expenses")
        unsettled = [e for e in current_event['expenses'] if not e.get('settled', False)]
        
        if not unsettled:
            st.success("Nothing to settle.")
        else:
            unsettled_df = pd.DataFrame(unsettled)
            if 'involved' in unsettled_df.columns:
                unsettled_df['involved_display'] = unsettled_df['involved'].apply(lambda x: ", ".join(x) if isinstance(x, list) else "All")
            
            with st.form("settle"):
                edited = st.data_editor(
                    unsettled_df,
                    column_config={"settled": st.column_config.CheckboxColumn("Mark Settled", default=False)},
                    disabled=["id", "title", "amount", "payer", "involved_display"],
                    hide_index=True
                )
                
                if st.form_submit_button("Settle Selected"):
                    settled_ids = edited[edited['settled'] == True]['id'].tolist()
                    for exp in current_event['expenses']:
                        if exp['id'] in settled_ids:
                            exp['settled'] = True
                    save_data(data)
                    st.session_state.data = data
                    st.success("Settled!")
                    st.rerun()

    # --- Manage Event ---
    elif menu == "Manage Event":
        st.title("Manage Event")
        
        st.subheader("Add Member to Event")
        with st.form("add_member_form"):
            new_member_username = st.text_input("Enter Username to Add")
            if st.form_submit_button("Add Member"):
                # Check if user exists
                user_exists = any(u['username'] == new_member_username for u in data['users'])
                if not user_exists:
                    st.error("User not found.")
                elif new_member_username in current_event['members']:
                    st.warning("User already in event.")
                else:
                    current_event['members'].append(new_member_username)
                    save_data(data)
                    st.session_state.data = data
                    st.success(f"Added {new_member_username}!")
                    st.rerun()
            
        st.divider()
        st.subheader("Event Members")
        for m in current_event['members']:
            st.text(f"- {m}")
