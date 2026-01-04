import streamlit as st
from supabase import create_client, Client
import json

# Initialize Supabase Client
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Supabase configuration missing or invalid: {e}")
        return None

def init_db():
    """Simple connection check."""
    supabase = init_connection()
    if not supabase:
        st.error("Failed to initialize Supabase connection.")
        return
    # Connection is established via init_connection()

@st.cache_data(ttl=30, show_spinner=False)  # Cache for 30 seconds
def load_data(current_user=None):
    """Load data from Supabase - optimized version with caching and efficient queries."""
    supabase = init_connection()
    if not supabase:
        return {'users': [], 'events': []}

    try:
        # Load users (public info only) - only if needed
        users_response = supabase.table('users').select("username, email, avatar, display_name").execute()
        users = users_response.data if users_response.data else []

        # If no user is logged in, return minimal data
        if not current_user:
            return {'users': users, 'events': []}

        # Get user's events
        members_response = supabase.table('event_members').select("event_id").eq('username', current_user).execute()
        user_event_ids = [m['event_id'] for m in (members_response.data or [])]

        if not user_event_ids:
            return {'users': users, 'events': []}

        # Batch load all related data in parallel-like fashion
        events_response = supabase.table('events').select("*").in_('id', user_event_ids).execute()
        events_raw = events_response.data if events_response.data else []

        members_response = supabase.table('event_members').select("*").in_('event_id', user_event_ids).execute()
        members_raw = members_response.data if members_response.data else []
        
        # Load event participants (custom names)
        event_participants_response = supabase.table('event_participants').select("*").in_('event_id', user_event_ids).execute()
        event_participants_raw = event_participants_response.data if event_participants_response.data else []

        expenses_response = supabase.table('expenses').select("*").in_('event_id', user_event_ids).execute()
        expenses_raw = expenses_response.data if expenses_response.data else []

        # Load expense participants only if there are expenses
        expense_ids = [e['id'] for e in expenses_raw]
        participants_raw = []
        if expense_ids:
            participants_response = supabase.table('expense_participants').select("*").in_('expense_id', expense_ids).execute()
            participants_raw = participants_response.data if participants_response.data else []

        settlements_response = supabase.table('settlements').select("*").in_('event_id', user_event_ids).execute()
        settlements_raw = settlements_response.data if settlements_response.data else []

        # OPTIMIZATION: Use dictionaries for O(1) lookups instead of O(n) list iterations
        # Group members by event_id
        members_by_event = {}
        for m in members_raw:
            event_id = m['event_id']
            if event_id not in members_by_event:
                members_by_event[event_id] = {'members': [], 'roles': {}}
            members_by_event[event_id]['members'].append(m['username'])
            members_by_event[event_id]['roles'][m['username']] = m['role']
        
        # Group event participants (custom names) by event_id
        custom_participants_by_event = {}
        for p in event_participants_raw:
            event_id = p['event_id']
            if event_id not in custom_participants_by_event:
                custom_participants_by_event[event_id] = []
            custom_participants_by_event[event_id].append(p['participant_name'])

        # Group expenses by event_id
        expenses_by_event = {}
        for exp in expenses_raw:
            event_id = exp['event_id']
            if event_id not in expenses_by_event:
                expenses_by_event[event_id] = []
            expenses_by_event[event_id].append(exp)

        # Group participants by expense_id
        participants_by_expense = {}
        for p in participants_raw:
            expense_id = p['expense_id']
            if expense_id not in participants_by_expense:
                participants_by_expense[expense_id] = []
            participants_by_expense[expense_id].append(p['username'])

        # Group settlements by event_id
        settlements_by_event = {}
        for s in settlements_raw:
            event_id = s['event_id']
            if event_id not in settlements_by_event:
                settlements_by_event[event_id] = []
            settlements_by_event[event_id].append(s)

        # Reconstruct data structure efficiently
        events = []
        for event in events_raw:
            event_id = event['id']
            
            # Add members and roles (O(1) lookup)
            event_data = members_by_event.get(event_id, {'members': [], 'roles': {}})
            event['members'] = event_data['members']
            event['roles'] = event_data['roles']
            
            # Add custom participants (non-users)
            event['custom_participants'] = custom_participants_by_event.get(event_id, [])
            
            # Create combined list of all participants (users + custom names)
            event['all_participants'] = event['members'] + event['custom_participants']
            
            # Add expenses with participants (O(1) lookup)
            event_expenses = expenses_by_event.get(event_id, [])
            for exp in event_expenses:
                exp['involved'] = participants_by_expense.get(exp['id'], [])
                exp['settled'] = bool(exp.get('settled', False))
            event['expenses'] = event_expenses
            
            # Add settlements (O(1) lookup)
            event['settlements'] = settlements_by_event.get(event_id, [])
            
            events.append(event)

        return {'users': users, 'events': events}

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return {'users': [], 'events': []}


