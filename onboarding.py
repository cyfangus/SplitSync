"""
Onboarding utilities for new users
"""
import streamlit as st
from datetime import datetime, timedelta
import random

def create_demo_event():
    """Create a demo event with sample data for new users"""
    current_user = st.session_state.get('current_user', 'You')
    
    demo_event = {
        "id": "demo_event_001",
        "name": "🎯 Demo: Weekend Trip",
        "members": [current_user, "Alice", "Bob", "Charlie"],
        "roles": {current_user: "admin", "Alice": "member", "Bob": "member", "Charlie": "member"},
        "currency": "USD",
        "access_code": "DEMO01",
        "expenses": [
            {
                "id": "demo_exp_1",
                "title": "Hotel Booking",
                "amount": 240.00,
                "payer": "You",
                "involved": ["You", "Alice", "Bob", "Charlie"],
                "date": str((datetime.now() - timedelta(days=2)).date()),
                "category": "🏠 Housing",
                "settled": False
            },
            {
                "id": "demo_exp_2",
                "title": "Dinner at Restaurant",
                "amount": 85.50,
                "payer": "Alice",
                "involved": ["You", "Alice", "Bob"],
                "date": str((datetime.now() - timedelta(days=1)).date()),
                "category": "🍔 Food & Dining  → Restaurant",
                "settled": False
            },
            {
                "id": "demo_exp_3",
                "title": "Gas for Road Trip",
                "amount": 45.00,
                "payer": "Bob",
                "involved": ["You", "Alice", "Bob", "Charlie"],
                "date": str(datetime.now().date()),
                "category": "🚗 Transportation  → Gas/Fuel",
                "settled": False
            },
            {
                "id": "demo_exp_4",
                "title": "Groceries",
                "amount": 32.75,
                "payer": "You",
                "involved": ["You", "Alice", "Bob", "Charlie"],
                "date": str(datetime.now().date()),
                "category": "🍔 Food & Dining  → Groceries",
                "settled": False
            }
        ],
        "settlements": [
            {
                "id": "demo_settle_1",
                "payer": "Charlie",
                "recipient": "You",
                "amount": 50.00,
                "date": str(datetime.now().date()),
                "notes": "Partial payment for hotel"
            }
        ]
    }
    return demo_event

