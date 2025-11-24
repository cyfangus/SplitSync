import sqlite3
import json
from datetime import datetime

DB_PATH = "splitsync.db"

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            currency TEXT DEFAULT 'USD',
            access_code TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Event members table (many-to-many relationship)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_members (
            event_id TEXT,
            username TEXT,
            role TEXT DEFAULT 'member',
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
            PRIMARY KEY (event_id, username)
        )
    """)
    
    # Expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            original_amount REAL,
            original_currency TEXT,
            exchange_rate REAL,
            payer TEXT NOT NULL,
            category TEXT,
            date TEXT NOT NULL,
            settled INTEGER DEFAULT 0,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        )
    """)
    
    # Expense participants table (many-to-many)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expense_participants (
            expense_id INTEGER,
            username TEXT,
            FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE,
            PRIMARY KEY (expense_id, username)
        )
    """)
    
    # Settlements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            payer TEXT NOT NULL,
            recipient TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_currency TEXT,
            converted_amount REAL,
            exchange_rate REAL,
            date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def load_data():
    """Load all data in the format expected by the app."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Load users
    cursor.execute("SELECT * FROM users")
    users = []
    for row in cursor.fetchall():
        users.append({
            'username': row['username'],
            'email': row['email'],
            'password': row['password'],
            'avatar': row['avatar']
        })
    
    # Load events
    cursor.execute("SELECT * FROM events")
    events = []
    for event_row in cursor.fetchall():
        event_id = event_row['id']
        
        # Get members and roles
        cursor.execute("""
            SELECT username, role FROM event_members WHERE event_id = ?
        """, (event_id,))
        members = []
        roles = {}
        for member_row in cursor.fetchall():
            username = member_row['username']
            members.append(username)
            roles[username] = member_row['role']
        
        # Get expenses
        cursor.execute("""
            SELECT * FROM expenses WHERE event_id = ?
        """, (event_id,))
        expenses = []
        for expense_row in cursor.fetchall():
            expense_id = expense_row['id']
            
            # Get participants
            cursor.execute("""
                SELECT username FROM expense_participants WHERE expense_id = ?
            """, (expense_id,))
            involved = [p['username'] for p in cursor.fetchall()]
            
            expenses.append({
                'id': expense_id,
                'title': expense_row['title'],
                'amount': expense_row['amount'],
                'original_amount': expense_row['original_amount'],
                'original_currency': expense_row['original_currency'],
                'exchange_rate': expense_row['exchange_rate'],
                'payer': expense_row['payer'],
                'involved': involved,
                'category': expense_row['category'],
                'date': expense_row['date'],
                'settled': bool(expense_row['settled'])
            })
        
        # Get settlements
        cursor.execute("""
            SELECT * FROM settlements WHERE event_id = ?
        """, (event_id,))
        settlements = []
        for settlement_row in cursor.fetchall():
            settlements.append({
                'payer': settlement_row['payer'],
                'recipient': settlement_row['recipient'],
                'amount': settlement_row['amount'],
                'payment_currency': settlement_row['payment_currency'],
                'converted_amount': settlement_row['converted_amount'],
                'exchange_rate': settlement_row['exchange_rate'],
                'date': settlement_row['date'],
                'notes': settlement_row['notes']
            })
        
        events.append({
            'id': event_id,
            'name': event_row['name'],
            'members': members,
            'roles': roles,
            'currency': event_row['currency'],
            'access_code': event_row['access_code'],
            'expenses': expenses,
            'settlements': settlements if settlements else []
        })
    
    conn.close()
    
    return {'users': users, 'events': events}

def save_data(data):
    """Save all data to SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        cursor.execute("DELETE FROM expense_participants")
        cursor.execute("DELETE FROM expenses")
        cursor.execute("DELETE FROM settlements")
        cursor.execute("DELETE FROM event_members")
        cursor.execute("DELETE FROM events")
        cursor.execute("DELETE FROM users")
        
        # Save users
        for user in data.get('users', []):
            cursor.execute("""
                INSERT INTO users (username, email, password, avatar)
                VALUES (?, ?, ?, ?)
            """, (
                user['username'],
                user['email'],
                user['password'],
                user.get('avatar')
            ))
        
        # Save events
        for event in data.get('events', []):
            cursor.execute("""
                INSERT INTO events (id, name, currency, access_code)
                VALUES (?, ?, ?, ?)
            """, (
                event['id'],
                event['name'],
                event.get('currency', 'USD'),
                event.get('access_code')
            ))
            
            # Save event members
            for member in event.get('members', []):
                role = event.get('roles', {}).get(member, 'member')
                cursor.execute("""
                    INSERT INTO event_members (event_id, username, role)
                    VALUES (?, ?, ?)
                """, (event['id'], member, role))
            
            # Save expenses
            for expense in event.get('expenses', []):
                cursor.execute("""
                    INSERT INTO expenses (
                        event_id, title, amount, original_amount, original_currency,
                        exchange_rate, payer, category, date, settled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event['id'],
                    expense['title'],
                    expense['amount'],
                    expense.get('original_amount'),
                    expense.get('original_currency'),
                    expense.get('exchange_rate'),
                    expense['payer'],
                    expense.get('category'),
                    expense['date'],
                    1 if expense.get('settled', False) else 0
                ))
                
                expense_id = cursor.lastrowid
                
                # Save expense participants
                for participant in expense.get('involved', []):
                    cursor.execute("""
                        INSERT INTO expense_participants (expense_id, username)
                        VALUES (?, ?)
                    """, (expense_id, participant))
            
            # Save settlements
            for settlement in event.get('settlements', []):
                cursor.execute("""
                    INSERT INTO settlements (
                        event_id, payer, recipient, amount, payment_currency,
                        converted_amount, exchange_rate, date, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event['id'],
                    settlement['payer'],
                    settlement['recipient'],
                    settlement['amount'],
                    settlement.get('payment_currency'),
                    settlement.get('converted_amount'),
                    settlement.get('exchange_rate'),
                    settlement['date'],
                    settlement.get('notes')
                ))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