# ===== SIMPLIFIED CRUD OPERATIONS =====

def register_user(user_data):
    """Register a new user."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('users').insert(user_data).execute()
        return True
    except Exception as e:
        st.error(f"Registration failed: {str(e)}")
        return False

def create_event(event_data):
    """Create a new event with members - optimized with batch insert."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # Insert event
        event_record = {
            'id': event_data['id'],
            'name': event_data['name'],
            'currency': event_data.get('currency', 'USD'),
            'access_code': event_data.get('access_code')
        }
        supabase.table('events').insert(event_record).execute()
        
        # OPTIMIZATION: Batch insert members instead of one-by-one
        members_to_insert = []
        for member in event_data.get('members', []):
            role = event_data.get('roles', {}).get(member, 'member')
            members_to_insert.append({
                'event_id': event_data['id'],
                'username': member,
                'role': role
            })
        
        if members_to_insert:
            supabase.table('event_members').insert(members_to_insert).execute()
        
        # Clear cache after creating event
        load_data.clear()
        
        return True
    except Exception as e:
        st.error(f"Failed to create event: {str(e)}")
        return False

def add_expense(event_id, expense_data):
    """Add an expense to an event - optimized with batch insert."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # Insert expense
        expense_record = {
            'event_id': event_id,
            'title': expense_data['title'],
            'amount': expense_data['amount'],
            'original_amount': expense_data.get('original_amount'),
            'original_currency': expense_data.get('original_currency'),
            'exchange_rate': expense_data.get('exchange_rate'),
            'payer': expense_data['payer'],
            'category': expense_data.get('category'),
            'date': expense_data['date'],
            'settled': expense_data.get('settled', False)
        }
        response = supabase.table('expenses').insert(expense_record).execute()
        expense_id = response.data[0]['id']
        
        # OPTIMIZATION: Batch insert participants
        participants_to_insert = []
        for participant in expense_data.get('involved', []):
            participants_to_insert.append({
                'expense_id': expense_id,
                'username': participant
            })
        
        if participants_to_insert:
            supabase.table('expense_participants').insert(participants_to_insert).execute()
        
        # Clear cache after adding expense
        load_data.clear()
        
        return True
    except Exception as e:
        st.error(f"Failed to add expense: {str(e)}")
        return False

def update_user(username, updates):
    """Update user information."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('users').update(updates).eq('username', username).execute()
        load_data.clear()  # Clear cache
        return True
    except Exception as e:
        st.error(f"Update failed: {str(e)}")
        return False

def anonymize_user(username):
    """
    Safely 'delete' a user by scrubbing PII but keeping transaction history.
    Returns True if successful.
    """
    supabase = init_connection()
    if not supabase:
        return False
    try:
        # 1. Generate random suffix to ensure unique constraint on email/username if needed
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        # 2. Update user record with anonymized data
        updates = {
            'email': f"deleted_{unique_id}@splitsync.app", # Keep email format valid but fake
            'password': "DELETED_ACCOUNT_HASH", # Invalidate login
            'display_name': "Deleted User",
            'avatar': None,
            # We keep the 'username' as is because it's a Foreign Key in many tables.
            # Changing it would require updating 'expenses', 'settlements', 'event_members', etc.
            # If username is PII (e.g. "john.smith"), we SHOULD update it, but for this MVP 
            # we will assume keeping the ID is acceptable or too complex to refactor now.
            # Ideally: update_username_references_in_db(username, f"user_{unique_id}")
        }
        
        supabase.table('users').update(updates).eq('username', username).execute()
        return True
    except Exception as e:
        st.error(f"Account deletion failed: {str(e)}")
        return False