def show_welcome_screen():
    """Display welcome screen for first-time users"""
    st.markdown("""
    <div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 15px; color: white;'>
        <h1 style='font-size: 3rem; margin-bottom: 0;'>👋 Welcome to SplitSync!</h1>
        <p style='font-size: 1.2rem; margin-top: 0.5rem;'>Your smart expense sharing companion</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background-color: #f8f9fa; border-radius: 10px; height: 200px;'>
            <div style='font-size: 3rem;'>💰</div>
            <h3>Track Expenses</h3>
            <p>Easily add and manage shared expenses with friends</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background-color: #f8f9fa; border-radius: 10px; height: 200px;'>
            <div style='font-size: 3rem;'>🤝</div>
            <h3>Split Bills</h3>
            <p>Automatically calculate who owes whom</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background-color: #f8f9fa; border-radius: 10px; height: 200px;'>
            <div style='font-size: 3rem;'>📊</div>
            <h3>Analyze Spending</h3>
            <p>Get insights with charts and AI-powered analytics</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Quick stats
    st.markdown("""
    ### ✨ What makes SplitSync special?
    
    - 🌍 **Multi-currency support** - Add expenses in any currency
    - 🤖 **AI-powered insights** - Ask questions about your spending
    - 📧 **Payment reminders** - Send friendly reminders via email
    - 📱 **Smart categorization** - Auto-categorize expenses
    - 🔒 **Secure & private** - Your data is protected
    """)
    
    st.divider()
    
    # Call to action
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Start Interactive Tutorial", type="primary", use_container_width=True):
            st.session_state.show_tutorial = True
            st.session_state.tutorial_step = 0
            st.rerun()
        
        if st.button("📝 Skip to Dashboard", use_container_width=True):
            st.session_state.onboarding_complete = True
            st.rerun()

def show_tutorial_step(step):
    """Display interactive tutorial steps"""
    
    total_steps = 5
    progress = (step + 1) / total_steps
    
    st.progress(progress)
    st.caption(f"Step {step + 1} of {total_steps}")
    
    if step == 0:
        st.markdown("""
        ## 📚 Step 1: Understanding Events
        
        In SplitSync, an **Event** is a group where you track shared expenses.
        
        ### Examples of Events:
        - 🏖️ Weekend trip with friends
        - 🏠 Shared apartment expenses
        - 🎉 Birthday party costs
        - ✈️ Vacation with family
        
        Each event has:
        - **Members**: People who share expenses
        - **Currency**: The main currency for the event
        - **Access Code**: To invite others
        
        💡 **Tip**: You can be part of multiple events at once!
        """)
        
    elif step == 1:
        st.markdown("""
        ## ➕ Step 2: Adding Expenses
        
        Adding an expense is super easy:
        
        1. **Description**: What did you buy? (e.g., "Dinner at Pizza Place")
        2. **Amount**: How much did it cost?
        3. **Paid By**: Who paid for it?
        4. **Split Among**: Who should share the cost?
        
        ### Cool Features:
        - 🧮 **Formula Support**: Type `12.50 * 3 + 5` instead of calculating manually
        - 💱 **Currency Conversion**: Add expenses in any currency
        - 🤖 **Smart Categories**: We auto-categorize based on description
        
        💡 **Tip**: You can edit or delete expenses anytime!
        """)
        
    elif step == 2:
        st.markdown("""
        ## 💸 Step 3: Settling Up
        
        SplitSync automatically calculates who owes whom!
        
        ### How it works:
        1. We track all expenses and who paid
        2. We calculate each person's share
        3. We simplify debts (minimize transactions)
        
        ### Example:
        - Alice paid $60 for dinner (split 3 ways = $20 each)
        - You owe Alice $20
        - Bob owes Alice $20
        
        ### Recording Payments:
        When someone pays you back:
        1. Go to "💸 Settle Up"
        2. Record the payment
        3. We'll update the balances automatically
        
        💡 **Tip**: Send payment reminders via email!
        """)
        
    elif step == 3:
        st.markdown("""
        ## 📊 Step 4: Analytics & Insights
        
        Understand your spending with powerful analytics:
        
        ### Available Charts:
        - 🥧 **Spending by Category**: See where your money goes
        - 📊 **Spending by Member**: Who spent the most?
        - 📈 **Spending Over Time**: Track trends
        
        ### AI Chatbot:
        Ask questions like:
        - "How much did I spend on food?"
        - "Who owes me the most?"
        - "What's my biggest expense category?"
        
        ### Export Options:
        - 📄 **CSV**: For Excel/Google Sheets
        - 📑 **PDF**: Professional reports
        
        💡 **Tip**: Use filters to analyze specific time periods!
        """)
        
    elif step == 4:
        st.markdown("""
        ## 🎯 Step 5: Try the Demo!
        
        We've created a **demo event** with sample data so you can explore all features risk-free!
        
        ### What's included:
        - ✅ Sample expenses (hotel, dinner, gas, groceries)
        - ✅ Multiple members (You, Alice, Bob, Charlie)
        - ✅ A recorded payment
        - ✅ All features unlocked
        
        ### You can:
        - View the dashboard and charts
        - Add/edit/delete expenses
        - Record settlements
        - Try the AI chatbot
        - Explore analytics
        
        **Don't worry** - This is just demo data. You can delete it anytime and create real events!
        
        💡 **Ready to explore?** Click "Load Demo Event" below!
        """)
    
    # Navigation buttons
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if step > 0:
            if st.button("⬅️ Previous", use_container_width=True):
                st.session_state.tutorial_step = step - 1
                st.rerun()
    
    with col2:
        if st.button("⏭️ Skip Tutorial", use_container_width=True):
            st.session_state.show_tutorial = False
            st.session_state.onboarding_complete = True
            st.rerun()
    
    with col3:
        if step < total_steps - 1:
            if st.button("Next ➡️", type="primary", use_container_width=True):
                st.session_state.tutorial_step = step + 1
                st.rerun()
        else:
            if st.button("🎯 Load Demo Event", type="primary", use_container_width=True):
                st.session_state.demo_loaded = True
                st.session_state.show_tutorial = False
                st.session_state.onboarding_complete = True
                st.toast("🎉 Demo event loaded! Explore the features.", icon="🎯")
                st.rerun()

def check_if_new_user(data):
    """Check if user is new (no events)"""
    if not data.get('events'):
        return True
    return False

def should_show_onboarding():
    """Determine if onboarding should be shown"""
    # Check if user has completed onboarding
    if st.session_state.get('onboarding_complete', False):
        return False
    
    # Check if user has any events (excluding demo)
    if st.session_state.get('data'):
        real_events = [e for e in st.session_state.data.get('events', []) 
                      if e.get('id') != 'demo_event_001']
        if real_events:
            st.session_state.onboarding_complete = True
            return False
    
    return True
