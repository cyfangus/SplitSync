"""
Input validation utilities for real-time feedback
"""
import streamlit as st
import re

def validate_email(email):
    """
    Validate email format and provide real-time feedback.
    Returns (is_valid, message)
    """
    if not email:
        return False, ""
    
    # Basic email regex
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if re.match(pattern, email):
        return True, "✅ Valid email format"
    else:
        return False, "❌ Invalid email format (e.g., user@example.com)"

def validate_username(username, existing_usernames=None):
    """
    Validate username and check availability.
    Returns (is_valid, message, availability_status)
    """
    if not username:
        return False, "", None
    
    # Check length
    if len(username) < 3:
        return False, "❌ Username must be at least 3 characters", None
    
    # Check characters
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "❌ Only letters, numbers, and underscores allowed", None
    
    # Check availability if list provided
    if existing_usernames is not None:
        if username in existing_usernames:
            return False, "❌ Username already taken", False
        else:
            return True, "✅ Username available!", True
    
    return True, "✅ Valid username format", None

def validate_password_strength(password):
    """
    Validate password and show strength indicator.
    Returns (is_valid, message, strength_score)
    """
    if not password:
        return False, "", 0
    
    score = 0
    feedback = []
    
    # Length check
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("At least 8 characters")
    
    # Uppercase check
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        feedback.append("One uppercase letter")
    
    # Lowercase check
    if re.search(r'[a-z]', password):
        score += 1
    else:
        feedback.append("One lowercase letter")
    
    # Number check
    if re.search(r'[0-9]', password):
        score += 1
    else:
        feedback.append("One number")
    
    # Special char check
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        feedback.append("One special character")
    
    # Determine strength
    if score == 5:
        return True, "✅ Strong password!", score
    elif score >= 3:
        return False, f"⚠️ Weak. Add: {', '.join(feedback)}", score
    else:
        return False, f"❌ Too weak. Need: {', '.join(feedback)}", score

def validate_amount(amount_str):
    """
    Validate amount input (must be positive number).
    Returns (is_valid, parsed_value, message)
    """
    if not amount_str:
        return False, 0.0, ""
    
    try:
        amount = float(amount_str)
        if amount <= 0:
            return False, amount, "❌ Amount must be greater than 0"
        elif amount > 1000000:
            return False, amount, "⚠️ Amount seems unusually large"
        else:
            return True, amount, f"✅ ${amount:,.2f}"
    except ValueError:
        return False, 0.0, "❌ Please enter a valid number"

def show_password_strength_meter(password):
    """Display a visual password strength meter"""
    is_valid, message, score = validate_password_strength(password)
    
    if not password:
        return
    
    # Color based on strength
    if score >= 4:
        color = "green"
        strength = "Strong"
    elif score >= 3:
        color = "orange"
        strength = "Medium"
    else:
        color = "red"
        strength = "Weak"
    
    # Progress bar
    progress = score / 5.0
    st.progress(progress)
    
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(f"**Strength:** <span style='color:{color}'>{strength}</span>", unsafe_allow_html=True)
    with col2:
        if is_valid:
            st.success(message)
        else:
            st.warning(message)

def validate_event_name(name):
    """Validate event name"""
    if not name:
        return False, ""
    
    if len(name) < 3:
        return False, "❌ Event name must be at least 3 characters"
    
    if len(name) > 50:
        return False, "❌ Event name too long (max 50 characters)"
    
    return True, "✅ Valid event name"
