"""
Utility functions for SplitSync
Extracted for testability and reusability
"""
import bcrypt
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import streamlit as st

# --- Auth Utilities (Keep here for backward compatibility or move to auth.py completely) ---
# For now, we'll import from auth.py if needed, or just keep them here if they are used by other utils.
# But the plan was to move them to auth.py. I will remove them from here if I can, but to avoid breaking changes 
# if I'm not careful, I'll leave them or just rely on auth.py. 
# Actually, I'll remove them from here and use auth.py in app.py.
# Wait, the previous utils.py had them. I should probably remove them to avoid duplication if I'm using auth.py.
# However, to minimize diffs and potential breakages in other files I haven't checked, I might keep them or just replace them with imports.
# Let's stick to the plan: auth.py has them. I will remove them from here.

def send_email(to_email, subject, body):
    if "email" not in st.secrets:
        st.error("Email configuration missing in secrets.")
        return False
    
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port = st.secrets["email"]["smtp_port"]
    sender_email = st.secrets["email"]["sender_email"]
    sender_password = st.secrets["email"]["sender_password"]

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def get_display_name(username, users_list=None):
    """Get display name for a username, falling back to username."""
    # If users_list is provided, use it. Otherwise try to get from session state.
    if users_list is None:
        if 'data' in st.session_state and 'users' in st.session_state.data:
            users_list = st.session_state.data['users']
        else:
            return username
            
    user = next((u for u in users_list if u['username'] == username), None)
    if user and user.get('display_name'):
        return user['display_name']
    return username

# Currency symbols mapping
CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "AUD": "A$", "CAD": "C$", "CHF": "Fr", "HKD": "HK$", "SGD": "S$",
    "KRW": "₩", "INR": "₹", "MXN": "Mex$", "BRL": "R$", "ZAR": "R",
    "NZD": "NZ$", "THB": "฿", "MYR": "RM", "PHP": "₱", "IDR": "Rp", "VND": "₫"
}

def format_currency(amount, currency_code='USD'):
    symbol = CURRENCY_SYMBOLS.get(currency_code, '$')
    return f"{symbol}{amount:.2f}"

def format_expense_display(expense, event_currency='USD'):
    base_amount = format_currency(expense['amount'], event_currency)
    if expense.get('original_currency') and expense.get('original_amount'):
        if expense['original_currency'] != event_currency:
                orig_amount = format_currency(expense['original_amount'], expense['original_currency'])
                return f"{base_amount} ({orig_amount})"
    return base_amount

@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_exchange_rate(from_currency, to_currency):
    if from_currency == to_currency:
        return 1.0
    
    try:
        # Using exchangerate-api.com (free tier: 1500 requests/month)
        url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if 'rates' in data and to_currency in data['rates']:
            return data['rates'][to_currency]
        else:
            st.warning(f"Could not fetch exchange rate for {from_currency} to {to_currency}")
            return None
    except Exception as e:
        st.error(f"Error fetching exchange rate: {e}")
        return None

def safe_eval_formula(formula_str):
    """Safely evaluate a math formula string."""
    if not formula_str:
        return 0.0
    
    # Remove whitespace
    formula_str = formula_str.strip()
    
    # If it's already a number, return it
    try:
        return float(formula_str)
    except ValueError:
        pass
    
    # Try to evaluate as a formula
    try:
        # Handle Excel-style leading '=' 
        if formula_str.startswith('='):
            formula_str = formula_str[1:]
            
        # Only allow safe characters: digits, operators, parentheses, decimal point
        if re.match(r'^[\d\s\+\-\*\/\(\)\.]+$', formula_str):
            result = eval(formula_str)
            return float(result)
        else:
            return 0.0
    except:
        return 0.0

