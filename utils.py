import re

def parse_group_info(text):
    """
    Parses text (like WhatsApp group info) to extract potential event name and members.
    
    Args:
        text (str): The raw text to parse.
        
    Returns:
        dict: A dictionary containing 'name' (str) and 'members' (list).
    """
    info = {
        "name": "",
        "members": []
    }
    
    if not text:
        return info
        
    lines = text.split('\n')
    
    # 1. Try to find Group Name
    # Heuristic: First non-empty line that doesn't look like a phone number, date, or system message
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip lines that look like dates or system messages
        if re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', line): # Date
            continue
        
        line_lower = line.lower()
        if any(x in line_lower for x in ["created group", "added you", "messages are end-to-end encrypted", "security code", "changed the subject", "group info"]):
            continue
            
        # If we find a line that seems to be a title (not too long, no numbers at start)
        if len(line) < 50 and not re.match(r'^[\+0-9]', line):
            info["name"] = line
            break
            
    # 2. Try to find Members
    # Heuristic: Look for names or phone numbers in comma-separated lists or new lines
    # WhatsApp often lists members like: "+1 234-567-890, John, Sarah, +44 7890 123456"
    
    # Normalize text to handle newlines as separators too if they look like a list
    # But be careful not to merge unrelated lines.
    
    # Regex for potential names/numbers
    # Matches:
    # - Phone numbers: +1 234 567 8900
    # - Names: John Doe, Sarah
    # - Excludes: "You", "Group info", dates
    
    # Strategy: Split by commas and newlines, then clean up
    tokens = re.split(r'[,\n]', text)
    
    potential_members = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
            
        # Filter out common junk
        token_lower = token.lower()
        if token_lower in ["you", "admin", "group info", "created by", "messages", "search"]:
            continue
            
        if any(x in token_lower for x in ["created group", "added you", "messages are end-to-end encrypted", "security code"]):
            continue
            
        # If it's the group name we found earlier, skip it
        if token == info["name"]:
            continue
            
        # If it looks like a date/time, skip
        if re.search(r'\d{1,2}:\d{2}', token) or re.search(r'\d{1,2}/\d{1,2}', token):
            continue
            
        # If it's reasonably short (name) or looks like a phone number
        if len(token) < 30:
            # Clean up phone numbers to just digits/plus for consistency if needed
            # For now, keep as is for display
            potential_members.append(token)
            
    # Remove duplicates
    info["members"] = list(set(potential_members))
    
    return info
