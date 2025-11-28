"""
Subscription and freemium limit management for SplitSync.
"""
import streamlit as st
from datetime import datetime

# Freemium Limits
FREE_LIMITS = {
    'max_events': 3,
    'max_expenses_per_event': 50,
    'ai_insights': False,  # Free users can't use AI
    'advanced_analytics': False,
    'export_formats': ['CSV'],  # Pro gets PDF too
}

PRO_LIMITS = {
    'max_events': float('inf'),  # Unlimited
    'max_expenses_per_event': float('inf'),
    'ai_insights': True,
    'advanced_analytics': True,
    'export_formats': ['CSV', 'PDF'],
}

def get_user_tier(user_data):
    """Get the subscription tier for a user."""
    if not user_data:
        return 'free'
    
    tier = user_data.get('subscription_tier', 'free')
    
    # Check if pro subscription has expired
    if tier == 'pro':
        expires_at = user_data.get('subscription_expires_at')
        if expires_at:
            # Parse the timestamp (Supabase returns ISO format)
            if isinstance(expires_at, str):
                from dateutil import parser
                expires_at = parser.parse(expires_at)
            
            if datetime.now(expires_at.tzinfo) > expires_at:
                return 'free'  # Expired
    
    return tier

def get_limits(tier):
    """Get limits for a given tier."""
    return PRO_LIMITS if tier == 'pro' else FREE_LIMITS

def is_pro(user_data):
    """Check if user is a pro subscriber."""
    return get_user_tier(user_data) == 'pro'

def can_create_event(user_data, current_events_count):
    """Check if user can create another event."""
    tier = get_user_tier(user_data)
    limits = get_limits(tier)
    return current_events_count < limits['max_events']

def can_add_expense(user_data, event):
    """Check if user can add another expense to an event."""
    tier = get_user_tier(user_data)
    limits = get_limits(tier)
    current_count = len(event.get('expenses', []))
    return current_count < limits['max_expenses_per_event']

def can_use_ai(user_data):
    """Check if user can use AI insights."""
    tier = get_user_tier(user_data)
    limits = get_limits(tier)
    return limits['ai_insights']

def show_upgrade_prompt(feature_name, location="inline"):
    """Show an upgrade prompt to the user."""
    if location == "inline":
        st.warning(f"🔒 **{feature_name}** is a Pro feature. Upgrade to unlock!")
        if st.button("⭐ Upgrade to Pro", key=f"upgrade_{feature_name}"):
            st.session_state.show_upgrade_modal = True
            st.rerun()
    elif location == "banner":
        st.info(f"💡 Upgrade to Pro to unlock **{feature_name}** and more!")
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button("⭐ See Pro Features", use_container_width=True):
                st.session_state.show_upgrade_modal = True
                st.rerun()

def show_limit_reached(limit_type, current, max_allowed):
    """Show a message when a limit is reached."""
    st.error(f"🚫 **Free Tier Limit Reached**: You have {current}/{max_allowed} {limit_type}.")
    st.info("💡 Upgrade to Pro for unlimited access!")
    if st.button("⭐ Upgrade to Pro", key=f"limit_{limit_type}"):
        st.session_state.show_upgrade_modal = True
        st.rerun()

def render_upgrade_modal():
    """Render the upgrade modal/page."""
    st.title("⭐ Upgrade to SplitSync Pro")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Free")
        st.markdown("""
        - ✅ 3 active events
        - ✅ 50 expenses per event
        - ✅ Basic analytics
        - ✅ Manual settlements
        - ✅ Standard support
        """)
    
    with col2:
        st.subheader("⭐ Pro - $4.99/month")
        st.markdown("""
        - ✅ **Unlimited events**
        - ✅ **Unlimited expenses**
        - ✅ **Advanced analytics**
        - ✅ **AI Insights (unlimited)**
        - ✅ **Priority support**
        - ✅ **Export to PDF**
        """)
        
        st.divider()
        
        if st.button("🚀 Upgrade Now", type="primary", use_container_width=True):
            # TODO: Redirect to Stripe checkout
            st.info("🚧 Stripe integration coming soon! For now, contact support to upgrade.")
    
    st.divider()
    
    if st.button("← Back"):
        st.session_state.show_upgrade_modal = False
        st.rerun()

def get_pro_badge():
    """Return a Pro badge HTML."""
    return """
    <span style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: bold;
        margin-left: 8px;
    ">PRO</span>
    """
