from ui_utils import confirm_action, render_feedback_widget

# ... (rest of imports)

# ... (inside Dashboard / Event Selection sidebar)
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
            
        st.divider()
        render_feedback_widget()

# ... (inside Event Dashboard sidebar)
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
        
        st.divider()
        render_feedback_widget()

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
    /* Global Styles */
    .main {
        padding-top: 1rem;
    }
    
    /* Button Styling */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3.5em; /* Larger touch target */
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton>button:active {
        transform: scale(0.98);
    }
    
    /* Metric Cards */
    .stMetric {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #e9ecef;
    }
    
    /* Input Fields */
    .stTextInput>div>div>input {
        border-radius: 10px;
        padding: 0.5rem 1rem;
    }
    .stSelectbox>div>div>div {
        border-radius: 10px;
    }
    
    /* Mobile Optimizations */
    @media (max-width: 768px) {
        .main {
            padding-top: 0.5rem;
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        
        /* Stack columns on mobile */
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 auto !important;
            min-width: 100% !important;
        }
        
        /* Larger text for inputs to prevent zoom */
        input, select, textarea {
            font-size: 16px !important;
        }
        
        /* Hide sidebar toggle on very small screens if needed (optional) */
    }
    
    /* Dark mode adjustments */
    @media (prefers-color-scheme: dark) {
        .stMetric {
            background-color: #262730;
            border-color: #3d3f4b;
        }
        .stButton>button {
            border: 1px solid #4a4c5a;
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
    
    # Inject demo event if requested
    if st.session_state.get('demo_loaded', False):
        from onboarding import create_demo_event
        demo_event = create_demo_event()
        # Ensure 'events' list exists
        if 'events' not in st.session_state.data:
            st.session_state.data['events'] = []
        # Check if already exists to avoid duplicates
        if not any(e.get('id') == 'demo_event_001' for e in st.session_state.data['events']):
            st.session_state.data['events'].insert(0, demo_event)

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
