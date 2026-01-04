import streamlit as st
import base64
import urllib.parse
from database import remove_event_member, add_event_member, update_member_role, update_event, delete_event, load_data, add_event_participant, remove_event_participant
from ui_utils import render_avatar

def render_manage_event(current_event, data):
    """Render the Manage Event page."""
    st.title("Manage Event")
    
    # Helper function to check if current user is admin
    def is_admin():
        roles = current_event.get('roles', {})
        return roles.get(st.session_state.current_user) == 'admin'

    # --- Invite Members Section ---
    st.subheader("🔗 Invite Members")
    
    # Access Code Display
    st.markdown("### 🔑 Access Code")
    st.info(f"Share this code with your friends: **{current_event.get('access_code', 'N/A')}**")
    
    # Generate Invite Link & Message
    base_url = "https://splitsync.streamlit.app" # Replace with your actual URL
    invite_link = f"{base_url}/?invite={current_event['id']}"
    access_code = current_event.get('access_code', 'N/A')
    
    # Smart Invite Message
    invite_message = f"""Hey! 👋 I'm using SplitSync to track expenses for "{current_event['name']}".

🔗 Join here: {invite_link}
🔑 Access Code: {access_code}

Let's split costs easily! 💸"""

    st.markdown("### 📨 Send Invite")
    st.write("Copy this message to share:")
    st.code(invite_message, language="text")
    
    # WhatsApp Share Button
    encoded_message = urllib.parse.quote(invite_message)
    whatsapp_url = f"https://wa.me/?text={encoded_message}"
    
    col1, col2 = st.columns(2)
    with col1:
        st.link_button("📲 Share on WhatsApp", whatsapp_url, type="primary", use_container_width=True)
    with col2:
        mailto_url = f"mailto:?subject=Join {urllib.parse.quote(current_event['name'])} on SplitSync&body={encoded_message}"
        st.link_button("📧 Share via Email", mailto_url, use_container_width=True)
    
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
                render_avatar(target_user, size=100)
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
            render_avatar(member, size=40)
        
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
                        with st.spinner(f"🚫 Removing {member}..."):
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
                    if add_event_member(current_event['id'], new_member_username):
                        st.session_state.data = load_data(st.session_state.current_user) # Reload data to reflect changes
                        st.session_state.member_added = True
                        st.rerun()
                    else:
                        st.error("Failed to add member.")
    
    st.divider()
    
    # Add Custom Participant Section (Available to All Users)
    st.subheader("➕ Add Participant to Event")
    st.info("💡 Add names of people who don't have accounts. They can still be included in expenses!")
    
    if 'participant_added' not in st.session_state:
        st.session_state.participant_added = False
    
    if st.session_state.participant_added:
        st.success("✅ Participant added successfully!")
        st.session_state.participant_added = False
    
    with st.form("add_participant_form", clear_on_submit=True):
        new_participant_name = st.text_input("Enter Participant Name", placeholder="e.g., John Doe")
        submitted_participant = st.form_submit_button("Add Participant", type="primary")
        
        if submitted_participant:
            if not new_participant_name.strip():
                st.error("Please enter a name.")
            elif new_participant_name.strip() in current_event.get('all_participants', []):
                st.warning("This name is already in the event.")
            else:
                with st.spinner("👤 Adding participant..."):
                    if add_event_participant(current_event['id'], new_participant_name.strip()):
                        st.session_state.data = load_data(st.session_state.current_user)
                        st.session_state.participant_added = True
                        st.rerun()
                    else:
                        st.error("Failed to add participant.")
    
    # Display custom participants
    custom_participants = current_event.get('custom_participants', [])
    if custom_participants:
        st.subheader("📋 Custom Participants")
        st.caption("These people can be included in expenses but don't have accounts.")
        
        for participant in custom_participants:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"👤 **{participant}**")
            with col2:
                # Only admins can remove participants
                if is_admin():
                    # Initialize remove confirmation state
                    if 'confirm_remove_participant' not in st.session_state:
                        st.session_state.confirm_remove_participant = None
                    
                    if st.session_state.confirm_remove_participant == participant:
                        if st.button(f"✅ Confirm", key=f"confirm_remove_part_{participant}", type="primary"):
                            with st.spinner(f"🚫 Removing {participant}..."):
                                if remove_event_participant(current_event['id'], participant):
                                    st.success(f"Removed {participant} from event.")
                                    st.session_state.data = load_data(st.session_state.current_user)
                                    st.session_state.confirm_remove_participant = None
                                    st.rerun()
                                else:
                                    st.error(f"Failed to remove {participant}.")
                                    st.session_state.confirm_remove_participant = None
                    else:
                        if st.button(f"Remove", key=f"remove_part_{participant}", type="secondary"):
                            st.session_state.confirm_remove_participant = participant
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
                    with st.spinner("👤 Updating role..."):
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
