import streamlit as st
import base64
import io
import time
import re
from PIL import Image
from utils import get_display_name
from auth import hash_password, verify_password, validate_password
from database import update_user, init_connection, get_user_by_username, update_username_references_in_db

def render_settings(data):
    """Render the account settings page."""
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
    
    with col2:
        st.subheader("Profile Settings")
        
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
                    
    if st.button("← Back to Events"):
        st.session_state.show_settings = False
        st.rerun()
