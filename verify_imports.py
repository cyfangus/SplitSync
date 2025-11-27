import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Checking imports...")
    import auth
    print("auth imported")
    import utils
    print("utils imported")
    import database
    print("database imported")
    import ai_utils
    print("ai_utils imported")
    
    # Views
    import views.auth_view
    print("views.auth_view imported")
    import views.dashboard_view
    print("views.dashboard_view imported")
    import views.settings_view
    print("views.settings_view imported")
    import views.event_details
    print("views.event_details imported")
    import views.expenses_view
    print("views.expenses_view imported")
    import views.settlements_view
    print("views.settlements_view imported")
    import views.analytics_view
    print("views.analytics_view imported")
    import views.manage_event_view
    print("views.manage_event_view imported")
    import views.chatbot_view
    print("views.chatbot_view imported")
    
    print("✅ All imports successful!")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
