import streamlit as st
import time
import random
import string
import re
from auth import hash_password, verify_password, validate_password
from utils import send_email
from database import register_user, init_connection, load_data

def render_auth(data):
    """Render the login/register/forgot password tabs."""
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
                                st.toast("✅ Login successful!", icon="✅")
                                st.session_state.current_user = user['username']
                                # Set query param for persistent login
                                st.query_params['user'] = user['username']
                                # Clear cache and reload fresh data for the logged‑in user
                                load_data.clear()
                                st.session_state.data = load_data(current_user=user['username'])
                                # Show home page after login (not events list)
                                st.session_state.show_events = False
                                time.sleep(0.5)  # Brief pause to show success message
                                st.rerun()
                            else:
                                st.error("❌ Incorrect password. Please try again.")
                                st.caption("💡 Forgot your password? Use the 'Forgot Password' tab.")
                        else:
                            st.error("❌ Username not found. Please check your spelling or register a new account.")
                    except Exception as e:
                        st.error("❌ Unable to log in right now. Please try again in a moment.")
                        st.caption(f"💡 If this persists, contact support. Error: {str(e)[:50]}")
                else:
                    st.error("❌ Cannot connect to the server. Please check your internet connection.")

    with tab2:
        st.markdown("Create a new account.")
        if st.session_state.reg_step == 1:
            with st.form("reg_form_1"):
                new_username = st.text_input("Choose Username")
                st.caption("📝 Min 3 chars. Letters, numbers, and underscores only. No spaces.")
                
                # Real-time username validation
                if new_username:
                    from validation import validate_username
                    existing_usernames = [u['username'] for u in data['users']]
                    is_valid, msg, available = validate_username(new_username, existing_usernames)
                    if available is False:
                        st.error(msg)
                    elif available is True:
                        st.success(msg)
                    elif not is_valid:
                        st.warning(msg)
                
                new_display_name = st.text_input("Display Name (Optional)", placeholder="e.g. John Doe")
                new_email = st.text_input("Email Address")
                
                # Real-time email validation
                if new_email:
                    from validation import validate_email
                    is_valid_email, email_msg = validate_email(new_email)
                    if is_valid_email:
                        st.success(email_msg)
                    else:
                        st.warning(email_msg)
                
                new_password = st.text_input("Choose Password", type="password")
                st.caption("🔒 Min 8 chars. Must include uppercase, lowercase, number, and special char.")
                
                # Real-time password strength indicator
                if new_password:
                    from validation import show_password_strength_meter
                    show_password_strength_meter(new_password)
                
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
                                    st.toast("✅ Verification code sent!", icon="📧")
                                    st.session_state.reg_code = code
                                    st.session_state.reg_data = {
                                        "username": new_username,
                                        "email": new_email,
                                        "password": hash_password(new_password),
                                        "display_name": new_display_name if new_display_name else new_username
                                    }
                                    st.session_state.reg_step = 2
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("❌ Unable to send verification email.")
                                    st.caption("💡 Please check that your email address is correct and try again.")
                    else:
                        st.error("❌ Please fill in all required fields to continue.")
        
        elif st.session_state.reg_step == 2:
            st.info(f"Verification code sent to {st.session_state.reg_data.get('email')}")
            code_input = st.text_input("Enter Verification Code")
            if st.button("Verify & Register"):
                if code_input == st.session_state.reg_code:
                    with st.spinner("✨ Creating your account..."):
                        if register_user(st.session_state.reg_data):
                            st.toast(f"✅ Account created! Welcome {st.session_state.reg_data['username']}!", icon="🎉")
                            # Reset state
                            st.session_state.reg_step = 1
                            st.session_state.reg_code = None
                            st.session_state.reg_data = {}
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Registration failed. Please try again or contact support.")
                else:
                    st.error("❌ Incorrect verification code. Please check and try again.")
                    st.caption("💡 The code was sent to your email. Check your spam folder if you don't see it.")
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
                        st.toast(f"✅ Reset code sent! Username: {username_for_email}", icon="📧")
                        st.rerun()
                    else:
                        st.error("❌ Unable to send reset email.")
                        st.caption("💡 Please check your email configuration or try again later.")
                else:
                    st.error("❌ No account found with this email address.")
                    st.caption("💡 Please check your spelling or register a new account.")
        
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
                        supabase = init_connection()
                        if supabase:
                            try:
                                # Find username by email
                                response = supabase.table('users').select("username").eq('email', st.session_state.reset_email).execute()
                                if response.data:
                                    username = response.data[0]['username']
                                    new_hash = hash_password(new_pass)
                                    supabase.table('users').update({'password': new_hash}).eq('username', username).execute()
                                    st.toast("✅ Password reset successful! Please login.", icon="🔐")
                                    st.session_state.reset_step = 1
                                    st.session_state.reset_code = None
                                    st.session_state.reset_email = None
                                    st.rerun()
                            except Exception as e:
                                st.error("❌ Unable to reset password right now.")
                                st.caption(f"💡 Please try again. Error: {str(e)[:50]}")
                else:
                    st.error("❌ Incorrect reset code. Please check and try again.")
                    st.caption("💡 The code was sent to your email. Make sure you entered it correctly.")
            if st.button("Cancel"):
                st.session_state.reset_step = 1
                st.rerun()
