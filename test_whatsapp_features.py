from utils import parse_group_info

def test_parsing():
    print("🧪 Testing Smart Import Parsing...")
    
    # Test Case 1: Standard WhatsApp Group Info
    text1 = """
    Japan Trip 2024
    Created by You, 12/01/2024
    
    +1 234 567 890, John Doe, Sarah Smith, You
    """
    result1 = parse_group_info(text1)
    print(f"\nTest 1 (Standard):")
    print(f"Input:\n{text1.strip()}")
    print(f"Output: {result1}")
    assert result1['name'] == "Japan Trip 2024"
    assert "John Doe" in result1['members']
    assert "Sarah Smith" in result1['members']
    assert "+1 234 567 890" in result1['members']
    assert "You" not in result1['members'] # Should be filtered out
    
    # Test Case 2: Messy Text
    text2 = """
    Messages are end-to-end encrypted.
    Weekend Getaway
    Admin added you
    
    Mike
    Tom
    +44 7890 123456
    """
    result2 = parse_group_info(text2)
    print(f"\nTest 2 (Messy):")
    print(f"Input:\n{text2.strip()}")
    print(f"Output: {result2}")
    assert result2['name'] == "Weekend Getaway"
    assert "Mike" in result2['members']
    assert "Tom" in result2['members']
    
    print("\n✅ All parsing tests passed!")

if __name__ == "__main__":
    test_parsing()