def predict_category(description, all_categories=None):
    """Predict category (and sub-category) based on description using advanced keyword matching."""
    if not description:
        return all_categories[0] if all_categories else "💰 Other"
    
    desc_lower = description.lower()
    
    # 1. Sub-category specific matching (More specific = Higher priority)
    subcategory_map = {
        # Food
        "  → Restaurant": ["restaurant", "dinner", "lunch", "bistro", "steakhouse", "sushi", "buffet", "dining", "nando", "wagamama", "pizza express", "zizzi", "wetherspoon", "pub", "sunday roast", "curry"],
        "  → Fast Food": ["mcdonald", "burger", "kfc", "taco", "pizza", "subway", "fries", "fast food", "chipotle", "greggs", "five guys", "domino", "papa john", "chicken shop"],
        "  → Cafe": ["coffee", "starbucks", "latte", "cafe", "tea", "dunkin", "espresso", "bakery", "costa", "nero", "pret", "gail", "leon"],
        "  → Groceries": ["grocery", "groceries", "supermarket", "market", "whole foods", "trader joe", "safeway", "kroger", "walmart", "costco", "fruit", "veg", "tesco", "sainsbury", "asda", "waitrose", "m&s", "marks and spencer", "morrison", "aldi", "lidl", "co-op", "iceland", "ocado"],
        "  → Delivery": ["uber eats", "doordash", "grubhub", "delivery", "postmates", "takeout", "deliveroo", "just eat", "hungry panda"],
        
        # Transport
        "  → Taxi/Uber": ["uber", "lyft", "taxi", "cab", "ride", "grab", "bolt", "black cab", "minicab"],
        "  → Flights": ["flight", "airline", "ticket", "delta", "united", "american air", "airport", "plane", "ba", "british airways", "easyjet", "ryanair", "virgin", "heathrow", "gatwick", "stansted", "luton", "city airport"],
        "  → Public Transit": ["bus", "train", "subway", "metro", "bart", "ticket", "pass", "transit", "tube", "tfl", "underground", "oyster", "contactless", "national rail", "trainline", "gwr", "lner", "southeastern", "thameslink", "dlr", "tram"],
        "  → Gas/Fuel": ["gas", "fuel", "petrol", "shell", "chevron", "bp", "station", "esso", "texaco"],
        
        # Housing
        "  → Utilities": ["electric", "water", "gas bill", "utility", "power", "internet", "wifi", "broadband", "british gas", "octopus", "scottish power", "thames water", "council tax", "tv license", "bt", "virgin media", "sky"],
        "  → Rent": ["rent", "lease", "housing", "landlord", "deposit"],
        
        # Entertainment
        "  → Movies": ["movie", "cinema", "film", "theatre", "theater", "imax", "amc", "odeon", "vue", "cineworld", "everyman"],
        "  → Streaming": ["netflix", "spotify", "hulu", "disney", "hbo", "subscription", "youtube", "prime video", "now tv", "apple tv"],
        "  → Games": ["game", "steam", "playstation", "xbox", "nintendo", "gaming"],
        
        # Shopping
        "  → Electronics": ["apple", "best buy", "tech", "phone", "laptop", "computer", "cable", "charger", "currys", "pc world", "argos"],
        "  → Clothing": ["clothes", "shirt", "pants", "dress", "shoes", "nike", "adidas", "zara", "uniqlo", "wear", "primark", "next", "asos", "jd sports", "sports direct", "tk maxx", "john lewis", "selfridges"],
        
        # Travel
        "  → Hotels": ["hotel", "airbnb", "motel", "stay", "resort", "booking", "hostel", "premier inn", "travelodge", "holiday inn"],
        
        # Health
        "  → Gym": ["gym", "fitness", "workout", "yoga", "crossfit", "membership", "puregym", "the gym", "virgin active", "david lloyd"],
        "  → Pharmacy": ["pharmacy", "cvs", "walgreens", "drug", "medicine", "pill", "boots", "superdrug", "lloyds", "nhs", "prescription"],
    }
    
    # Check specific sub-categories first
    for subcat, keywords in subcategory_map.items():
        if any(k in desc_lower for k in keywords):
            return subcat

    # 2. Fallback to Main Category matching
    keyword_map = {
        "🍔 Food & Dining": ["food", "meal", "eat", "snack", "drink"],
        "🚗 Transportation": ["transport", "car", "vehicle", "parking", "toll"],
        "🏠 Housing": ["home", "house", "apartment", "furniture", "cleaning"],
        "🎬 Entertainment": ["fun", "hobby", "ticket", "show", "concert"],
        "🛍️ Shopping": ["shop", "store", "buy", "gift", "amazon"],
        "💊 Health": ["doctor", "medical", "health", "dentist", "insurance"],
        "✈️ Travel": ["travel", "trip", "vacation", "visa", "passport"],
        "📚 Education": ["school", "class", "course", "book", "tuition"],
        "💼 Work": ["work", "office", "business"],
        "🎉 Events": ["party", "birthday", "wedding", "celebration"],
        "🐾 Pets": ["pet", "dog", "cat", "vet"],
    }
    
    best_match = None
    max_matches = 0
    
    for category, keywords in keyword_map.items():
        matches = sum(1 for keyword in keywords if keyword in desc_lower)
        if matches > max_matches:
            max_matches = matches
            best_match = category
    
    if best_match and all_categories and best_match in all_categories:
        return best_match
    
    return all_categories[0] if all_categories else "💰 Other"

