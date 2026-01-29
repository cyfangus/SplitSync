import streamlit as st
import base64
import io
import time
import re
from PIL import Image
from utils import get_display_name
from auth import hash_password, verify_password, validate_password
from database import update_user, init_connection, get_user_by_username, update_username_references_in_db
from ui_utils import render_avatar

def render_settings(data):
    """Render the account settings page."""
    st.title("⚙️ Account Settings")
    
    # Profile Header
    col_av, col_info = st.columns([1, 4])
    with col_av:
        render_avatar(st.session_state.current_user, size=80)
    with col_info:
        st.subheader(f"{st.session_state.current_user}")
        st.caption("Auto-generated avatar based on your username.")
    
    st.divider()
    
    
    # Display Name Form
    current_display_name = get_display_name(st.session_state.current_user, data['users'])
    
    with st.form("change_display_name"):
        new_display_name = st.text_input("Display Name", value=current_display_name)
        if st.form_submit_button("Update Display Name"):
            if new_display_name:
                with st.spinner("✏️ Updating display name..."):
                    if update_user(st.session_state.current_user, {'display_name': new_display_name}):
                        st.success("✅ Display name updated!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.error("Display name cannot be empty.")
    
    st.divider()
    
    # Change Password Section
    st.subheader("Change Password")
    with st.form("change_password"):
        current_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        st.caption("🔒 Min 8 chars. Must include uppercase, lowercase, number, and special char.")
        confirm_pwd = st.text_input("Confirm New Password", type="password")
        
        if st.form_submit_button("Update Password", type="primary"):
            with st.spinner("🔐 Updating password..."):
                # Query Supabase directly for password verification
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


    st.divider()
    
    # Tutorial Section
    st.subheader("🎓 Tutorial")
    if st.button("Restart Onboarding Tutorial"):
        st.session_state.onboarding_complete = False
        st.session_state.show_tutorial = True
        st.session_state.tutorial_step = 0
        st.session_state.show_settings = False
        st.session_state.show_events = False
        st.toast("Tutorial restarted! Redirecting...", icon="🎓")
        time.sleep(1)
        st.rerun()
    
    st.divider()

    # Change Username Section
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
                    with st.spinner("🔄 Updating username across all events..."):
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
    
    # --- Danger Zone (Delete Account) ---
    st.subheader("⚠️ Danger Zone")
    with st.expander("Delete Account"):
        st.warning("🚨 This action is permanent and cannot be undone.")
        
        # 1. Safety Check: Outstanding Debts
        from utils import calculate_debts
        blocking_events = []
        
        for event in data['events']:
            # Calculate debts for this event including settlements
            debts = calculate_debts(event.get('expenses', []), event.get('members', []), event.get('settlements', []))
            
            # Check if user is involved in any debt
            user_debt = next((d for d in debts if d['debtor'] == st.session_state.current_user or d['creditor'] == st.session_state.current_user), None)
            
            if user_debt:
                blocking_events.append(event['name'])
        
        if blocking_events:
            st.error("❌ You cannot delete your account because you have unsettled debts/credits in the following events:")
            for evt in blocking_events:
                st.write(f"• {evt}")
            st.info("💡 Please settle all balances in these events before deleting your account.")
        else:
            st.write("To confirm deletion, please type your username below:")
            confirm_username = st.text_input("Username", key="del_acc_confirm")
            
            if st.button("🗑️ Delete My Account", type="primary", disabled=(confirm_username != st.session_state.current_user)):
                if confirm_username == st.session_state.current_user:
                    from database import anonymize_user
                    
                    with st.spinner("Deleting account..."):
                        if anonymize_user(st.session_state.current_user):
                            st.success("Account deleted successfully.")
                            # Logout
                            st.session_state.current_user = None
                            st.session_state.current_event = None
                            st.session_state.show_events = False
                            st.query_params.clear()
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("Failed to delete account. Please try again.")
                else:
                    st.error("Username does not match.")

    st.divider()
                    
    if st.button("← Back to Events"):
        st.session_state.show_settings = False
        st.rerun()
