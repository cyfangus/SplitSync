import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
from datetime import datetime
import random
import string
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from PIL import Image
import base64
import io
import time
import re
from datetime import datetime, timedelta

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
# --- Data Management ---
from database import (
    init_db, load_data, save_data, 
    register_user, create_event, add_expense, 
    add_event_member, get_event_by_access_code,
    update_user, update_username_references_in_db,
    get_user_by_username, init_connection
)

# Initialize database on first run
init_db()

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
            if sett.get('payer') == old_username:
                sett['payer'] = new_username
            if sett.get('recipient') == old_username:
                sett['recipient'] = new_username
    return data

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
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, ""

# --- Session State Initialization ---
if 'data' not in st.session_state:
    with st.spinner("🔄 Loading your data..."):
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

# Reload data with current user context for security
with st.spinner("🔄 Refreshing data..."):
    data = st.session_state.data = load_data(current_user=st.session_state.get('current_user'))

# --- Auto-login from query params ---
query_params = st.query_params

# Handle Invite Links
if 'invite' in query_params:
    invite_code = query_params['invite']
    # Store invite code in session state to handle after login
    st.session_state.pending_invite = invite_code
    
    # If user is already logged in, try to join immediately
    if st.session_state.current_user:
        with st.spinner("🔗 Processing invite link..."):
            from database import get_event_by_access_code, add_event_member
            # In this simple implementation, we use the event ID as the invite code
            # But for security, we should verify it exists first
            # Here we assume invite_code is the event ID for simplicity, or we could look it up
            
            # Let's try to find the event
            target_event = next((e for e in data.get('events', []) if e['id'] == invite_code), None)
            
            if target_event:
                if st.session_state.current_user in target_event['members']:
                    st.success(f"✅ You are already a member of '{target_event['name']}'")
                    st.session_state.current_event = target_event
                    # Clear query param
                    st.query_params.clear()
                else:
                    if add_event_member(target_event['id'], st.session_state.current_user):
                        st.success(f"🎉 Successfully joined '{target_event['name']}'!")
                        load_data.clear() # Refresh data
                        st.session_state.data = load_data(st.session_state.current_user)
                        st.session_state.current_event = target_event
                        st.query_params.clear()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to join event via invite link.")
            else:
                # Maybe it's an access code?
                event_by_code = get_event_by_access_code(invite_code)
                if event_by_code:
                     if st.session_state.current_user in event_by_code['members']:
                        st.success(f"✅ You are already a member of '{event_by_code['name']}'")
                        st.session_state.current_event = event_by_code
                        st.query_params.clear()
                     else:
                        if add_event_member(event_by_code['id'], st.session_state.current_user):
                            st.success(f"🎉 Successfully joined '{event_by_code['name']}'!")
                            load_data.clear()
                            st.session_state.data = load_data(st.session_state.current_user)
                            st.session_state.current_event = event_by_code
                            st.query_params.clear()
                            time.sleep(1)
                            st.rerun()
                        else:
                             st.error("Failed to join event.")
                else:
                    st.error("Invalid invite link.")

if not st.session_state.current_user:
    if 'user' in query_params:
        username_from_url = query_params['user']
        # Verify user exists in database
        if any(u['username'] == username_from_url for u in data.get('users', [])):
            st.session_state.current_user = username_from_url