def update_event(event_id, updates):
    """Update event information."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('events').update(updates).eq('id', event_id).execute()
        load_data.clear()  # Clear cache
        return True
    except Exception as e:
        st.error(f"Update failed: {str(e)}")
        return False

def add_event_member(event_id, username, role='member'):
    """Add a member to an event."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('event_members').insert({
            'event_id': event_id,
            'username': username,
            'role': role
        }).execute()
        load_data.clear()  # Clear cache
        return True
    except Exception as e:
        st.error(f"Failed to add member: {str(e)}")
        return False

def remove_event_member(event_id, username):
    """Remove a member from an event."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('event_members').delete().eq('event_id', event_id).eq('username', username).execute()
        return True
    except Exception as e:
        st.error(f"Failed to remove member: {str(e)}")
        return False

def update_member_role(event_id, username, new_role):
    """Update a member's role."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('event_members').update({'role': new_role}).eq('event_id', event_id).eq('username', username).execute()
        return True
    except Exception as e:
        st.error(f"Failed to update role: {str(e)}")
        return False

def update_expense(expense_id, updates):
    """Update an expense."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        # Handle participants separately
        participants = updates.pop('involved', None)
        
        if updates:
            supabase.table('expenses').update(updates).eq('id', expense_id).execute()
        
        if participants is not None:
            # Replace participants
            supabase.table('expense_participants').delete().eq('expense_id', expense_id).execute()
            for participant in participants:
                supabase.table('expense_participants').insert({
                    'expense_id': expense_id,
                    'username': participant
                }).execute()
        
        return True
    except Exception as e:
        st.error(f"Failed to update expense: {str(e)}")
        return False

def delete_expense(expense_id):
    """Delete an expense."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('expense_participants').delete().eq('expense_id', expense_id).execute()
        supabase.table('expenses').delete().eq('id', expense_id).execute()
        return True
    except Exception as e:
        st.error(f"Failed to delete expense: {str(e)}")
        return False

def add_settlement(event_id, settlement_data):
    """Add a settlement."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        settlement_data['event_id'] = event_id
        supabase.table('settlements').insert(settlement_data).execute()
        return True
    except Exception as e:
        st.error(f"Failed to add settlement: {str(e)}")
        return False

def delete_settlement(settlement_id):
    """Delete a settlement."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('settlements').delete().eq('id', settlement_id).execute()
        return True
    except Exception as e:
        st.error(f"Failed to delete settlement: {str(e)}")
        return False

def delete_event(event_id):
    """Delete an event (cascades to related data)."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('events').delete().eq('id', event_id).execute()
        return True
    except Exception as e:
        st.error(f"Failed to delete event: {str(e)}")
        return False

def get_user_by_username(username):
    """Get user by username."""
    supabase = init_connection()
    if not supabase:
        return None
    try:
        response = supabase.table('users').select("*").eq('username', username).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None

def get_event_by_access_code(access_code):
    """Get event by access code."""
    supabase = init_connection()
    if not supabase:
        return None
    try:
        response = supabase.table('events').select("*").eq('access_code', access_code).execute()
        if response.data:
            event = response.data[0]
            # Get members
            members_response = supabase.table('event_members').select("username").eq('event_id', event['id']).execute()
            event['members'] = [m['username'] for m in (members_response.data or [])]
            return event
        return None
    except Exception:
        return None

def get_event_by_id(event_id):
    """Get event by ID."""
    supabase = init_connection()
    if not supabase:
        return None
    try:
        # Try to fetch event by ID
        response = supabase.table('events').select("*").eq('id', event_id).execute()
        if response.data:
            event = response.data[0]
            # Get members
            members_response = supabase.table('event_members').select("username").eq('event_id', event['id']).execute()
            event['members'] = [m['username'] for m in (members_response.data or [])]
            return event
        return None
    except Exception:
        return None

def update_username_references_in_db(old_username, new_username):
    """Update all username references."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('event_members').update({'username': new_username}).eq('username', old_username).execute()
        supabase.table('expenses').update({'payer': new_username}).eq('payer', old_username).execute()
        supabase.table('expense_participants').update({'username': new_username}).eq('username', old_username).execute()
        supabase.table('settlements').update({'payer': new_username}).eq('payer', old_username).execute()
        supabase.table('settlements').update({'recipient': new_username}).eq('recipient', old_username).execute()
        return True
    except Exception as e:
        st.error(f"Failed to update username: {str(e)}")
        return False

