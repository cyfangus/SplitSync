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
        st.error("Failed to initialize Supabase connection.")
        return
    
    # Simple health check
    try:
        # Try to select 1 row from users to verify connection
        # We use count to be efficient and avoid data leakage if RLS is weird
        response = supabase.table('users').select("count", count='exact').limit(1).execute()
        # st.success("Database connection established.") 
    except Exception as e:
        st.error(f"Database health check failed: {e}")
        if "relation \"public.users\" does not exist" in str(e):
             st.error("The 'users' table does not exist. Please run schema.sql in Supabase SQL Editor.")

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
        members_inserted = 0
        for member in event_data.get('members', []):
            role = event_data.get('roles', {}).get(member, 'member')
            member_insert = {
                'event_id': event_data['id'],
                'username': member,
                'role': role
            }
            try:
                member_response = supabase.table('event_members').insert(member_insert).execute()
                if member_response.data:
                    members_inserted += 1
                else:
                    st.warning(f"⚠️ Failed to add member {member} to event")
            except Exception as member_error:
                st.error(f"❌ Error adding member {member}: {str(member_error)}")
        
        if members_inserted == 0:
            st.error("❌ Event created but no members were added. This will cause the event to not appear in your list.")
            return False
        
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

# ===== User Operations =====

def register_user(user_data):
    """Register a new user."""
    supabase = init_connection()
    if not supabase:
        st.error("Database connection failed during registration.")
        return False
    
    try:
        response = supabase.table('users').insert(user_data).execute()
        return True
    except Exception as e:
        st.error(f"Error registering user: {e}")
        return False

def update_user(username, updates):
    """Update user information."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        supabase.table('users').update(updates).eq('username', username).execute()
        return True
    except Exception as e:
        st.error(f"Error updating user: {e}")
        return False

def delete_user(username):
    """Delete a user."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        supabase.table('users').delete().eq('username', username).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting user: {e}")
        return False

# ===== Event Member Operations =====

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
        return True
    except Exception as e:
        st.error(f"Error adding member: {e}")
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
        st.error(f"Error removing member: {e}")
        return False

def update_member_role(event_id, username, new_role):
    """Update a member's role in an event."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        supabase.table('event_members').update({'role': new_role}).eq('event_id', event_id).eq('username', username).execute()
        return True
    except Exception as e:
        st.error(f"Error updating role: {e}")
        return False

# ===== Expense Operations =====

def update_expense(expense_id, updates):
    """Update an expense."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # Separate participants from other updates
        participants = updates.pop('involved', None)
        
        if updates:
            supabase.table('expenses').update(updates).eq('id', expense_id).execute()
        
        if participants is not None:
            # Update participants: Delete old, insert new
            supabase.table('expense_participants').delete().eq('expense_id', expense_id).execute()
            
            for participant in participants:
                supabase.table('expense_participants').insert({
                    'expense_id': expense_id,
                    'username': participant
                }).execute()
            
        return True
    except Exception as e:
        st.error(f"Error updating expense: {e}")
        return False

def delete_expense(expense_id):
    """Delete an expense."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # Delete participants first (foreign key)
        supabase.table('expense_participants').delete().eq('expense_id', expense_id).execute()
        # Delete expense
        supabase.table('expenses').delete().eq('id', expense_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting expense: {e}")
        return False

# ===== Settlement Operations =====

def add_settlement(event_id, settlement_data):
    """Add a settlement to an event."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        settlement_data['event_id'] = event_id
        supabase.table('settlements').insert(settlement_data).execute()
        return True
    except Exception as e:
        st.error(f"Error adding settlement: {e}")
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
        st.error(f"Error deleting settlement: {e}")
        return False

# ===== Event Operations =====

def delete_event(event_id):
    """Delete an event and all related data."""
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # Foreign keys will cascade delete related data
        supabase.table('events').delete().eq('id', event_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting event: {e}")
        return False

# ===== Helper Functions =====

def get_user_by_username(username):
    """Get user details by username."""
    supabase = init_connection()
    if not supabase:
        return None
    try:
        response = supabase.table('users').select("*").eq('username', username).execute()
        return response.data[0] if response.data else None
    except Exception:
        return None

def get_event_by_access_code(access_code):
    """Get event details by access code."""
    supabase = init_connection()
    if not supabase:
        return None
    try:
        response = supabase.table('events').select("*").eq('access_code', access_code).execute()
        if response.data:
            event = response.data[0]
            # Fetch members for this event to be consistent with app expectation
            members_response = supabase.table('event_members').select("username").eq('event_id', event['id']).execute()
            event['members'] = [m['username'] for m in members_response.data]
            return event
        return None
    except Exception:
        return None

def update_username_references_in_db(old_username, new_username):
    """
    Update all references to a username in the database.
    Note: Since FKs are not ON UPDATE CASCADE, we must do this manually.
    This is risky without transactions.
    """
    supabase = init_connection()
    if not supabase:
        return False
    
    try:
        # 1. Event Members
        supabase.table('event_members').update({'username': new_username}).eq('username', old_username).execute()
        
        # 2. Expenses (payer)
        supabase.table('expenses').update({'payer': new_username}).eq('payer', old_username).execute()
        
        # 3. Expense Participants
        supabase.table('expense_participants').update({'username': new_username}).eq('username', old_username).execute()
        
        # 4. Settlements (payer)
        supabase.table('settlements').update({'payer': new_username}).eq('payer', old_username).execute()
        
        # 5. Settlements (recipient)
        supabase.table('settlements').update({'recipient': new_username}).eq('recipient', old_username).execute()
        
        return True
    except Exception as e:
        st.error(f"Error updating username references: {e}")
        return False
