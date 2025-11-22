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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from PIL import Image
import base64
import io

# --- Configuration & Styling ---
st.set_page_config(
    page_title="SplitSync",
    page_icon="💸",
    layout="wide",
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

def send_email(to_email, subject, body):
    if "email" not in st.secrets:
        st.error("Email configuration missing in secrets.")
        return False
    
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port = st.secrets["email"]["smtp_port"]
    sender_email = st.secrets["email"]["sender_email"]
    sender_password = st.secrets["email"]["sender_password"]

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

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
            
            # Ensure 'settled' is boolean
            settled_val = exp.get('settled', False)
            if isinstance(settled_val, str):
                exp['settled'] = settled_val.upper() == 'TRUE'
            else:
                exp['settled'] = bool(settled_val)
            
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
            
            # Parse 'roles' back from string to dict
            if isinstance(evt.get('roles'), str):
                try:
                    evt['roles'] = json.loads(evt['roles'])
                except:
                    evt['roles'] = {}
            elif 'roles' not in evt:
                evt['roles'] = {}
            
            # Parse 'settlements' back from string to list
            if isinstance(evt.get('settlements'), str):
                try:
                    evt['settlements'] = json.loads(evt['settlements'])
                except:
                    evt['settlements'] = []
            elif 'settlements' not in evt:
                evt['settlements'] = []
            
            # Ensure currency field exists
            if 'currency' not in evt:
                evt['currency'] = 'USD'
            
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

def update_username_references(data, old_username, new_username):
    """Updates username references across all events, expenses, and settlements."""
    for event in data['events']:
        # Update members list
        if old_username in event['members']:
            event['members'] = [new_username if m == old_username else m for m in event['members']]
        
        # Update roles
        if old_username in event.get('roles', {}):
            event['roles'][new_username] = event['roles'].pop(old_username)
            
        # Update expenses
        for exp in event['expenses']:
            if exp['payer'] == old_username:
                exp['payer'] = new_username
            if 'involved' in exp:
                if isinstance(exp['involved'], list):
                    exp['involved'] = [new_username if m == old_username else m for m in exp['involved']]
        
        # Update settlements
        for sett in event.get('settlements', []):
            if sett['from_user'] == old_username:
                sett['from_user'] = new_username
            if sett['to_user'] == old_username:
                sett['to_user'] = new_username
    return data

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
            evt_row['roles'] = json.dumps(evt_row.get('roles', {})) # Serialize roles dict
            evt_row['settlements'] = json.dumps(evt_row.get('settlements', [])) # Serialize settlements list
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
            ws.update(range_name='A1', values=[["username", "password", "email"]]) # Header only

        # Update Events Sheet
        try:
            ws = sh.worksheet("Events")
            ws.clear()
        except:
            ws = sh.add_worksheet("Events", 1000, 10)
            
        if events_rows:
            ws.update(range_name='A1', values=[list(events_rows[0].keys())] + [list(r.values()) for r in events_rows])
        else:
            ws.update(range_name='A1', values=[["id", "name", "members", "roles", "currency", "access_code", "settlements"]])

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
if 'reg_step' not in st.session_state:
    st.session_state.reg_step = 1
if 'reg_code' not in st.session_state:
    st.session_state.reg_code = None
if 'reg_data' not in st.session_state:
    st.session_state.reg_data = {}
if 'reset_step' not in st.session_state:
    st.session_state.reset_step = 1
if 'reset_code' not in st.session_state:
    st.session_state.reset_code = None
if 'reset_email' not in st.session_state:
    st.session_state.reset_email = None

data = st.session_state.data

# --- Login Screen ---
if not st.session_state.current_user:
    st.title("👋 Welcome to SplitSync")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])
    
    with tab1:
        st.markdown("Please login to continue.")
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

    with tab2:
        st.markdown("Create a new account.")
        if st.session_state.reg_step == 1:
            with st.form("reg_form_1"):
                new_username = st.text_input("Choose Username")
                new_email = st.text_input("Email Address")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                if st.form_submit_button("Next: Verify Email"):
                    if new_username and new_email and new_password:
                        if new_password != confirm_password:
                            st.error("Passwords do not match.")
                        elif any(u['username'] == new_username for u in data['users']):
                            st.warning("Username already exists.")
                        elif any(u.get('email') == new_email for u in data['users']):
                            st.warning("Email already registered.")
                        else:
                            # Generate Code
                            code = ''.join(random.choices(string.digits, k=6))
                            if send_email(new_email, "SplitSync Verification Code", f"Your code is: {code}"):
                                st.session_state.reg_code = code
                                st.session_state.reg_data = {
                                    "username": new_username,
                                    "email": new_email,
                                    "password": hash_password(new_password)
                                }
                                st.session_state.reg_step = 2
                                st.rerun()
                            else:
                                st.error("Failed to send email. Check configuration.")
                    else:
                        st.error("Please fill all fields.")
        
        elif st.session_state.reg_step == 2:
            st.info(f"Verification code sent to {st.session_state.reg_data.get('email')}")
            code_input = st.text_input("Enter Verification Code")
            if st.button("Verify & Register"):
                if code_input == st.session_state.reg_code:
                    data['users'].append(st.session_state.reg_data)
                    save_data(data)
                    st.session_state.data = data
                    st.success(f"User {st.session_state.reg_data['username']} registered! Please login.")
                    # Reset state
                    st.session_state.reg_step = 1
                    st.session_state.reg_code = None
                    st.session_state.reg_data = {}
                else:
                    st.error("Invalid code.")
            if st.button("Back"):
                st.session_state.reg_step = 1
                st.rerun()

    with tab3:
        st.markdown("Reset your password.")
        if st.session_state.reset_step == 1:
            reset_email = st.text_input("Enter your registered email")
            if st.button("Send Reset Code"):
                user_exists = False
                for u in data['users']:
                    if u.get('email') == reset_email:
                        user_exists = True
                        break
                
                if user_exists:
                    code = ''.join(random.choices(string.digits, k=6))
                    if send_email(reset_email, "SplitSync Password Reset", f"Your reset code is: {code}"):
                        st.session_state.reset_code = code
                        st.session_state.reset_email = reset_email
                        st.session_state.reset_step = 2
                        st.rerun()
                    else:
                        st.error("Failed to send email.")
                else:
                    st.error("Email not found.")
        
        elif st.session_state.reset_step == 2:
            st.info(f"Reset code sent to {st.session_state.reset_email}")
            reset_code_input = st.text_input("Enter Reset Code")
            new_pass = st.text_input("New Password", type="password")
            
            if st.button("Reset Password"):
                if reset_code_input == st.session_state.reset_code:
                    # Update password
                    for u in data['users']:
                        if u.get('email') == st.session_state.reset_email:
                            u['password'] = hash_password(new_pass)
                            break
                    save_data(data)
                    st.session_state.data = data
                    st.success("Password reset successful! Please login.")
                    st.session_state.reset_step = 1
                    st.session_state.reset_code = None
                    st.session_state.reset_email = None
                else:
                    st.error("Invalid code.")
            if st.button("Cancel"):
                st.session_state.reset_step = 1
                st.rerun()