# --- Login Screen ---
if not st.session_state.current_user:
    st.title("👋 Welcome to SplitSync")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Forgot Password"])
    
    with tab1:
        st.markdown("Please login to continue.")
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        
        if st.button("Login", type="primary"):
            with st.spinner("🔐 Logging in..."):
                # Query Supabase directly for password verification
                supabase = init_connection()
                
                if supabase:
                    try:
                        # Fetch user with password for verification
                        response = supabase.table('users').select("username, password").eq('username', username_input).execute()
                        
                        if response.data and len(response.data) > 0:
                            user = response.data[0]
                            if verify_password(password_input, user['password']):
                                st.success("✅ Login successful!")
                                st.session_state.current_user = user['username']
                                # Set query param for persistent login
                                st.query_params['user'] = user['username']
                                # Clear cache to load fresh data for the logged-in user
                                load_data.clear()
                                # Force reload data into session state
                                st.session_state.data = load_data(current_user=user['username'])
                                time.sleep(0.5)  # Brief pause to show success message
                                st.rerun()
                            else:
                                st.error("Invalid username or password.")
                        else:
                            st.error("Invalid username or password.")
                    except Exception as e:
                        st.error(f"Login error: {e}")
                else:
                    st.error("Database connection error.")

    with tab2:
        st.markdown("Create a new account.")
        if st.session_state.reg_step == 1:
            with st.form("reg_form_1"):
                new_username = st.text_input("Choose Username")
                st.caption("📝 Min 3 chars. Letters, numbers, and underscores only. No spaces.")
                new_email = st.text_input("Email Address")
                new_password = st.text_input("Choose Password", type="password")
                st.caption("🔒 Min 8 chars. Must include uppercase, lowercase, number, and special char.")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                if st.form_submit_button("Next: Verify Email"):
                    if new_username and new_email and new_password:
                        is_valid_pass, pass_err = validate_password(new_password)
                        
                        if new_password != confirm_password:
                            st.error("Passwords do not match.")
                        elif not is_valid_pass:
                            st.error(pass_err)
                        elif not re.match(r"^[a-zA-Z0-9_]+$", new_username):
                            st.error("Username can only contain letters, numbers, and underscores (no spaces).")
                        elif len(new_username) < 3:
                            st.error("Username must be at least 3 characters long.")
                        elif any(u['username'] == new_username for u in data['users']):
                            st.warning("Username already exists.")
                        elif any(u.get('email') == new_email for u in data['users']):
                            st.warning("Email already registered.")
                        else:
                            # Generate Code
                            with st.spinner("📧 Sending verification code..."):
                                code = ''.join(random.choices(string.digits, k=6))
                                if send_email(new_email, "SplitSync Verification Code", f"Your code is: {code}"):
                                    st.success("✅ Verification code sent!")
                                    st.session_state.reg_code = code
                                    st.session_state.reg_data = {
                                        "username": new_username,
                                        "email": new_email,
                                        "password": hash_password(new_password)
                                    }
                                    st.session_state.reg_step = 2
                                    time.sleep(0.5)
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
                    with st.spinner("✨ Creating your account..."):
                        # Use register_user instead of save_data
                        # register_user imported at top
                        if register_user(st.session_state.reg_data):
                            st.success(f"✅ User {st.session_state.reg_data['username']} registered! Please login.")
                            # Reset state
                            st.session_state.reg_step = 1
                            st.session_state.reg_code = None
                            st.session_state.reg_data = {}
                            time.sleep(1)
                        else:
                            st.error("❌ Registration failed. Please try again.")
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
                username_for_email = None
                for u in data['users']:
                    if u.get('email') == reset_email:
                        user_exists = True
                        username_for_email = u['username']
                        break
                
                if user_exists:
                    code = ''.join(random.choices(string.digits, k=6))
                    email_body = f"""Hello,

Your username is: {username_for_email}

Your password reset code is: {code}

Enter this code in the app to reset your password.

If you didn't request this, please ignore this email.
"""
                    if send_email(reset_email, "SplitSync Password Reset", email_body):
                        st.session_state.reset_code = code
                        st.session_state.reset_email = reset_email
                        st.session_state.reset_step = 2
                        st.success(f"✅ Reset code sent! Your username is: **{username_for_email}**")
                        st.rerun()
                    else:
                        st.error("Failed to send email.")
                else:
                    st.error("Email not found.")
        
        elif st.session_state.reset_step == 2:
            st.info(f"Reset code sent to {st.session_state.reset_email}")
            reset_code_input = st.text_input("Enter Reset Code")
            new_pass = st.text_input("New Password", type="password")
            st.caption("🔒 Min 8 chars. Must include uppercase, lowercase, number, and special char.")
            
            if st.button("Reset Password"):
                is_valid_pass, pass_err = validate_password(new_pass)
                
                if reset_code_input == st.session_state.reset_code:
                    if not is_valid_pass:
                        st.error(pass_err)
                    else:
                        # Update password directly in Supabase
                        # init_connection imported at top
                        supabase = init_connection()
                        if supabase:
                            try:
                                # Find username by email
                                response = supabase.table('users').select("username").eq('email', st.session_state.reset_email).execute()
                                if response.data:
                                    username = response.data[0]['username']
                                    new_hash = hash_password(new_pass)
                                    supabase.table('users').update({'password': new_hash}).eq('username', username).execute()
                                    st.success("✅ Password reset successful! Please login.")
                                    st.session_state.reset_step = 1
                                    st.session_state.reset_code = None
                                    st.session_state.reset_email = None
                            except Exception as e:
                                st.error(f"Error resetting password: {e}")
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
        load_data.clear()  # Clear cache to show fresh events
        st.rerun()

    if st.sidebar.button("⚙️ Account Settings"):
        st.session_state.show_settings = True
        st.rerun()
        
    if st.sidebar.button("Logout"):
        st.session_state.current_user = None
        st.session_state.show_settings = False
        # Clear query param
        st.query_params.clear()
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
                        # update_user imported at top
                        if update_user(st.session_state.current_user, {'avatar': img_str}):
                            st.success("✅ Avatar updated!")
                            st.rerun()
                        else:
                            st.error("Failed to update avatar.")
                    except Exception as e:
                        st.error(f"Error processing image: {e}")
        
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Change Password")
            with st.form("change_password"):
                current_pwd = st.text_input("Current Password", type="password")
                new_pwd = st.text_input("New Password", type="password")
                st.caption("🔒 Min 8 chars. Must include uppercase, lowercase, number, and special char.")
                confirm_pwd = st.text_input("Confirm New Password", type="password")
                
                if st.form_submit_button("Update Password", type="primary"):
                    # Query Supabase directly for password verification
                    # init_connection imported at top
                    supabase = init_connection()
                    
                    if supabase:
                        try:
                            # Fetch current password hash
                            response = supabase.table('users').select("password").eq('username', st.session_state.current_user).execute()
                            
                            if response.data and len(response.data) > 0:
                                current_hash = response.data[0]['password']
                                
                                if verify_password(current_pwd, current_hash):
                                    if new_pwd == confirm_pwd:
                                        is_valid_pass, pass_err = validate_password(new_pwd)
                                        if is_valid_pass:
                                            # Update password in Supabase
                                            new_hash = hash_password(new_pwd)
                                            supabase.table('users').update({'password': new_hash}).eq('username', st.session_state.current_user).execute()
                                            st.success("✅ Password updated successfully!")
                                        else:
                                            st.error(pass_err)
                                    else:
                                        st.error("New passwords do not match.")
                                else:
                                    st.error("Incorrect current password.")
                        except Exception as e:
                            st.error(f"Error updating password: {e}")
        
        with col2:
            st.subheader("Change Username")
            st.warning("⚠️ Changing your username will update it across all past events and expenses.")
            with st.form("change_username"):
                new_username = st.text_input("New Username")
                st.caption("📝 Min 3 chars. Letters, numbers, and underscores only. No spaces.")
                
                if st.form_submit_button("Update Username", type="primary"):
                    if new_username and new_username != st.session_state.current_user:
                        if not re.match(r"^[a-zA-Z0-9_]+$", new_username):
                            st.error("Username can only contain letters, numbers, and underscores (no spaces).")
                        elif len(new_username) < 3:
                            st.error("Username must be at least 3 characters long.")
                        else:
                            # Update username in database
                            # functions imported at top
                            
                            
                            existing_user = get_user_by_username(new_username)
                            if existing_user:
                                st.error("Username already taken.")
                            else:
                                old_user = st.session_state.current_user
                                if update_user(old_user, {'username': new_username}):
                                    # Update references
                                    if update_username_references_in_db(old_user, new_username):
                                        st.session_state.current_user = new_username
                                        st.query_params['user'] = new_username
                                        st.success(f"✅ Username changed to {new_username}!")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("Failed to update username references.")
                                else:
                                    st.error("Failed to update username.")
                    elif new_username == st.session_state.current_user:
                        st.info("New username is the same as current.")
                    else:
                        st.error("Please enter a valid username.")
        
        st.divider()
                        
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
        
        # --- Smart Import Feature ---
        with st.expander("✨ Import from WhatsApp/Text", expanded=False):
            st.caption("Paste your WhatsApp group info here to auto-fill details.")
            import_text = st.text_area("Group Info / Text", height=100, placeholder="Example:\nGroup: Japan Trip\nMembers: John, Sarah, +1 234 567 890")
            
            if st.button("Parse & Fill"):
                if import_text:
                    from utils import parse_group_info
                    info = parse_group_info(import_text)
                    if info['name']:
                        st.session_state.new_event_name = info['name']
                        st.success(f"Found Event: {info['name']}")
                    if info['members']:
                        # We can't auto-add members to the database yet, but we can list them
                        # For now, let's just use the name, as members need to be registered users
                        st.info(f"Found potential members: {', '.join(info['members'])}")
                        st.caption("Note: You'll need to invite them after creating the event.")
                else:
                    st.warning("Please paste some text first.")
        
        # Initialize session state for create event
        if 'event_created' not in st.session_state:
            st.session_state.event_created = False
        
        if st.session_state.event_created:
            st.success("✅ Event created successfully!")
            st.session_state.event_created = False
        
        with st.form("new_event", clear_on_submit=True):
            # Use session state value if available (from import)
            default_name = st.session_state.get('new_event_name', '')
            event_name = st.text_input("Event Name", value=default_name, placeholder="e.g. Japan Trip 2024")
            
            # Clear the session state after using it so it doesn't persist forever
            if 'new_event_name' in st.session_state:
                del st.session_state.new_event_name
            
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
                    with st.spinner("🎉 Creating your event..."):
                        # Generate unique event ID using timestamp
                        import time
                        event_id = f"event_{int(time.time() * 1000)}"
                        
                        # Generate unique access code
                        access_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        
                        new_event = {
                            "id": event_id,
                            "name": event_name,
                            "members": members,
                            "roles": {st.session_state.current_user: "admin"},  # Creator is admin
                            "currency": selected_currency,
                            "expenses": [],
                            "access_code": access_code,
                            "settlements": []
                        }
                        
                        # Use create_event instead of save_data
                        # create_event imported at top
                        if create_event(new_event):
                            st.success(f"✅ Event '{event_name}' created! Access code: **{access_code}**")
                            st.info("Refresh the page to see your new event.")
                        else:
                            st.error("❌ Failed to create event. Please check the error message above.")
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
                    with st.spinner("🤝 Joining event..."):
                        # Find event with matching code
                        matching_event = None
                        # get_event_by_access_code imported at top
                        event_to_join = get_event_by_access_code(code_input.upper())
                        
                        if event_to_join:
                            if st.session_state.current_user not in event_to_join['members']:
                                # Add user to event
                                # add_event_member imported at top
                                if add_event_member(event_to_join['id'], st.session_state.current_user, 'member'):
                                    st.success(f"✅ Joined event: {event_to_join['name']}")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to join event.")
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
                    with st.spinner("💰 Saving expense..."):
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
                        
                        expense_data = {
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
                        
                        from database import add_expense
                        if add_expense(current_event['id'], expense_data):
                            st.session_state.expense_saved = True
                            st.rerun()
                        else:
                            st.error("Failed to save expense.")
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
                    # Find the index of the initial currency
                    currency_list = list(currencies.keys())
                    try:
                        initial_index = currency_list.index(initial_currency)
                    except ValueError:
                        initial_index = currency_list.index(event_currency) if event_currency in currency_list else 0
                    
                    new_currency = st.selectbox(
                        "Currency",
                        options=currency_list,
                        index=initial_index,
                        format_func=lambda x: currencies[x],
                        key="edit_exp_curr"
                    )
                    # Show original currency as reference
                    if initial_currency:
                        st.caption(f"💡 Original: {currencies.get(initial_currency, initial_currency)}")
                
                conversion_mode = "Auto"
                if new_currency != event_currency:
                    with col_mode:
                        conversion_mode = st.radio(
                            "Conversion Method", 
                            ["Auto (Market Rate)", "Manual (Set Base Amount)"], 
                            horizontal=True,
                            key="edit_exp_mode"
                        )
                
                # Show current expense summary
                with st.expander("📋 Current Expense Details", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Title:** {selected_expense['title']}")
                        st.write(f"**Amount:** {format_expense_display(selected_expense)}")
                        st.write(f"**Paid By:** {selected_expense['payer']}")
                        st.write(f"**Date:** {selected_expense['date']}")
                    with col2:
                        st.write(f"**Category:** {selected_expense.get('category', 'N/A')}")
                        st.write(f"**Split Among:** {', '.join(selected_expense.get('involved', current_event['members']))}")
                        st.write(f"**Status:** {'✓ Settled' if selected_expense.get('settled', False) else '⏳ Pending'}")

                with st.form("edit_expense_form"):
                    st.caption("✏️ Edit the fields below (pre-filled with current values)")
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
                            with st.spinner("✏️ Updating expense..."):
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
                                
                                updates = {
                                    'title': new_title,
                                    'amount': final_amount,
                                    'original_amount': original_amt,
                                    'original_currency': original_curr,
                                    'exchange_rate': exch_rate,
                                    'payer': new_payer,
                                    'category': new_category,
                                    'involved': new_involved,
                                    'date': str(new_date),
                                    'settled': selected_expense.get('settled', False)
                                }
                                
                                from database import update_expense
                                if update_expense(selected_expense['id'], updates):
                                    st.session_state.expense_updated = True
                                    st.rerun()
                                else:
                                    st.error("Failed to update expense.")
                        else:
                            st.error("Please fill all required fields.")
                
                
                # Delete button with confirmation
                st.divider()
                
                # Initialize delete confirmation state
                if 'confirm_delete_expense' not in st.session_state:
                    st.session_state.confirm_delete_expense = None
                
                if st.session_state.confirm_delete_expense == selected_expense['id']:
                    # Show confirmation dialog
                    st.warning("⚠️ Are you sure you want to delete this expense? This action cannot be undone!")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Yes, Delete", type="primary", key="confirm_delete_yes"):
                            with st.spinner("🗑️ Deleting expense..."):
                                from database import delete_expense
                                if delete_expense(selected_expense['id']):
                                    st.success("Expense deleted successfully!")
                                    st.session_state.confirm_delete_expense = None
                                    st.rerun()
                                else:
                                    st.error("Failed to delete expense.")
                                    st.session_state.confirm_delete_expense = None
                    with col2:
                        if st.button("❌ Cancel", key="confirm_delete_no"):
                            st.session_state.confirm_delete_expense = None
                            st.rerun()
                else:
                    # Show initial delete button
                    if st.button("🗑️ Delete Expense", type="secondary"):
                        st.session_state.confirm_delete_expense = selected_expense['id']
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
        
        # Payment Reminder Feature
        st.subheader("📧 Send Payment Reminder")
        
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
                        debt_options[debt_key] = f"{debtor_name} owes {creditor_name}: {format_currency(amount)}"
                    else:
                        # Show only debtor for regular users
                        debt_key = debtor_name
                        debt_options[debt_key] = f"{debtor_name} owes you {format_currency(amount)}"
                
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

You owe {creditor_name}: {format_currency(selected_debt['amount'])}

Please settle this at your earliest convenience. You can record the payment in the app once done.

Best regards,
{st.session_state.current_user} (Event Admin)"""
                        else:
                            default_message = f"""Hi {debtor_name},

This is a friendly reminder about the outstanding balance in our "{current_event['name']}" event.

Amount owed: {format_currency(selected_debt['amount'])}

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
                    with st.spinner("💳 Recording payment..."):
                        # Create settlement record
                        settlement_data = {
                            "payer": payer,
                            "recipient": recipient,
                            "amount": amount,
                            "payment_currency": payment_currency,
                            "converted_amount": converted_amount,
                            "exchange_rate": exchange_rate,
                            "date": str(payment_date), # Use payment_date here
                            "notes": notes
                        }
                        
                        from database import add_settlement
                        if add_settlement(current_event['id'], settlement_data):
                            st.session_state.payment_recorded = True # Changed to payment_recorded
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
        
        # --- Invite Members Section ---
        st.subheader("🔗 Invite Members")
        
        # Generate Invite Link
        # In production, this would be your actual domain
        # For local dev, it might be localhost:8501
        base_url = "https://splitsync.streamlit.app" # Replace with your actual URL
        invite_link = f"{base_url}/?invite={current_event['id']}"
        
        st.info("Share this link to let others join instantly:")
        st.code(invite_link, language="text")
        
        # WhatsApp Share Button
        # URL encode the message
        import urllib.parse
        message = f"Join our '{current_event['name']}' expense group on SplitSync: {invite_link}"
        encoded_message = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/?text={encoded_message}"
        
        st.link_button("📲 Share on WhatsApp", whatsapp_url, type="primary")
        
        st.divider()
        
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
                    # Initialize remove confirmation state
                    if 'confirm_remove_member' not in st.session_state:
                        st.session_state.confirm_remove_member = None
                    
                    if st.session_state.confirm_remove_member == member:
                        # Show confirmation
                        if st.button(f"✅ Confirm", key=f"confirm_remove_{member}", type="primary"):
                            from database import remove_event_member
                            if remove_event_member(current_event['id'], member):
                                st.success(f"Removed {member} from event.")
                                st.session_state.data = load_data(st.session_state.current_user)
                                st.session_state.confirm_remove_member = None
                                st.rerun()
                            else:
                                st.error(f"Failed to remove {member}.")
                                st.session_state.confirm_remove_member = None
                    else:
                        if st.button(f"Remove", key=f"remove_{member}", type="secondary"):
                            st.session_state.confirm_remove_member = member
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
                    with st.spinner("👥 Adding member..."):
                        from database import add_event_member
                        if add_event_member(current_event['id'], new_member_username):
                            st.session_state.data = load_data(st.session_state.current_user) # Reload data to reflect changes
                            st.session_state.member_added = True
                            st.rerun()
                        else:
                            st.error("Failed to add member.")
        
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
                        with st.spinner("👤 Updating role..."):
                            from database import update_member_role
                            if update_member_role(current_event['id'], selected_member, new_role):
                                st.session_state.data = load_data(st.session_state.current_user) # Reload data to reflect changes
                                st.session_state.role_updated = True
                                st.rerun()
                            else:
                                st.error("Failed to update role.")
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
                        with st.spinner("💱 Updating currency..."):
                            from database import update_event
                        if update_event(current_event['id'], {'currency': new_currency}):
                            st.session_state.data = load_data(st.session_state.current_user) # Reload data to reflect changes
                            st.success("Event currency updated!")
                            st.rerun()
                        else:
                            st.error("Failed to update currency.")
                    else:
                        st.info("Currency is already set to this value.")

            # Danger Zone (Admin Only)
            st.divider()
            st.subheader("⚠️ Danger Zone")
            
            with st.expander("Delete Event"):
                st.warning("⚠️ This action cannot be undone. All expenses and data for this event will be permanently deleted.")
                
                # Initialize delete confirmation state
                if 'confirm_delete_event' not in st.session_state:
                    st.session_state.confirm_delete_event = False
                
                if not st.session_state.confirm_delete_event:
                    # First step: Show delete button
                    if st.button("🗑️ I want to delete this event", type="secondary", key="init_delete_event"):
                        st.session_state.confirm_delete_event = True
                        st.rerun()
                else:
                    # Second step: Type event name to confirm
                    st.error(f"⚠️ **DANGER**: You are about to permanently delete \"{current_event['name']}\"")
                    st.write("To confirm, please type the event name exactly as shown above:")
                    
                    confirm_text = st.text_input("Event name:", key="delete_event_confirm_text")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Yes, Delete Forever", type="primary", key="final_delete_event", disabled=(confirm_text != current_event['name'])):
                            if confirm_text == current_event['name']:
                                with st.spinner("🗑️ Deleting event..."):
                                    from database import delete_event
                                    if delete_event(current_event['id']):
                                        st.success("Event deleted successfully!")
                                        st.session_state.current_event = None
                                        st.session_state.data = load_data(st.session_state.current_user)
                                        st.session_state.confirm_delete_event = False
                                        st.rerun()
                                    else:
                                        st.error("Failed to delete event.")
                                        st.session_state.confirm_delete_event = False
                            else:
                                st.error("Event name doesn't match. Deletion cancelled.")
                    with col2:
                        if st.button("❌ Cancel", key="cancel_delete_event"):
                            st.session_state.confirm_delete_event = False
                            st.rerun()
