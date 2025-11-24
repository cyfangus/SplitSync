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

def load_data():
    """Load all data from Supabase and reconstruct the app's expected structure."""
    supabase = init_connection()
    if not supabase:
        return {'users': [], 'events': []}

    try:
        # 1. Load Users
        response = supabase.table('users').select("*").execute()
        users = response.data

        # 2. Load Events
        response = supabase.table('events').select("*").execute()
        events_raw = response.data

        # 3. Load Event Members
        response = supabase.table('event_members').select("*").execute()
        members_raw = response.data

        # 4. Load Expenses
        response = supabase.table('expenses').select("*").execute()
        expenses_raw = response.data

        # 5. Load Expense Participants
        response = supabase.table('expense_participants').select("*").execute()
        participants_raw = response.data

        # 6. Load Settlements
        response = supabase.table('settlements').select("*").execute()
        settlements_raw = response.data

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

def save_data(data):
    """
    Save data to Supabase.
    Strategy: Delete all records and re-insert.
    Note: In a high-concurrency production app, this is bad practice.
    For a personal app, it ensures consistency without complex diffing logic.
    """
    supabase = init_connection()
    if not supabase:
        return

    try:
        # --- 1. Clear Tables (Order matters due to Foreign Keys) ---
        # Delete from child tables first
        supabase.table('expense_participants').delete().neq('username', 'placeholder_impossible_value').execute()
        supabase.table('settlements').delete().neq('id', -1).execute()
        supabase.table('expenses').delete().neq('id', -1).execute()
        supabase.table('event_members').delete().neq('event_id', 'placeholder').execute()
        supabase.table('events').delete().neq('id', 'placeholder').execute()
        supabase.table('users').delete().neq('username', 'placeholder').execute()

        # --- 2. Insert Users ---
        if data.get('users'):
            supabase.table('users').insert(data['users']).execute()

        # --- 3. Insert Events ---
        events_to_insert = []
        members_to_insert = []
        expenses_to_insert = []
        settlements_to_insert = []
        
        # We need to track expense IDs to map participants later
        # Since we are re-inserting, we lose original IDs unless we kept them.
        # The app's 'id' for expenses is usually an integer.
        # Let's assume the app manages IDs or we let DB generate them.
        # Wait, if we let DB generate IDs, we lose the link to participants if we don't get them back.
        # CRITICAL: The app's internal state has IDs. We should try to preserve them if possible,
        # OR we insert expenses one by one and get the ID back.
        
        # For this implementation, let's try to insert expenses one by one to handle IDs correctly
        # OR, since we cleared the table, we can just re-insert with the SAME IDs if the DB allows identity insert.
        # Postgres 'generated by default as identity' allows inserting explicit values.
        
        for evt in data.get('events', []):
            # Event
            events_to_insert.append({
                'id': evt['id'],
                'name': evt['name'],
                'currency': evt.get('currency', 'USD'),
                'access_code': evt.get('access_code')
            })
            
            # Members
            for member in evt.get('members', []):
                role = evt.get('roles', {}).get(member, 'member')
                members_to_insert.append({
                    'event_id': evt['id'],
                    'username': member,
                    'role': role
                })
            
            # Settlements
            for s in evt.get('settlements', []):
                # Remove 'id' if it exists to let DB generate new one, or keep it?
                # Settlements don't have dependencies, so new IDs are fine.
                s_clean = s.copy()
                if 'id' in s_clean: del s_clean['id']
                s_clean['event_id'] = evt['id']
                settlements_to_insert.append(s_clean)

        # Batch Insert Events & Members
        if events_to_insert:
            supabase.table('events').insert(events_to_insert).execute()
        if members_to_insert:
            supabase.table('event_members').insert(members_to_insert).execute()
        if settlements_to_insert:
            supabase.table('settlements').insert(settlements_to_insert).execute()

        # Expenses & Participants (Complex due to ID mapping)
        # We will insert expenses one by one or in batches if we trust the IDs.
        # If the app's IDs are unique integers, we can insert them directly.
        
        all_participants = []
        
        for evt in data.get('events', []):
            for exp in evt.get('expenses', []):
                exp_data = {
                    'id': exp['id'], # Force the ID from the app state
                    'event_id': evt['id'],
                    'title': exp['title'],
                    'amount': exp['amount'],
                    'original_amount': exp.get('original_amount'),
                    'original_currency': exp.get('original_currency'),
                    'exchange_rate': exp.get('exchange_rate'),
                    'payer': exp['payer'],
                    'category': exp.get('category'),
                    'date': exp['date'],
                    'settled': exp.get('settled', False)
                }
                expenses_to_insert.append(exp_data)
                
                for p in exp.get('involved', []):
                    all_participants.append({
                        'expense_id': exp['id'],
                        'username': p
                    })

        if expenses_to_insert:
            supabase.table('expenses').insert(expenses_to_insert).execute()
        
        if all_participants:
            supabase.table('expense_participants').insert(all_participants).execute()

    except Exception as e:
        st.error(f"Error saving to Supabase: {e}")