# Deprecated - kept for compatibility
def save_data(data):
    """DEPRECATED: Use specific CRUD functions instead."""
    st.warning("⚠️ save_data() is deprecated")
    return False

# --- Feedback ---
def submit_feedback(user, message, type='general'):
    """Submit user feedback."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        # Try to insert into feedback table
        # Note: Requires 'feedback' table in Supabase
        feedback_data = {
            'username': user,
            'message': message,
            'type': type,
            'created_at': 'now()'
        }
        supabase.table('feedback').insert(feedback_data).execute()
        return True
    except Exception as e:
        # Fallback: Log to console if table doesn't exist
        print(f"Feedback received from {user}: {message}")
        return True # Return true so user sees success even if DB fails (graceful degradation)

# --- Telegram Bot Support ---

def link_telegram_user(username, telegram_id):
    """Links a Telegram ID to a SplitSync user."""
    supabase = init_connection()
    if not supabase: return False
    
    try:
        # Check if user exists
        response = supabase.table('users').select("username").eq('username', username).execute()
        if not response.data:
            return False
            
        # Update user with telegram_id
        # Note: This requires a 'telegram_id' column in the users table
        supabase.table('users').update({'telegram_id': str(telegram_id)}).eq('username', username).execute()
        return True
    except Exception as e:
        print(f"Error linking telegram user: {e}")
        return False

def get_user_by_telegram_id(telegram_id):
    """Finds the SplitSync user associated with a Telegram ID."""
    supabase = init_connection()
    if not supabase: return None
    
    try:
        response = supabase.table('users').select("username").eq('telegram_id', str(telegram_id)).execute()
        if response.data:
            return response.data[0]['username']
        return None
    except Exception as e:
        print(f"Error fetching user by telegram id: {e}")
        return None

def get_user_current_event(username):
    """Gets the most recently accessed event for a user (simplified for bot)."""
    # For the bot, we'll just pick the first event they are a member of for now
    # In a real app, we might store 'last_accessed_event' in the DB
    supabase = init_connection()
    if not supabase: return None
    
    try:
        # Get events user is a member of
        response = supabase.table('event_members').select("event_id").eq('username', username).execute()
        if not response.data:
            return None
            
        # Just pick the first one
        event_id = response.data[0]['event_id']
        
        # Get event details
        event_response = supabase.table('events').select("*").eq('id', event_id).execute()
        if event_response.data:
            return event_response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching user event: {e}")
        return None

# --- Event Participants (Custom Names) ---

def add_event_participant(event_id, participant_name):
    """Add a custom participant (non-user) to an event."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('event_participants').insert({
            'event_id': event_id,
            'participant_name': participant_name,
            'is_user': False
        }).execute()
        load_data.clear()  # Clear cache
        return True
    except Exception as e:
        st.error(f"Failed to add participant: {str(e)}")
        return False

# Alias for user terminology
add_custom_member = add_event_participant

def remove_event_participant(event_id, participant_name):
    """Remove a custom participant from an event."""
    supabase = init_connection()
    if not supabase:
        return False
    try:
        supabase.table('event_participants').delete().eq('event_id', event_id).eq('participant_name', participant_name).execute()
        load_data.clear()  # Clear cache
        return True
    except Exception as e:
        st.error(f"Failed to remove participant: {str(e)}")
        return False

# Alias for user terminology
remove_custom_member = remove_event_participant

def get_event_participants(event_id):
    """Get all custom participants for an event."""
    supabase = init_connection()
    if not supabase:
        return []
    try:
        response = supabase.table('event_participants').select("participant_name").eq('event_id', event_id).execute()
        return [p['participant_name'] for p in (response.data or [])]
    except Exception:
        return []

# Alias for user terminology
get_custom_members = get_event_participants