# --- Event Selection Screen ---
elif not st.session_state.current_event:
    # Get user data for avatar
    current_user_data = next((u for u in data['users'] if u['username'] == st.session_state.current_user), None)
    
    if current_user_data and current_user_data.get('avatar'):
        try:
            avatar_bytes = base64.b64decode(current_user_data['avatar'])
            st.sidebar.image(avatar_bytes, width=100)
            st.sidebar.markdown(f"### {st.session_state.current_user}")
        except:
             st.sidebar.title(f"👤 {st.session_state.current_user}")
    else:
        st.sidebar.title(f"👤 {st.session_state.current_user}")
    
    # Initialize settings state
    if 'show_settings' not in st.session_state:
        st.session_state.show_settings = False
    
    if st.sidebar.button("🏠 My Events"):
        st.session_state.show_settings = False
        st.rerun()

    if st.sidebar.button("⚙️ Account Settings"):
        st.session_state.show_settings = True
        st.rerun()
        
    if st.sidebar.button("Logout"):
        st.session_state.current_user = None
        st.session_state.show_settings = False
        st.rerun()
    
    if st.session_state.show_settings:
        st.title("⚙️ Account Settings")
        
        # Profile Picture Section
        st.subheader("Profile Picture")
        col_avatar, col_upload = st.columns([1, 3])
        
        current_user_data = next((u for u in data['users'] if u['username'] == st.session_state.current_user), None)
        
        with col_avatar:
            if current_user_data and current_user_data.get('avatar'):
                try:
                    st.image(base64.b64decode(current_user_data['avatar']), width=100, caption="Current")
                except:
                    st.error("Error loading avatar")
            else:
                st.info("No avatar set")
        
        with col_upload:
            uploaded_file = st.file_uploader("Upload new avatar", type=['png', 'jpg', 'jpeg'])
            if uploaded_file is not None:
                if st.button("Save Avatar", type="primary"):
                    try:
                        image = Image.open(uploaded_file)
                        # Resize to square 150x150
                        image = image.resize((150, 150))
                        # Convert to base64
                        buffered = io.BytesIO()
                        image.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        
                        # Save
                        user_idx = next((i for i, u in enumerate(data['users']) if u['username'] == st.session_state.current_user), -1)
                        if user_idx != -1:
                            data['users'][user_idx]['avatar'] = img_str
                            save_data(data)
                            st.success("✅ Avatar updated!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error processing image: {e}")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Change Password")
            with st.form("change_password"):
                current_pwd = st.text_input("Current Password", type="password")
                new_pwd = st.text_input("New Password", type="password")
                confirm_pwd = st.text_input("Confirm New Password", type="password")
                
                if st.form_submit_button("Update Password", type="primary"):
                    user_idx = next((i for i, u in enumerate(data['users']) if u['username'] == st.session_state.current_user), -1)
                    if user_idx != -1:
                        user = data['users'][user_idx]
                        if user['password'] == hash_password(current_pwd):
                            if new_pwd == confirm_pwd:
                                if len(new_pwd) >= 6:
                                    data['users'][user_idx]['password'] = hash_password(new_pwd)
                                    save_data(data)
                                    st.success("✅ Password updated successfully!")
                                else:
                                    st.error("Password must be at least 6 characters.")
                            else:
                                st.error("New passwords do not match.")
                        else:
                            st.error("Incorrect current password.")
        
        with col2:
            st.subheader("Change Username")
            st.warning("⚠️ Changing your username will update it across all past events and expenses.")
            with st.form("change_username"):
                new_username = st.text_input("New Username")
                
                if st.form_submit_button("Update Username", type="primary"):
                    if new_username and new_username != st.session_state.current_user:
                        if any(u['username'] == new_username for u in data['users']):
                            st.error("Username already taken.")
                        else:
                            user_idx = next((i for i, u in enumerate(data['users']) if u['username'] == st.session_state.current_user), -1)
                            if user_idx != -1:
                                old_user = st.session_state.current_user
                                data['users'][user_idx]['username'] = new_username
                                update_username_references(data, old_user, new_username)
                                st.session_state.current_user = new_username
                                save_data(data)
                                st.success("✅ Username updated successfully!")
                                st.rerun()
                    elif new_username == st.session_state.current_user:
                        st.info("New username is the same as current.")
                    else:
                        st.error("Please enter a valid username.")
        
        st.divider()
        st.subheader("🏦 Bank Details & Privacy")
        
        col_bank, col_requests = st.columns(2)
        
        current_user_idx = next((i for i, u in enumerate(data['users']) if u['username'] == st.session_state.current_user), -1)
        user = data['users'][current_user_idx]
        
        with col_bank:
            st.markdown("**My Bank Information**")
            st.caption("Shared only with approved users.")
            
            # Parse existing data
            current_data = {}
            try:
                current_data = json.loads(user.get('bank_details', '{}'))
            except:
                pass
            
            countries = ["GB", "US", "EU", "AU", "CN", "JP", "Other"]
            country_names = {
                "GB": "🇬🇧 United Kingdom", "US": "🇺🇸 United States", "EU": "🇪🇺 Europe (IBAN)",
                "AU": "🇦🇺 Australia", "CN": "🇨🇳 China", "JP": "🇯🇵 Japan", "Other": "🌍 Other"
            }
            
            saved_country = current_data.get('country', 'Other')
            try:
                default_idx = countries.index(saved_country)
            except:
                default_idx = 6
                
            selected_country = st.selectbox("Bank Country", countries, format_func=lambda x: country_names[x], index=default_idx)
            
            form_data = {}
            # Universal field
            form_data['account_holder_name'] = st.text_input("Account Holder Name", value=current_data.get('fields', {}).get('account_holder_name', ''))
            
            if selected_country == "GB":
                form_data['sort_code'] = st.text_input("Sort Code (6 digits)", value=current_data.get('fields', {}).get('sort_code', ''), placeholder="XX-XX-XX")
                form_data['account_number'] = st.text_input("Account Number (8 digits)", value=current_data.get('fields', {}).get('account_number', ''))
            elif selected_country == "US":
                form_data['routing_number'] = st.text_input("Routing Number (ABA)", value=current_data.get('fields', {}).get('routing_number', ''))
                form_data['account_number'] = st.text_input("Account Number", value=current_data.get('fields', {}).get('account_number', ''))
                form_data['account_type'] = st.selectbox("Account Type", ["Checking", "Savings"], index=0 if current_data.get('fields', {}).get('account_type') == "Checking" else 1)
            elif selected_country == "EU":
                form_data['iban'] = st.text_input("IBAN", value=current_data.get('fields', {}).get('iban', ''))
                form_data['bic'] = st.text_input("BIC / SWIFT (Optional)", value=current_data.get('fields', {}).get('bic', ''))
            elif selected_country == "AU":
                form_data['bsb'] = st.text_input("BSB (6 digits)", value=current_data.get('fields', {}).get('bsb', ''), placeholder="XXX-XXX")
                form_data['account_number'] = st.text_input("Account Number", value=current_data.get('fields', {}).get('account_number', ''))
                form_data['payid'] = st.text_input("PayID (Optional)", value=current_data.get('fields', {}).get('payid', ''))
            elif selected_country == "CN":
                form_data['bank_name'] = st.text_input("Bank Name", value=current_data.get('fields', {}).get('bank_name', ''))
                form_data['card_number'] = st.text_input("Card / Account Number", value=current_data.get('fields', {}).get('card_number', ''))
                form_data['branch_name'] = st.text_input("Branch Name (Sub-branch)", value=current_data.get('fields', {}).get('branch_name', ''))
            elif selected_country == "JP":
                form_data['bank_name'] = st.text_input("Bank Name", value=current_data.get('fields', {}).get('bank_name', ''))
                form_data['branch_name'] = st.text_input("Branch Name / Code", value=current_data.get('fields', {}).get('branch_name', ''))
                form_data['account_type'] = st.selectbox("Account Type", ["Ordinary (Futsu)", "Current (Toza)", "Savings (Chochiku)"], index=0)
                form_data['account_number'] = st.text_input("Account Number", value=current_data.get('fields', {}).get('account_number', ''))
            else:
                legacy_val = user.get('bank_details', '') if not current_data else current_data.get('fields', {}).get('details', '')
                form_data['details'] = st.text_area("Details", value=legacy_val, height=100)

            if st.button("Save Bank Details"):
                # Auto-format specific fields
                if selected_country == "GB":
                    # Sort Code: XX-XX-XX
                    sc = form_data.get('sort_code', '').replace('-', '').replace(' ', '')
                    if len(sc) == 6 and sc.isdigit():
                        form_data['sort_code'] = f"{sc[:2]}-{sc[2:4]}-{sc[4:]}"
                
                elif selected_country == "AU":
                    # BSB: XXX-XXX
                    bsb = form_data.get('bsb', '').replace('-', '').replace(' ', '')
                    if len(bsb) == 6 and bsb.isdigit():
                        form_data['bsb'] = f"{bsb[:3]}-{bsb[3:]}"

                save_struct = {
                    "country": selected_country,
                    "fields": form_data
                }
                user['bank_details'] = json.dumps(save_struct)
                save_data(data)
                st.success("Saved!")
                
        with col_requests:
            st.markdown("**Access Requests**")
            
            # Pending Requests
            requests = user.get('access_requests', [])
            if requests:
                st.info(f"You have {len(requests)} pending requests.")
                for req_user in requests:
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.write(req_user)
                    if c2.button("Approve", key=f"app_{req_user}"):
                        if 'approved_viewers' not in user: user['approved_viewers'] = []
                        user['approved_viewers'].append(req_user)
                        user['access_requests'].remove(req_user)
                        save_data(data)
                        st.rerun()
                    if c3.button("Reject", key=f"rej_{req_user}"):
                        user['access_requests'].remove(req_user)
                        save_data(data)
                        st.rerun()
            else:
                st.caption("No pending requests.")
                
            st.divider()
            st.markdown("**Approved Users**")
            approved = user.get('approved_viewers', [])
            if approved:
                for app_user in approved:
                    c1, c2 = st.columns([3, 1])
                    c1.write(app_user)
                    if c2.button("Revoke", key=f"rev_{app_user}"):
                        user['approved_viewers'].remove(app_user)
                        save_data(data)
                        st.rerun()
            else:
                st.caption("No users have access.")
                        
        if st.button("← Back to Events"):
            st.session_state.show_settings = False
            st.rerun()
            
        st.stop()

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
        # Initialize session state for create event
        if 'event_created' not in st.session_state:
            st.session_state.event_created = False
        
        if st.session_state.event_created:
            st.success("✅ Event created successfully!")
            st.session_state.event_created = False
        
        with st.form("new_event", clear_on_submit=True):
            event_name = st.text_input("Event Name", placeholder="e.g. Japan Trip 2024")
            
            # Currency selection
            currencies = {
                "USD": "$ (US Dollar)",
                "EUR": "€ (Euro)",
                "GBP": "£ (British Pound)",
                "JPY": "¥ (Japanese Yen)",
                "CNY": "¥ (Chinese Yuan)",
                "AUD": "A$ (Australian Dollar)",
                "CAD": "C$ (Canadian Dollar)",
                "CHF": "Fr (Swiss Franc)",
                "HKD": "HK$ (Hong Kong Dollar)",
                "SGD": "S$ (Singapore Dollar)",
                "KRW": "₩ (South Korean Won)",
                "INR": "₹ (Indian Rupee)",
                "MXN": "Mex$ (Mexican Peso)",
                "BRL": "R$ (Brazilian Real)",
                "ZAR": "R (South African Rand)",
                "NZD": "NZ$ (New Zealand Dollar)",
                "THB": "฿ (Thai Baht)",
                "MYR": "RM (Malaysian Ringgit)",
                "PHP": "₱ (Philippine Peso)",
                "IDR": "Rp (Indonesian Rupiah)",
                "VND": "₫ (Vietnamese Dong)"
            }
            
            selected_currency = st.selectbox(
                "Currency",
                options=list(currencies.keys()),
                format_func=lambda x: currencies[x],
                index=0
            )
            
            # Only add creator initially to protect user privacy
            # Other members can be added by code or manually by name
            members = [st.session_state.current_user]
            
            submitted = st.form_submit_button("Create Event", type="primary")
            
            if submitted:
                if event_name:
                    with st.spinner("Creating event..."):
                        # Generate unique access code
                        access_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        
                        new_event = {
                            "id": f"event_{len(data['events']) + 1}",
                            "name": event_name,
                            "members": members,
                            "roles": {st.session_state.current_user: "admin"},  # Creator is admin
                            "currency": selected_currency,
                            "expenses": [],
                            "access_code": access_code
                        }
                        data['events'].append(new_event)
                        save_data(data)
                        st.session_state.data = data
                        st.session_state.event_created = True
                        st.rerun()
                else:
                    st.error("Please provide an event name.")

    with col2:
        st.markdown("### Join Event")
        
        if 'event_joined' not in st.session_state:
            st.session_state.event_joined = False
        
        if st.session_state.event_joined:
            st.success("✅ Successfully joined event!")
            st.session_state.event_joined = False
        
        with st.form("join_event", clear_on_submit=True):
            code_input = st.text_input("Enter Access Code", placeholder="e.g. ABC123")
            submitted = st.form_submit_button("Join Event", type="primary")
            
            if submitted:
                if code_input:
                    with st.spinner("Joining event..."):
                        # Find event with matching code
                        matching_event = None
                        for evt in data['events']:
                            if evt.get('access_code') == code_input.upper():
                                matching_event = evt
                                break
                        
                        if matching_event:
                            if st.session_state.current_user not in matching_event['members']:
                                matching_event['members'].append(st.session_state.current_user)
                                # Ensure roles dict exists
                                if 'roles' not in matching_event:
                                    matching_event['roles'] = {}
                                # Assign member role
                                matching_event['roles'][st.session_state.current_user] = "member"
                                save_data(data)
                                st.session_state.data = data
                                st.session_state.event_joined = True
                                st.rerun()
                            else:
                                st.info("You are already a member of this event.")
                        else:
                            st.error("Invalid Access Code.")
                else:
                    st.error("Please enter an access code.")

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
    
    # Helper function to check if current user is admin
    def is_admin():
        roles = current_event.get('roles', {})
        return roles.get(st.session_state.current_user) == 'admin'
    
    # Currency symbols mapping
    CURRENCY_SYMBOLS = {
        "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
        "AUD": "A$", "CAD": "C$", "CHF": "Fr", "HKD": "HK$", "SGD": "S$",
        "KRW": "₩", "INR": "₹", "MXN": "Mex$", "BRL": "R$", "ZAR": "R",
        "NZD": "NZ$", "THB": "฿", "MYR": "RM", "PHP": "₱", "IDR": "Rp", "VND": "₫"
    }
    
    # Helper function to format currency
    def format_currency(amount, currency_override=None):
        currency_code = currency_override or current_event.get('currency', 'USD')
        symbol = CURRENCY_SYMBOLS.get(currency_code, '$')
        return f"{symbol}{amount:.2f}"

    # Helper function to format expense display (showing original currency if applicable)
    def format_expense_display(expense):
        base_amount = format_currency(expense['amount'])
        if expense.get('original_currency') and expense.get('original_amount'):
            event_curr = current_event.get('currency', 'USD')
            if expense['original_currency'] != event_curr:
                 orig_amount = format_currency(expense['original_amount'], expense['original_currency'])
                 return f"{base_amount} ({orig_amount})"
        return base_amount
    
    # Helper function to get exchange rate
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_exchange_rate(from_currency, to_currency):
        if from_currency == to_currency:
            return 1.0
        
        try:
            # Using exchangerate-api.com (free tier: 1500 requests/month)
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            response = requests.get(url, timeout=5)
            data = response.json()
            
            if 'rates' in data and to_currency in data['rates']:
                return data['rates'][to_currency]
            else:
                st.warning(f"Could not fetch exchange rate for {from_currency} to {to_currency}")
                return None
        except Exception as e:
            st.error(f"Error fetching exchange rate: {e}")
            return None
    
    # Sidebar
    with st.sidebar:
        st.title("💸 SplitSync")
        st.caption(f"Event: {current_event['name']}")
        
        # Display user and role
        user_role = current_event.get('roles', {}).get(st.session_state.current_user, 'member')
        role_emoji = "👑" if user_role == "admin" else "👤"
        st.caption(f"{role_emoji} {st.session_state.current_user} ({user_role.title()})")
        
        # Display Access Code
        code = current_event.get('access_code', 'N/A')
        st.info(f"🔑 Code: **{code}**")
        
        # Display Currency
        currency_code = current_event.get('currency', 'USD')
        currency_symbol = CURRENCY_SYMBOLS.get(currency_code, '$')
        st.caption(f"💱 Currency: {currency_symbol} {currency_code}")
        
        if st.button("⬅️ Back to Events"):
            st.session_state.current_event = None
            st.rerun()
            
        st.divider()
        menu = st.radio("Navigation", ["Dashboard", "Add Expense", "Edit Expenses", "Settle Expenses", "Manage Event"])

    # Data Prep
    df = pd.DataFrame(current_event['expenses'])
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])

    # --- Dashboard ---
    if menu == "Dashboard":
        st.title(current_event['name'])
        
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
            st.info("No expenses recorded yet.")
        else:
            debts = calculate_debts(current_event['expenses'], current_event['members'])
            
            col1, col2 = st.columns(2)
            total_unsettled = unsettled_df['amount'].sum() if not unsettled_df.empty else 0
            col1.metric("Total Unsettled", format_currency(total_unsettled))
            col2.metric("Pending Settlements", len(debts))
            
            if debts:
                st.subheader("⚠️ Who Owes Who")
                for debt in debts:
                    st.info(f"**{debt['debtor']}** owes **{debt['creditor']}**: {format_currency(debt['amount'])}")
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
            
            # Add formatted amount column
            display_df['display_amount'] = display_df.apply(format_expense_display, axis=1)
            
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

    # --- Add Expense ---
    elif menu == "Add Expense":
        st.title("Add Expense")
        
        # Initialize session state for form submission tracking
        if 'expense_saved' not in st.session_state:
            st.session_state.expense_saved = False
        
        # Show success message if expense was just saved
        if st.session_state.expense_saved:
            st.success("✅ Expense saved successfully!")
            st.session_state.expense_saved = False
        
        # 1. Currency Selection (Outside Form for interactivity)
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
        
        col_curr, col_mode = st.columns([1, 2])
        with col_curr:
            selected_currency = st.selectbox(
                "Currency",
                options=list(currencies.keys()),
                index=list(currencies.keys()).index(event_currency) if event_currency in currencies else 0,
                format_func=lambda x: x,
                key="add_exp_curr"
            )
            
        conversion_mode = "Auto"
        if selected_currency != event_currency:
            with col_mode:
                conversion_mode = st.radio(
                    "Conversion Method", 
                    ["Auto (Market Rate)", "Manual (Set Base Amount)"], 
                    horizontal=True,
                    help="Auto: We fetch the rate. Manual: You specify the exact amount in event currency.",
                    key="add_exp_mode"
                )
        
        with st.form("add_expense", clear_on_submit=True):
            title = st.text_input("Description")
            
            # Dynamic Inputs
            amount_in_base = 0.0
            amount_in_original = 0.0
            
            if selected_currency == event_currency:
                amount_in_base = st.number_input(f"Amount ({event_currency})", min_value=0.01)
            else:
                if conversion_mode == "Auto (Market Rate)":
                    amount_in_original = st.number_input(f"Amount ({selected_currency})", min_value=0.01)
                    st.caption(f"Will be converted to {event_currency} on submit.")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        amount_in_original = st.number_input(f"Spent ({selected_currency})", min_value=0.01)
                    with c2:
                        amount_in_base = st.number_input(f"Equivalent ({event_currency})", min_value=0.01)
                
            payer = st.selectbox("Paid By", current_event['members'], index=current_event['members'].index(st.session_state.current_user) if st.session_state.current_user in current_event['members'] else 0)
            category = st.selectbox("Category", ["Food", "Transport", "Accommodation", "Entertainment", "Utilities", "Other"])
            involved = st.multiselect("Split Among", current_event['members'], default=current_event['members'])
            date = st.date_input("Date", datetime.today())
            
            submitted = st.form_submit_button("Save Expense", type="primary")
            
            if submitted:
                if title and involved:
                    with st.spinner("Saving expense..."):
                        # Logic to determine final amounts
                        final_amount = 0.0
                        original_amt = None
                        original_curr = None
                        exch_rate = None
                        
                        if selected_currency == event_currency:
                            final_amount = amount_in_base
                        else:
                            original_curr = selected_currency
                            original_amt = amount_in_original
                            
                            if conversion_mode == "Auto (Market Rate)":
                                rate = get_exchange_rate(selected_currency, event_currency)
                                if rate:
                                    final_amount = amount_in_original * rate
                                    exch_rate = rate
                                else:
                                    st.error("Could not fetch rate. Using 1:1.")
                                    final_amount = amount_in_original
                                    exch_rate = 1.0
                            else:
                                final_amount = amount_in_base
                                if amount_in_original > 0:
                                    exch_rate = final_amount / amount_in_original
                        
                        new_expense = {
                            "id": len(current_event['expenses']) + 1,
                            "title": title,
                            "amount": final_amount,
                            "original_amount": original_amt,
                            "original_currency": original_curr,
                            "exchange_rate": exch_rate,
                            "payer": payer,
                            "involved": involved,
                            "date": str(date),
                            "category": category,
                            "settled": False
                        }
                        current_event['expenses'].append(new_expense)
                        save_data(data)
                        st.session_state.data = data
                        st.session_state.expense_saved = True
                        st.rerun()
                else:
                    st.error("Please fill all required fields.")

    # --- Edit Expenses ---
    elif menu == "Edit Expenses":
        st.title("Edit Expenses")
        
        # Check if user is admin
        if not is_admin():
            st.warning("⚠️ Only event admins can edit or delete expenses.")
            st.info("Contact an admin if you need to modify an expense.")
        elif not current_event['expenses']:
            st.info("No expenses to edit yet.")
        else:
            # Initialize session state for edit tracking
            if 'edit_expense_id' not in st.session_state:
                st.session_state.edit_expense_id = None
            if 'expense_updated' not in st.session_state:
                st.session_state.expense_updated = False
            
            # Show success message if expense was just updated
            if st.session_state.expense_updated:
                st.success("✅ Expense updated successfully!")
                st.session_state.expense_updated = False
            
            # Display list of expenses to select from
            st.subheader("Select an expense to edit:")
            
            expense_options = []
            for exp in current_event['expenses']:
                status = "✓ Settled" if exp.get('settled', False) else "⏳ Pending"
                display_amt = format_expense_display(exp)
                expense_options.append(f"{exp['date']} - {exp['title']} ({display_amt}) - {status}")
            
            selected_idx = st.selectbox(
                "Choose expense:",
                range(len(expense_options)),
                format_func=lambda x: expense_options[x]
            )
            
            if selected_idx is not None:
                selected_expense = current_event['expenses'][selected_idx]
                
                st.divider()
                st.subheader("Edit Details:")
                
                # 1. Currency Selection (Outside Form)
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
                
                # Determine initial values for outside widgets
                initial_currency = selected_expense.get('original_currency', event_currency)
                initial_amount_orig = selected_expense.get('original_amount', selected_expense['amount'])
                initial_amount_base = selected_expense['amount']
                
                # Use session state to initialize widgets only once per selection
                if 'edit_curr' not in st.session_state or st.session_state.get('last_edit_id') != selected_expense['id']:
                    st.session_state.edit_curr = initial_currency
                    st.session_state.last_edit_id = selected_expense['id']
                    # Default mode: Manual if we have original amount, else Auto
                    st.session_state.edit_mode = "Manual (Set Base Amount)" if selected_expense.get('original_amount') else "Auto (Market Rate)"

                col_curr, col_mode = st.columns([1, 2])
                with col_curr:
                    new_currency = st.selectbox(
                        "Currency",
                        options=list(currencies.keys()),
                        index=list(currencies.keys()).index(initial_currency) if initial_currency in currencies else 0,
                        format_func=lambda x: x,
                        key="edit_exp_curr"
                    )
                
                conversion_mode = "Auto"
                if new_currency != event_currency:
                    with col_mode:
                        conversion_mode = st.radio(
                            "Conversion Method", 
                            ["Auto (Market Rate)", "Manual (Set Base Amount)"], 
                            horizontal=True,
                            key="edit_exp_mode"
                        )

                with st.form("edit_expense_form"):
                    new_title = st.text_input("Description", value=selected_expense['title'])
                    
                    # Dynamic Inputs
                    new_amount_base = 0.0
                    new_amount_orig = 0.0
                    
                    if new_currency == event_currency:
                        new_amount_base = st.number_input(f"Amount ({event_currency})", min_value=0.01, value=float(initial_amount_base))
                    else:
                        if conversion_mode == "Auto (Market Rate)":
                            # If switching to Auto, try to use original amount if available, else base
                            val = float(initial_amount_orig) if initial_currency == new_currency else 1.0
                            new_amount_orig = st.number_input(f"Amount ({new_currency})", min_value=0.01, value=val)
                            st.caption(f"Will be converted to {event_currency} on submit.")
                        else:
                            c1, c2 = st.columns(2)
                            with c1:
                                val_orig = float(initial_amount_orig) if initial_currency == new_currency else 1.0
                                new_amount_orig = st.number_input(f"Spent ({new_currency})", min_value=0.01, value=val_orig)
                            with c2:
                                val_base = float(initial_amount_base)
                                new_amount_base = st.number_input(f"Equivalent ({event_currency})", min_value=0.01, value=val_base)
                    
                    # Get current payer index
                    try:
                        payer_idx = current_event['members'].index(selected_expense['payer'])
                    except ValueError:
                        payer_idx = 0
                    
                    new_payer = st.selectbox("Paid By", current_event['members'], index=payer_idx)
                    
                    # Get current category index
                    categories = ["Food", "Transport", "Accommodation", "Entertainment", "Utilities", "Other"]
                    try:
                        cat_idx = categories.index(selected_expense['category'])
                    except ValueError:
                        cat_idx = 0
                    
                    new_category = st.selectbox("Category", categories, index=cat_idx)
                    
                    # Handle involved members
                    current_involved = selected_expense.get('involved', current_event['members'])
                    new_involved = st.multiselect("Split Among", current_event['members'], default=current_involved)
                    
                    # Parse date
                    try:
                        current_date = datetime.strptime(selected_expense['date'], '%Y-%m-%d').date()
                    except:
                        current_date = datetime.today().date()
                    
                    new_date = st.date_input("Date", value=current_date)
                    
                    submitted = st.form_submit_button("Update Expense", type="primary")
                    
                    if submitted:
                        if new_title and new_involved: # Added this check back for form validation
                            with st.spinner("Updating expense..."):
                                # Logic to determine final amounts
                                final_amount = 0.0
                                original_amt = None
                                original_curr = None
                                exch_rate = None
                                
                                if new_currency == event_currency:
                                    final_amount = new_amount_base
                                else:
                                    original_curr = new_currency
                                    original_amt = new_amount_orig
                                    
                                    if conversion_mode == "Auto (Market Rate)":
                                        rate = get_exchange_rate(new_currency, event_currency)
                                        if rate:
                                            final_amount = new_amount_orig * rate
                                            exch_rate = rate
                                        else:
                                            st.error("Could not fetch rate. Using 1:1.")
                                            final_amount = new_amount_orig
                                            exch_rate = 1.0
                                    else:
                                        final_amount = new_amount_base
                                        if new_amount_orig > 0:
                                            exch_rate = final_amount / new_amount_orig
                                
                                selected_expense['title'] = new_title
                                selected_expense['amount'] = final_amount
                                selected_expense['original_amount'] = original_amt
                                selected_expense['original_currency'] = original_curr
                                selected_expense['exchange_rate'] = exch_rate
                                selected_expense['payer'] = new_payer
                                selected_expense['category'] = new_category
                                selected_expense['involved'] = new_involved
                                selected_expense['date'] = str(new_date)
                                selected_expense['settled'] = selected_expense.get('settled', False) # Ensure settled status is preserved
                                
                                save_data(data)
                                st.session_state.data = data
                                st.session_state.expense_updated = True
                                st.rerun()
                        else:
                            st.error("Please fill all required fields.")
                
                # Delete button is now outside the form
                if st.button("🗑️ Delete Expense"):
                    with st.spinner("Deleting expense..."):
                        current_event['expenses'].pop(selected_idx) # Use pop with index to remove
                        save_data(data)
                        st.session_state.data = data
                        st.success("Expense deleted successfully!")
                        st.rerun()


    # --- Settle Expenses ---
    elif menu == "Settle Expenses":
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
        else:
            st.info("The following payments are pending:")
            for debt in debts:
                st.write(f"• **{debt['debtor']}** owes **{debt['creditor']}**: {format_currency(debt['amount'])}")
        
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
                
                # Show suggested amount if user owes this person
                # Re-check debt for the *selected* recipient (in case user changed selection, 
                # but wait, inside form we can't react to selection change. 
                # So we only show suggestion for the *default* or *initially selected* one?
                # Actually, we can't show dynamic suggestions inside the form based on form selection.
                # We can only show "You owe [Someone]: [Amount]" if we move recipient selection outside.
                # But let's keep it simple for now. We'll just show the suggestion for the *default* selection if applicable,
                # or maybe just list all debts above the form (which we already do).
                
                if suggested_debt and recipient == suggested_debt['creditor']:
                     st.info(f"💡 {payer} owes {recipient}: {format_currency(suggested_debt['amount'])}")
                
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
                    with st.spinner("Recording payment..."):
                        # Create settlement record
                        new_settlement = {
                            "id": len(current_event.get('settlements', [])) + 1,
                            "from_user": payer,
                            "to_user": recipient,
                            "amount": converted_amount,  # Store converted amount in event currency
                            "original_amount": amount if use_different_currency else None,
                            "original_currency": payment_currency if use_different_currency else None,
                            "exchange_rate": exchange_rate if use_different_currency else None,
                            "date": str(payment_date),
                            "notes": notes
                        }
                        
                        current_event['settlements'].append(new_settlement)
                        save_data(data)
                        st.session_state.data = data
                        st.session_state.payment_recorded = True
                        st.rerun()
        
        # Display payment history
        if current_event.get('settlements'):
            st.divider()
            st.subheader("📜 Payment History")
            
            settlements_df = pd.DataFrame(current_event['settlements'])
            settlements_df = settlements_df.sort_values('date', ascending=False)
            
            # Format for display with currency conversion info
            for idx, settlement in enumerate(current_event['settlements'][::-1]):  # Reverse to match sorted order
                with st.expander(
                    f"{settlement['date']} - {settlement['from_user']} → {settlement['to_user']}: {format_currency(settlement['amount'])}"
                ):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**From:** {settlement['from_user']}")
                        st.write(f"**To:** {settlement['to_user']}")
                        st.write(f"**Date:** {settlement['date']}")
                    with col2:
                        st.write(f"**Amount:** {format_currency(settlement['amount'])}")
                        
                        # Show conversion info if available
                        if settlement.get('original_currency') and settlement.get('original_amount'):
                            st.write(f"**Original:** {format_currency(settlement['original_amount'], settlement['original_currency'])}")
                            st.write(f"**Rate:** 1 {settlement['original_currency']} = {settlement.get('exchange_rate', 0):.4f} {current_event.get('currency', 'USD')}")
                        
                        if settlement.get('notes'):
                            st.write(f"**Notes:** {settlement['notes']}")


    # --- Manage Event ---
    elif menu == "Manage Event":
        st.title("Manage Event")
        
        # Initialize profile view state
        if 'viewing_profile' not in st.session_state:
            st.session_state.viewing_profile = None
            
        # Profile View
        if st.session_state.viewing_profile:
            target_user = st.session_state.viewing_profile
            user_data = next((u for u in data['users'] if u['username'] == target_user), None)
            
            with st.expander(f"👤 Profile: {target_user}", expanded=True):
                c1, c2 = st.columns([1, 3])
                with c1:
                    if user_data and user_data.get('avatar'):
                        try:
                            st.image(base64.b64decode(user_data['avatar']), width=100)
                        except:
                            st.write("👤")
                    else:
                        st.write("👤 No Avatar")
                with c2:
                    st.subheader(target_user)
                    role = current_event.get('roles', {}).get(target_user, 'member')
                    st.info(f"Role: {role.title()}")
                    
                    # Bank Details Logic
                    st.divider()
                    st.markdown("#### 🏦 Bank Details")
                    
                    if target_user == st.session_state.current_user:
                         st.info("Go to Account Settings to manage your details.")
                    else:
                        approved_list = user_data.get('approved_viewers', []) if user_data else []
                        requests_list = user_data.get('access_requests', []) if user_data else []
                        
                        if st.session_state.current_user in approved_list:
                            raw_details = user_data.get('bank_details', '')
                            try:
                                details_json = json.loads(raw_details)
                                st.success("✅ Access Granted")
                                st.caption(f"Region: {details_json.get('country')}")
                                for k, v in details_json.get('fields', {}).items():
                                    if v:
                                        st.text(f"{k.replace('_', ' ').title()}: {v}")
                            except:
                                st.success("✅ Access Granted")
                                st.code(raw_details or "No details provided.")
                        elif st.session_state.current_user in requests_list:
                            st.warning("⏳ Request Pending Approval")
                        else:
                            if st.button("🔒 Request Access to Bank Details"):
                                if user_data:
                                    if 'access_requests' not in user_data:
                                        user_data['access_requests'] = []
                                    user_data['access_requests'].append(st.session_state.current_user)
                                    save_data(data)
                                    st.success("Request sent!")
                                    st.rerun()
                
                if st.button("Close Profile"):
                    st.session_state.viewing_profile = None
                    st.rerun()
            st.divider()
        
        # Display all members with their roles
        st.subheader("👥 Event Members")
        
        # Ensure roles dict exists
        if 'roles' not in current_event:
            current_event['roles'] = {}
        
        # Display members in a nice format
        for member in current_event['members']:
            role = current_event['roles'].get(member, 'member')
            role_emoji = "👑" if role == "admin" else "👤"
            
            # Get avatar for list
            member_data = next((u for u in data['users'] if u['username'] == member), None)
            
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            with col1:
                if member_data and member_data.get('avatar'):
                    try:
                        st.image(base64.b64decode(member_data['avatar']), width=35)
                    except:
                        st.write("👤")
                else:
                    st.write("👤")
            
            with col2:
                st.write(f"**{member}**")
                st.caption(f"{role.title()}")
            
            with col3:
                if st.button("View Profile", key=f"view_{member}"):
                    st.session_state.viewing_profile = member
                    st.rerun()
            
            with col4:
                # Only admins can remove members or change roles
                if is_admin() and member != st.session_state.current_user:
                    if st.button(f"Remove", key=f"remove_{member}"):
                        current_event['members'].remove(member)
                        if member in current_event['roles']:
                            del current_event['roles'][member]
                        save_data(data)
                        st.session_state.data = data
                        st.success(f"Removed {member}")
                        st.rerun()
        
        st.divider()
        
        # Add Member Section
        st.subheader("➕ Add Member to Event")
        
        if 'member_added' not in st.session_state:
            st.session_state.member_added = False
        
        if st.session_state.member_added:
            st.success("✅ Member added successfully!")
            st.session_state.member_added = False
        
        with st.form("add_member_form", clear_on_submit=True):
            new_member_username = st.text_input("Enter Username to Add")
            submitted = st.form_submit_button("Add Member", type="primary")
            
            if submitted:
                # Check if user exists
                user_exists = any(u['username'] == new_member_username for u in data['users'])
                if not user_exists:
                    st.error("User not found.")
                elif new_member_username in current_event['members']:
                    st.warning("User already in event.")
                else:
                    with st.spinner("Adding member..."):
                        current_event['members'].append(new_member_username)
                        # Assign default member role
                        current_event['roles'][new_member_username] = "member"
                        save_data(data)
                        st.session_state.data = data
                        st.session_state.member_added = True
                        st.rerun()
        
        # Role Management Section (Admin Only)
        if is_admin():
            st.divider()
            st.subheader("👑 Manage Roles (Admin Only)")
            
            if 'role_updated' not in st.session_state:
                st.session_state.role_updated = False
            
            if st.session_state.role_updated:
                st.success("✅ Role updated successfully!")
                st.session_state.role_updated = False
            
            with st.form("role_management_form"):
                # Get non-admin members
                eligible_members = [m for m in current_event['members'] 
                                  if m != st.session_state.current_user]
                
                if eligible_members:
                    selected_member = st.selectbox("Select Member", eligible_members)
                    current_role = current_event['roles'].get(selected_member, 'member')
                    new_role = st.radio("Assign Role", ["member", "admin"], 
                                       index=0 if current_role == "member" else 1)
                    
                    submitted = st.form_submit_button("Update Role", type="primary")
                    
                    if submitted:
                        with st.spinner("Updating role..."):
                            current_event['roles'][selected_member] = new_role
                            save_data(data)
                            st.session_state.data = data
                            st.session_state.role_updated = True
                            st.rerun()
                else:
                    st.info("No other members to manage.")
                    st.form_submit_button("Update Role", disabled=True)
            
            # Currency Management Section (Admin Only)
            st.divider()
            st.subheader("💱 Change Event Currency (Admin Only)")
            
            if 'currency_updated' not in st.session_state:
                st.session_state.currency_updated = False
            
            if st.session_state.currency_updated:
                st.success("✅ Currency updated successfully!")
                st.session_state.currency_updated = False
            
            currencies = {
                "USD": "$ (US Dollar)", "EUR": "€ (Euro)", "GBP": "£ (British Pound)",
                "JPY": "¥ (Japanese Yen)", "CNY": "¥ (Chinese Yuan)", "AUD": "A$ (Australian Dollar)",
                "CAD": "C$ (Canadian Dollar)", "CHF": "Fr (Swiss Franc)", "HKD": "HK$ (Hong Kong Dollar)",
                "SGD": "S$ (Singapore Dollar)", "KRW": "₩ (South Korean Won)", "INR": "₹ (Indian Rupee)",
                "MXN": "Mex$ (Mexican Peso)", "BRL": "R$ (Brazilian Real)", "ZAR": "R (South African Rand)",
                "NZD": "NZ$ (New Zealand Dollar)", "THB": "฿ (Thai Baht)", "MYR": "RM (Malaysian Ringgit)",
                "PHP": "₱ (Philippine Peso)", "IDR": "Rp (Indonesian Rupiah)", "VND": "₫ (Vietnamese Dong)"
            }
            
            current_currency = current_event.get('currency', 'USD')
            current_idx = list(currencies.keys()).index(current_currency) if current_currency in currencies else 0
            
            with st.form("currency_change_form"):
                new_currency = st.selectbox(
                    "Select New Currency",
                    options=list(currencies.keys()),
                    format_func=lambda x: currencies[x],
                    index=current_idx
                )
                
                st.caption(f"Current currency: {currencies.get(current_currency, current_currency)}")
                
                submitted = st.form_submit_button("Update Currency", type="primary")
                
                if submitted:
                    if new_currency != current_currency:
                        with st.spinner("Updating currency..."):
                            current_event['currency'] = new_currency
                            save_data(data)
                            st.session_state.data = data
                            st.session_state.currency_updated = True
                            st.rerun()
                    else:
                        st.info("Currency is already set to this value.")


