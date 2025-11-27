import streamlit as st
import random
import string
import time
from datetime import datetime
from utils import get_display_name, parse_group_info
from database import create_event, get_event_by_access_code, add_event_member, load_data

def render_landing_page(data):
    """Render the main landing page."""
    from onboarding import should_show_onboarding, show_welcome_screen, show_tutorial_step, check_if_new_user
    
    # Check if this is a new user
    is_new_user = check_if_new_user(data)
    
    # Show onboarding for new users
    if is_new_user and should_show_onboarding():
        # Check if tutorial is active
        if st.session_state.get('show_tutorial', False):
            tutorial_step = st.session_state.get('tutorial_step', 0)
            show_tutorial_step(tutorial_step)
            return
        else:
            # Show welcome screen
            show_welcome_screen()
            return
    
    # Regular landing page for existing users
    st.title("Welcome to SplitSync! 👋")
    
    st.markdown("""
    ### Your Smart Expense Sharing Companion
    
    Track shared expenses, split bills fairly, and settle up with friends - all in one place.
    """)
    
    # Quick stats
    my_events = [e for e in data.get('events', []) if st.session_state.current_user in e['members']]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Your Events", len(my_events))
    with col2:
        total_expenses = sum(len(e.get('expenses', [])) for e in my_events)
        st.metric("Total Expenses", total_expenses)
    with col3:
        st.metric("Active", len([e for e in my_events if len(e.get('expenses', [])) > 0]))
    
    st.divider()
    
    # Action buttons
    st.subheader("What would you like to do?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 View My Events", type="primary", use_container_width=True):
            st.session_state.show_events = True
            st.rerun()
        st.caption("See all your events and manage expenses")
    
    with col2:
        if st.button("➕ Create New Event", type="secondary", use_container_width=True):
            st.session_state.show_events = True
            st.rerun()
        st.caption("Start a new expense sharing event")
    
    st.divider()
    
    # Recent activity (if any)
    if my_events:
        st.subheader("Recent Activity")
        recent_event = my_events[0]  # Show most recent
        with st.container():
            st.markdown(f"**{recent_event['name']}**")
            member_names = [get_display_name(m, data['users']) for m in recent_event['members']]
            st.caption(f"Members: {', '.join(member_names[:3])}" + 
                      (f" +{len(member_names)-3} more" if len(member_names) > 3 else ""))
            if st.button("Open", key="open_recent"):
                st.session_state.current_event = recent_event
                st.rerun()

def render_events_list(data):
    """Render the list of events and create/join forms."""
    from onboarding import create_demo_event
    
    # Load demo event if requested
    if st.session_state.get('demo_loaded', False) and not any(e.get('id') == 'demo_event_001' for e in data.get('events', [])):
        demo_event = create_demo_event()
        # Add demo event to data (in-memory only for demo purposes)
        if 'events' not in data:
            data['events'] = []
        data['events'].insert(0, demo_event)
        st.session_state.data = data
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("← Home"):
            st.session_state.show_events = False
            st.rerun()
    with col2:
        st.title("Your Events")
    
    # Filter events where current user is a member
    my_events = [e for e in data.get('events', []) if st.session_state.current_user in e['members']]
    
    if my_events:
        for event in my_events:
            with st.container():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.subheader(event['name'])
                    member_names = [get_display_name(m, data['users']) for m in event['members']]
                    st.caption(f"Members: {', '.join(member_names)}")
                with c2:
                    if st.button("Open", key=f"open_{event['id']}"):
                        st.session_state.current_event = event
                        st.rerun()
                st.divider()
    else:
        st.info("📭 **No events found.** Create your first event to get started!")
        st.markdown("""
        ### How to create an event:
        1. Fill in the event name (e.g., "Japan Trip 2024")
        2. Choose your currency
        3. Click "Create Event"
        4. Share the access code with friends to invite them!
        
        💡 **Tip:** Use the "Smart Import" feature to auto-fill details from WhatsApp!
        """)
        
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
                    info = parse_group_info(import_text)
                    if info['name']:
                        st.session_state.new_event_name = info['name']
                        st.success(f"Found Event: {info['name']}")
                    if info['members']:
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
            members = [st.session_state.current_user]
            
            submitted = st.form_submit_button("Create Event", type="primary")
            
            if submitted:
                if event_name:
                    with st.spinner("🎉 Creating your event..."):
                        # Generate unique event ID using timestamp
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
                        
                        if create_event(new_event):
                            st.toast(f"✅ Event '{event_name}' created! Code: {access_code}", icon="🎉")
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
                        event_to_join = get_event_by_access_code(code_input.upper())
                        
                        if event_to_join:
                            if st.session_state.current_user not in event_to_join['members']:
                                # Add user to event
                                if add_event_member(event_to_join['id'], st.session_state.current_user, 'member'):
                                    st.toast(f"✅ Joined event: {event_to_join['name']}", icon="🤝")
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
