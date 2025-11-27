"""
UI Utilities for consistent user feedback
"""
import streamlit as st
import time

def show_success(message, duration=2):
    """Show a success message with auto-dismiss"""
    st.success(f"✅ {message}")
    
def show_error(message, help_text=None):
    """Show a user-friendly error message"""
    st.error(f"❌ {message}")
    if help_text:
        st.caption(f"💡 {help_text}")

def show_warning(message):
    """Show a warning message"""
    st.warning(f"⚠️ {message}")

def show_info(message):
    """Show an info message"""
    st.info(f"ℹ️ {message}")

def confirm_action(action_name, warning_message=None):
    """
    Create a confirmation dialog for destructive actions.
    Returns True if confirmed, False otherwise.
    
    Usage:
        if confirm_action("delete this expense", "This cannot be undone"):
            # perform delete
    """
    key = f"confirm_{action_name.replace(' ', '_')}"
    
    if key not in st.session_state:
        st.session_state[key] = False
    
    if not st.session_state[key]:
        col1, col2 = st.columns([3, 1])
        with col1:
            if warning_message:
                st.warning(f"⚠️ {warning_message}")
        with col2:
            if st.button(f"Confirm {action_name}", key=f"{key}_btn", type="primary"):
                st.session_state[key] = True
                st.rerun()
        return False
    else:
        # Reset after confirmation
        st.session_state[key] = False
        return True

def with_loading(message="Processing..."):
    """
    Decorator for functions that need loading state
    
    Usage:
        @with_loading("Saving data...")
        def save_data():
            # do work
            return result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with st.spinner(message):
                return func(*args, **kwargs)
        return wrapper
    return decorator

# Consistent error messages
ERROR_MESSAGES = {
    "db_connection": "Unable to connect to database. Please try again later.",
    "invalid_input": "Please check your input and try again.",
    "permission_denied": "You don't have permission to perform this action.",
    "not_found": "The requested item was not found.",
    "network_error": "Network error. Please check your connection.",
    "unknown": "Something went wrong. Please try again.",
}

def get_error_message(error_type, custom_message=None):
    """Get a user-friendly error message"""
    base_message = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["unknown"])
    if custom_message:
        return f"{base_message} Details: {custom_message}"
    return base_message
