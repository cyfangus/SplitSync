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
    """
    Supabase tables should be created via the SQL Editor using schema.sql.
    This function is a placeholder or could check connection.
    """
    supabase = init_connection()
    if not supabase:
        return
    # Optional: Simple health check
    # supabase.table('users').select("count", count='exact').execute()

def load_data(current_user=None):
    """Load all data from Supabase and reconstruct the app's expected structure.
    
    Args:
        current_user: Username of the logged-in user. If provided, only loads their events.
    """
    supabase = init_connection()
    if not supabase:
        return {'users': [], 'events': []}

    try:
        # 1. Load Users (needed for lookups, but filter sensitive data)
        response = supabase.table('users').select("username, email, avatar").execute()
        users = response.data

        # 2. Load Events - Filter by current user if logged in
        if current_user:
            # First, get event IDs where user is a member
            response = supabase.table('event_members').select("event_id").eq('username', current_user).execute()
            user_event_ids = [m['event_id'] for m in response.data]
            
            if user_event_ids:
                # Load only events the user is a member of
                response = supabase.table('events').select("*").in_('id', user_event_ids).execute()
                events_raw = response.data
            else:
                events_raw = []
        else:
            # Not logged in, return empty events
            events_raw = []

        # 3. Load Event Members (only for user's events)
        if current_user and user_event_ids:
            response = supabase.table('event_members').select("*").in_('event_id', user_event_ids).execute()
            members_raw = response.data
        else:
            members_raw = []

        # 4. Load Expenses (only for user's events)
        if current_user and user_event_ids:
            response = supabase.table('expenses').select("*").in_('event_id', user_event_ids).execute()
            expenses_raw = response.data
        else:
            expenses_raw = []

        # 5. Load Expense Participants (only for user's events)
        if expenses_raw:
            expense_ids = [e['id'] for e in expenses_raw]
            response = supabase.table('expense_participants').select("*").in_('expense_id', expense_ids).execute()
            participants_raw = response.data
        else:
            participants_raw = []

        # 6. Load Settlements (only for user's events)
        if current_user and user_event_ids:
            response = supabase.table('settlements').select("*").in_('event_id', user_event_ids).execute()
            settlements_raw = response.data
        else:
            settlements_raw = []

        # --- Reconstruct Data Structure ---
        
        # Helper: Group members by event
        members_by_event = {}
        roles_by_event = {}
        for m in members_raw:
            eid = m['event_id']
            if eid not in members_by_event:
                members_by_event[eid] = []
                roles_by_event[eid] = {}
            members_by_event[eid].append(m['username'])
            roles_by_event[eid][m['username']] = m['role']

        # Helper: Group participants by expense
        participants_by_expense = {}
        for p in participants_raw:
            xid = p['expense_id']
            if xid not in participants_by_expense:
                participants_by_expense[xid] = []
            participants_by_expense[xid].append(p['username'])

        # Helper: Group expenses by event
        expenses_by_event = {}
        for exp in expenses_raw:
            eid = exp['event_id']
            if eid not in expenses_by_event:
                expenses_by_event[eid] = []
            
            # Attach participants
            exp['involved'] = participants_by_expense.get(exp['id'], [])
            # Ensure settled is boolean
            exp['settled'] = bool(exp['settled'])
            
            expenses_by_event[eid].append(exp)

        # Helper: Group settlements by event
        settlements_by_event = {}
        for s in settlements_raw:
            eid = s['event_id']
            if eid not in settlements_by_event:
                settlements_by_event[eid] = []
            settlements_by_event[eid].append(s)

        # Build final Events list
        events = []
        for evt in events_raw:
            evt_id = evt['id']
            evt['members'] = members_by_event.get(evt_id, [])
            evt['roles'] = roles_by_event.get(evt_id, {})
            evt['expenses'] = expenses_by_event.get(evt_id, [])
            evt['settlements'] = settlements_by_event.get(evt_id, [])
            events.append(evt)

        return {'users': users, 'events': events}

    except Exception as e:
        st.error(f"Error loading data from Supabase: {e}")
        return {'users': [], 'events': []}

# ===== NEW: Individual CRUD Operations =====

def create_event(event_data):
    """Create a new event without affecting other data.
    
    Args:
        event_data: Dict with keys: id, name, members, roles, currency, access_code
    """
    supabase = init_connection()
    if not supabase:
        st.error("❌ Database connection failed")
        return False
    
    try:
        # Insert event
        event_insert = {
            'id': event_data['id'],
            'name': event_data['name'],
            'currency': event_data.get('currency', 'USD'),
            'access_code': event_data.get('access_code')
        }
        
        response = supabase.table('events').insert(event_insert).execute()
        
        if not response.data:
            st.error(f"❌ Failed to insert event into database")
            return False
        
        # Insert event members
        for member in event_data.get('members', []):
            role = event_data.get('roles', {}).get(member, 'member')
            member_insert = {
                'event_id': event_data['id'],
                'username': member,
                'role': role
            }
            supabase.table('event_members').insert(member_insert).execute()
        
        return True
    except Exception as e:
        st.error(f"❌ Error creating event: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
        return False

def update_event(event_id, updates):
    """Update an existing event.
    
    Args:
        event_id: Event ID
        updates: Dict of fields to update (name, currency, etc.)
    """
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        supabase.table('events').update(updates).eq('id', event_id).execute()
        return True
    except Exception as e:
        st.error(f"Error updating event: {e}")
        return False

def add_expense(event_id, expense_data):
    """Add an expense to an event.
    
    Args:
        event_id: Event ID
        expense_data: Dict with expense details
    """
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # Insert expense
        response = supabase.table('expenses').insert({
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
        }).execute()
        
        # Get the inserted expense ID
        expense_id = response.data[0]['id']
        
        # Insert participants
        for participant in expense_data.get('involved', []):
            supabase.table('expense_participants').insert({
                'expense_id': expense_id,
                'username': participant
            }).execute()
        
        return True
    except Exception as e:
        st.error(f"Error adding expense: {e}")
        return False

def save_data(data):
    """
    DEPRECATED: Use individual CRUD functions instead.
    This function is kept for backward compatibility but should not be used.
    """
    st.warning("⚠️ save_data() is deprecated. Use create_event(), add_expense(), etc. instead.")
    return False
