"""
Utility functions for SplitSync
Extracted for testability
"""
import bcrypt
import re


def hash_password(password):
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password, hashed):
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def validate_password(password):
    """
    Validate password strength.
    Returns (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, ""


def calculate_debts(expenses, members):
    """
    Calculate who owes whom based on expenses.
    Returns list of debts: [{'debtor': str, 'creditor': str, 'amount': float}]
    """
    # Filter out settled expenses
    unsettled = [e for e in expenses if not e.get('settled', False)]
    
    if not unsettled:
        return []
    
    # Calculate balances for each member
    balances = {member: 0.0 for member in members}
    
    for expense in unsettled:
        payer = expense['payer']
        amount = expense['amount']
        involved = expense.get('involved', members)
        
        if not involved:
            involved = members
        
        # Split amount equally among involved members
        split_amount = amount / len(involved)
        
        # Payer gets credited
        balances[payer] += amount
        
        # Each involved member gets debited their share
        for person in involved:
            balances[person] -= split_amount
    
    # Convert balances to debts
    debts = []
    creditors = [(person, bal) for person, bal in balances.items() if bal > 0.01]
    debtors = [(person, -bal) for person, bal in balances.items() if bal < -0.01]
    
    # Match debtors with creditors
    for debtor, debt_amount in debtors:
        for creditor, credit_amount in creditors:
            if debt_amount > 0.01 and credit_amount > 0.01:
                payment = min(debt_amount, credit_amount)
                debts.append({
                    'debtor': debtor,
                    'creditor': creditor,
                    'amount': round(payment, 2)
                })
                debt_amount -= payment
                credit_amount -= payment
                # Update the creditor's remaining credit
                creditors = [(c, amt - payment if c == creditor else amt) 
                            for c, amt in creditors]
    
    return debts


def calculate_settlements(debts):
    """
    Convert debts into settlement instructions.
    Returns list of settlements: [{'from_user': str, 'to_user': str, 'amount': float}]
    """
    if not debts:
        return []
    
    # For now, just convert debts to settlements directly
    # A more sophisticated algorithm could minimize the number of transactions
    settlements = []
    for debt in debts:
        settlements.append({
            'from_user': debt['debtor'],
            'to_user': debt['creditor'],
            'amount': debt['amount']
        })
    
    return settlements