def calculate_settlements(debts):
    """
    Simplify a list of debts (minimize transactions).
    Returns list of settlements: [{'payer': str, 'recipient': str, 'amount': float}]
    """
    if not debts:
        return []
    
    # Calculate net balances from the list of debts
    balances = {}
    for debt in debts:
        debtor = debt['debtor']
        creditor = debt['creditor']
        amount = debt['amount']
        
        balances[debtor] = balances.get(debtor, 0.0) - amount
        balances[creditor] = balances.get(creditor, 0.0) + amount
    
    # Convert balances to simplified settlements
    creditors = [[person, bal] for person, bal in balances.items() if bal > 0.01]
    debtors = [[person, bal] for person, bal in balances.items() if bal < -0.01]
    
    # Sort by amount to optimize matching (greedy approach)
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1])
    
    settlements = []
    i = 0
    j = 0
    
    while i < len(debtors) and j < len(creditors):
        debtor, debt_amount = debtors[i]
        creditor, credit_amount = creditors[j]
        
        # The amount to settle is the minimum of what's owed and what's due
        amount = min(abs(debt_amount), credit_amount)
        if amount > 0.01:
            settlements.append({"payer": debtor, "recipient": creditor, "amount": amount})
        
        # Update balances
        debtors[i][1] += amount
        creditors[j][1] -= amount
        
        # Move to next if settled
        if abs(debtors[i][1]) < 0.01: i += 1
        if creditors[j][1] < 0.01: j += 1
        
    return settlements

def calculate_debts(expenses, members, settlements=None):
    """
    Calculate who owes whom based on expenses and settlements.
    Returns list of debts: [{'debtor': str, 'creditor': str, 'amount': float}]
    """
    # Filter out settled expenses
    unsettled = [e for e in expenses if not e.get('settled', False)]
    
    # Calculate balances for each member
    balances = {member: 0.0 for member in members}
    
    # Process expenses
    for expense in unsettled:
        payer = expense['payer']
        amount = expense['amount']
        involved = expense.get('involved', members)
        split_type = expense.get('split_type', 'equally')
        split_data = expense.get('split_data', {}) # {username: value}
        
        if not involved:
            involved = members
            
        # Calculate shares based on split type
        shares = {member: 0.0 for member in involved}
        
        if split_type == 'equally' or not split_data:
            split_amount = amount / len(involved)
            for person in involved:
                shares[person] = split_amount
        elif split_type == 'exactly':
            for person in involved:
                shares[person] = float(split_data.get(person, 0.0))
        elif split_type == 'percentages':
            for person in involved:
                percentage = float(split_data.get(person, 0.0))
                shares[person] = (percentage / 100.0) * amount
        elif split_type == 'shares':
            total_shares = sum(float(v) for v in split_data.values())
            if total_shares > 0:
                for person in involved:
                    member_shares = float(split_data.get(person, 0.0))
                    shares[person] = (member_shares / total_shares) * amount
            else:
                # Fallback to equal if shares are zero
                split_amount = amount / len(involved)
                for person in involved:
                    shares[person] = split_amount
        
        # Payer gets credited
        if payer in balances:
            balances[payer] += amount
        
        # Each involved member gets debited their share
        for person, share_amount in shares.items():
            if person in balances:
                balances[person] -= share_amount

    # Process settlements (payments)
    if settlements:
        for s in settlements:
            payer = s.get('payer')
            recipient = s.get('recipient')
            amount = s.get('amount', 0.0)
            
            if payer in balances:
                balances[payer] += amount
            if recipient in balances:
                balances[recipient] -= amount
    
    # Convert absolute balances to simplified debts
    creditors = [[person, bal] for person, bal in balances.items() if bal > 0.01]
    debtors = [[person, bal] for person, bal in balances.items() if bal < -0.01]
    
    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1])
    
    transactions = []
    i = 0
    j = 0
    
    while i < len(debtors) and j < len(creditors):
        debtor, debt_amt = debtors[i]
        creditor, credit_amt = creditors[j]
        amount = min(abs(debt_amt), credit_amt)
        if amount > 0.01:
            transactions.append({"debtor": debtor, "creditor": creditor, "amount": amount})
        debtors[i][1] += amount
        creditors[j][1] -= amount
        if abs(debtors[i][1]) < 0.01: i += 1
        if creditors[j][1] < 0.01: j += 1
        
    return transactions

def parse_group_info(text):
    """
    Parse pasted text from WhatsApp/Text to extract group name and members.
    Returns dict: {'name': str, 'members': list}
    """
    info = {'name': None, 'members': []}
    
    # Try to find group name
    # Look for "Group: Name" or just take the first line if it looks like a title
    lines = text.split('\n')
    if lines:
        first_line = lines[0].strip()
        if ':' in first_line:
            # e.g. "Group: Japan Trip"
            parts = first_line.split(':', 1)
            if 'group' in parts[0].lower():
                info['name'] = parts[1].strip()
        else:
            # Assume first line is name if it's short
            if len(first_line) < 50:
                info['name'] = first_line
    
    # Extract potential members (names or phone numbers)
    # This is a simple heuristic
    import re
    
    # Look for phone numbers
    phone_pattern = r'\+?[\d\s-]{10,}'
    phones = re.findall(phone_pattern, text)
    info['members'].extend([p.strip() for p in phones])
    
    # Look for names (capitalized words, exclude common words)
    # This is hard to do reliably without NLP, so we'll just look for comma separated lists
    # or lines that look like lists of names
    
    return info
