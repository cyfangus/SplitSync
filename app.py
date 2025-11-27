import streamlit as st
from streamlit_autorefresh import st_autorefresh
from database import init_db, load_data, init_connection
from views.auth_view import render_auth
from views.dashboard_view import render_landing_page, render_events_list
from views.settings_view import render_settings
from views.event_details import render_event_dashboard
from views.expenses_view import render_add_expense, render_edit_expenses
from views.settlements_view import render_settle_expenses
from views.analytics_view import render_analytics
from views.manage_event_view import render_manage_event
from views.chatbot_view import render_chatbot

# --- Page Config ---
st.set_page_config(
    page_title="SplitSync",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
    <style>
    .main {
        padding-top: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
    }
    /* Dark mode adjustments */
    @media (prefers-color-scheme: dark) {
        .stMetric {
            background-color: #262730;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- Auto-refresh ---
# Auto-refresh every 30 seconds to keep data in sync
st_autorefresh(interval=30000, key="data_refresh")

# --- Initialization ---
if 'db_initialized' not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# Initialize Session State
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'current_event' not in st.session_state:
    st.session_state.current_event = None
if 'data' not in st.session_state:
    st.session_state.data = {}
if 'reg_step' not in st.session_state:
    st.session_state.reg_step = 1
if 'reset_step' not in st.session_state:
    st.session_state.reset_step = 1
if 'show_events' not in st.session_state:
    st.session_state.show_events = False
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

# --- Auto-login from query params ---
query_params = st.query_params
if "user" in query_params and not st.session_state.current_user:
    user_param = query_params["user"]
    # Verify user exists in DB (simple check)
    supabase = init_connection()
    if supabase:
        try:
            response = supabase.table('users').select("username").eq('username', user_param).execute()
            if response.data:
                st.session_state.current_user = user_param
                st.toast(f"Welcome back, {user_param}!")
        except Exception:
            pass

# --- Data Loading ---
if st.session_state.current_user:
    # Always reload data to ensure freshness
    st.session_state.data = load_data(st.session_state.current_user)

# --- Main App Logic ---

if not st.session_state.current_user:
    # 1. Auth Flow
    render_auth(st.session_state.data)

elif st.session_state.show_settings:
    # 2. Settings Page
    render_settings(st.session_state.data)

elif st.session_state.current_user and not st.session_state.current_event:
    # 3. Dashboard / Event Selection
    with st.sidebar:
        st.title(f"Hi, {st.session_state.current_user}!")
        if st.button("⚙️ Account Settings"):
            st.session_state.show_settings = True
            st.rerun()
        
        if st.button("🚪 Logout"):
            st.session_state.current_user = None
            st.session_state.current_event = None
            st.session_state.show_events = False
            st.query_params.clear()
            st.rerun()
    
    if st.session_state.show_events:
        render_events_list(st.session_state.data)
    else:
        render_landing_page(st.session_state.data)

elif st.session_state.current_user and st.session_state.current_event:
    # 4. Event Dashboard
    current_event = st.session_state.current_event
    
    # Sidebar Navigation
    with st.sidebar:
        if st.button("← Back to Events"):
            st.session_state.current_event = None
            st.rerun()
            
        st.divider()
        st.header(current_event['name'])
        st.caption(f"Code: {current_event['access_code']}")
        
        menu = st.radio(
            "Menu",
            ["📊 Dashboard", "➕ Add Expense", "📝 Edit Expenses", "💸 Settle Up", "📈 Analytics & Export", "🧠 AI Insights", "⚙️ Manage Event"]
        )
        
        st.divider()
        st.caption(f"Logged in as: {st.session_state.current_user}")

    # Main Content Area
    if menu == "📊 Dashboard":
        render_event_dashboard(current_event, st.session_state.data)
        
    elif menu == "➕ Add Expense":
        render_add_expense(current_event)
        
    elif menu == "📝 Edit Expenses":
        render_edit_expenses(current_event)
        
    elif menu == "💸 Settle Up":
        render_settle_expenses(current_event, st.session_state.data)
        
    elif menu == "📈 Analytics & Export":
        render_analytics(current_event)
        
    elif menu == "🧠 AI Insights":
        render_chatbot(current_event)
        
    elif menu == "⚙️ Manage Event":
        render_manage_event(current_event, st.session_state.data)
