import streamlit as st
from datetime import datetime
from utils import predict_category, get_exchange_rate, safe_eval_formula, format_expense_display
from database import add_expense, update_expense, delete_expense, get_user_by_username
from subscription import can_add_expense, show_limit_reached, FREE_LIMITS

def render_add_expense(current_event):
    """Render the Add Expense form."""
    st.title("Add Expense")
    
    # Initialize session state for form submission tracking
    if 'expense_saved' not in st.session_state:
        st.session_state.expense_saved = False
    
    # Show success message if expense was just saved
    if st.session_state.expense_saved:
        st.toast("✅ Expense saved successfully!", icon="💰")
        st.session_state.expense_saved = False
    
    # 1. Currency Selection (Outside Form for interactivity)
    event_currency = current_event.get('currency', 'USD')
    currencies = {
        "USD": "$ (US Dollar)", "EUR": "€ (Euro)", "GBP": "£ (British Pound)",
        "JPY": "¥ (Japanese Yen)", "CNY": "¥ (Chinese Yuan)", "AUD": "A$ (Australian Dollar)",
        "CAD": "C$ (Canadian Dollar)", "CHF": "Fr (Swiss Franc)", "HKD": "HK$ (Hong Kong Dollar)",
        "SGD": "S$ (Singapore Dollar)", "KRW": "₩ (South Korean Won)", "INR": "₹ (Indian Rupee)",
        "MXN": "Mex$ (Mexican Peso)", "BRL": "R$ (Brazilian Real)", "ZAR": "R (South African Rand)",
        "NZD": "NZ$ (New Zealand Dollar)", "THB": "฿ (Thai Baht)", "MYR": "RM (Malaysian Ringgit)",
        "PHP": "₱ (Philippine Peso)", "IDR": "Rp (Indonesian Rupiah)", "VND": "₫ (Vietnamese Dong)"
    }
    
    col_curr, col_mode = st.columns([1, 2])
    with col_curr:
        selected_currency = st.selectbox(
            "Currency",
            options=list(currencies.keys()),
            index=list(currencies.keys()).index(event_currency) if event_currency in currencies else 0,
            format_func=lambda x: x,
            key="add_exp_curr"
        )
        
    conversion_mode = "Auto"
    if selected_currency != event_currency:
        with col_mode:
            conversion_mode = st.radio(
                "Conversion Method", 
                ["Auto (Market Rate)", "Manual (Set Base Amount)"], 
                horizontal=True,
                help="Auto: We fetch the rate. Manual: You specify the exact amount in event currency.",
                key="add_exp_mode"
            )
    
    # Comprehensive Category System
    DEFAULT_CATEGORIES = {
        "🍔 Food & Dining": ["Restaurant", "Groceries", "Fast Food", "Cafe", "Delivery"],
        "🚗 Transportation": ["Gas/Fuel", "Public Transit", "Taxi/Uber", "Parking", "Car Maintenance"],
        "🏠 Housing": ["Rent", "Utilities", "Internet", "Furniture", "Home Supplies"],
        "🎬 Entertainment": ["Movies", "Concerts", "Games", "Streaming", "Hobbies"],
        "🛍️ Shopping": ["Clothing", "Electronics", "Books", "Gifts", "Personal Care"],
        "💊 Health": ["Medical", "Pharmacy", "Gym", "Wellness", "Insurance"],
        "✈️ Travel": ["Flights", "Hotels", "Activities", "Souvenirs", "Visa/Fees"],
        "📚 Education": ["Tuition", "Books", "Courses", "Supplies", "Software"],
        "💼 Work": ["Office Supplies", "Equipment", "Professional Development"],
        "🎉 Events": ["Parties", "Celebrations", "Weddings", "Birthdays"],
        "🐾 Pets": ["Food", "Vet", "Supplies", "Grooming"],
        "💰 Other": ["Miscellaneous", "Uncategorized"]
    }
    
    # Get custom categories from event (if any)
    custom_categories = current_event.get('custom_categories', [])
    
    # Combine default and custom categories
    all_categories = []
    for main_cat, subcats in DEFAULT_CATEGORIES.items():
        all_categories.append(main_cat)
        all_categories.extend([f"  → {sub}" for sub in subcats])
    all_categories.extend(custom_categories)

    with st.form("add_expense", clear_on_submit=True):
        title = st.text_input("Description")
        
        # Dynamic Inputs with Formula Support
        amount_in_base = 0.0
        amount_in_original = 0.0
        
        if selected_currency == event_currency:
            st.caption("💡 **Tip:** You can type math formulas! e.g., `12.50 * 3 + 5`")
            col_amt, col_calc = st.columns([2, 1])
            with col_amt:
                amount_formula = st.text_input(
                    f"Amount ({event_currency})", 
                    placeholder="e.g., 12.50 * 3 + 5",
                    help="Enter a number or formula (e.g., 3.7+6.5, 15*3, (10+5)/2)"
                )
                amount_in_base = safe_eval_formula(amount_formula)
            with col_calc:
                if amount_formula and amount_in_base > 0:
                    st.metric("Calculated", f"{amount_in_base:.2f}")
                else:
                    st.write("")  # Spacer
        else:
            st.caption("💡 **Tip:** Math formulas supported! e.g., `10 + 5`")
            if conversion_mode == "Auto (Market Rate)":
                col_amt, col_calc = st.columns([2, 1])
                with col_amt:
                    amount_formula_orig = st.text_input(
                        f"Amount ({selected_currency})", 
                        placeholder="e.g., 3.7+6.5",
                        help="Enter a number or formula"
                    )
                    amount_in_original = safe_eval_formula(amount_formula_orig)
                with col_calc:
                    if amount_formula_orig and amount_in_original > 0:
                        st.metric("Calculated", f"{amount_in_original:.2f}")
                st.caption(f"Will be converted to {event_currency} on submit.")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    amt_orig_formula = st.text_input(f"Spent ({selected_currency})", placeholder="e.g. 10+5")
                    amount_in_original = safe_eval_formula(amt_orig_formula)
                    if amt_orig_formula and amount_in_original > 0:
                        st.caption(f"= {amount_in_original:.2f}")
                        
                with c2:
                    amt_base_formula = st.text_input(f"Equivalent ({event_currency})", placeholder="e.g. 15*0.9")
                    amount_in_base = safe_eval_formula(amt_base_formula)
                    if amt_base_formula and amount_in_base > 0:
                        st.caption(f"= {amount_in_base:.2f}")
            
        
        # Get all participants (users + custom names)
        all_participants = current_event.get('all_participants', current_event['members'])
        
        payer = st.selectbox("Paid By", all_participants, index=all_participants.index(st.session_state.current_user) if st.session_state.current_user in all_participants else 0)
        
        # Smart Category Prediction
        predicted_category = predict_category(title, all_categories) if title else all_categories[0]
        
        # Auto-categorization with optional override
        st.markdown("### 🤖 Smart Categorization")
        
        if title:
            st.success(f"✨ **Auto-categorized as:** {predicted_category}")
            st.caption("This will be used automatically. Expand below to change if needed.")
        else:
            st.info("💡 Type a description above and we'll auto-categorize it for you!")
        
        # Collapsible manual override
        with st.expander("🔧 Manually select category (optional)", expanded=False):
            st.caption("Only use this if you want to override the auto-suggestion")
            
            # Manual category selection
            try:
                default_index = all_categories.index(predicted_category)
            except ValueError:
                default_index = 0
            
            manual_category = st.selectbox(
                "Choose category", 
                all_categories, 
                index=default_index,
                key="manual_cat_select"
            )
            
            # Custom category option
            custom_category = st.text_input(
                "Or enter custom category", 
                placeholder="e.g., Pet Supplies",
                key="custom_cat_input"
            )
            
            # Determine final category based on user input
            if custom_category.strip():
                category = f"🏷️ {custom_category.strip()}"
            elif manual_category != predicted_category:
                category = manual_category
            else:
                category = predicted_category
        
        # If expander not opened/used, use predicted category
        if not custom_category.strip() and (manual_category == predicted_category or 'manual_cat_select' not in locals()):
            category = predicted_category
        
        involved = st.multiselect("Split Among", all_participants, default=all_participants)
        date = st.date_input("Date", datetime.today())
        
        submitted = st.form_submit_button("Save Expense", type="primary")
        
        if submitted:
            if title and involved:
                # Check subscription limits
                user_data = get_user_by_username(st.session_state.current_user)
                
                if not can_add_expense(user_data, current_event):
                    # Show limit reached message
                    current_count = len(current_event.get('expenses', []))
                    show_limit_reached("expenses in this event", current_count, FREE_LIMITS['max_expenses_per_event'])
                else:
                    with st.spinner("💰 Saving expense..."):
                        # Logic to determine final amounts
                        final_amount = 0.0
                        original_amt = None
                        original_curr = None
                        exch_rate = None
                        
                        if selected_currency == event_currency:
                            final_amount = amount_in_base
                        else:
                            original_curr = selected_currency
                            original_amt = amount_in_original
                            
                            if conversion_mode == "Auto (Market Rate)":
                                rate = get_exchange_rate(selected_currency, event_currency)
                                if rate:
                                    final_amount = amount_in_original * rate
                                    exch_rate = rate
                                else:
                                    st.error("Could not fetch rate. Using 1:1.")
                                    final_amount = amount_in_original
                                    exch_rate = 1.0
                            else:
                                final_amount = amount_in_base
                                if amount_in_original > 0:
                                    exch_rate = final_amount / amount_in_original
                        
                        expense_data = {
                            "title": title,
                            "amount": final_amount,
                            "original_amount": original_amt,
                            "original_currency": original_curr,
                            "exchange_rate": exch_rate,
                            "payer": payer,
                            "involved": involved,
                            "date": str(date),
                            "category": category,
                            "settled": False
                        }
                        
                        if add_expense(current_event['id'], expense_data):
                            st.session_state.expense_saved = True
                            st.rerun()
                        else:
                            st.error("Failed to save expense.")
            else:
                st.error("Please fill all required fields.")

def render_edit_expenses(current_event):
    """Render the Edit Expenses form."""
    st.title("Edit Expenses")
    
    # Helper function to check if current user is admin
    def is_admin():
        roles = current_event.get('roles', {})
        return roles.get(st.session_state.current_user) == 'admin'

    # Check if user is admin
    if not is_admin():
        st.warning("⚠️ Only event admins can edit or delete expenses.")
        st.info("Contact an admin if you need to modify an expense.")
    elif not current_event['expenses']:
        st.info("No expenses to edit yet.")
    else:
        # Initialize session state for edit tracking
        if 'edit_expense_id' not in st.session_state:
            st.session_state.edit_expense_id = None
        if 'expense_updated' not in st.session_state:
            st.session_state.expense_updated = False
        
        # Show success message if expense was just updated
        if st.session_state.expense_updated:
            st.toast("✅ Expense updated successfully!", icon="✏️")
            st.session_state.expense_updated = False
        
        # Display list of expenses to select from
        st.subheader("Select an expense to edit:")
        
        expense_options = []
        for exp in current_event['expenses']:
            status = "✓ Settled" if exp.get('settled', False) else "⏳ Pending"
            display_amt = format_expense_display(exp, current_event.get('currency', 'USD'))
            expense_options.append(f"{exp['date']} - {exp['title']} ({display_amt}) - {status}")
        
        selected_idx = st.selectbox(
            "Choose expense:",
            range(len(expense_options)),
            format_func=lambda x: expense_options[x]
        )
        
        if selected_idx is not None:
            selected_expense = current_event['expenses'][selected_idx]
            
            st.divider()
            st.subheader("Edit Details:")
            
            # 1. Currency Selection (Outside Form)
            event_currency = current_event.get('currency', 'USD')
            currencies = {
                "USD": "$ (US Dollar)", "EUR": "€ (Euro)", "GBP": "£ (British Pound)",
                "JPY": "¥ (Japanese Yen)", "CNY": "¥ (Chinese Yuan)", "AUD": "A$ (Australian Dollar)",
                "CAD": "C$ (Canadian Dollar)", "CHF": "Fr (Swiss Franc)", "HKD": "HK$ (Hong Kong Dollar)",
                "SGD": "S$ (Singapore Dollar)", "KRW": "₩ (South Korean Won)", "INR": "₹ (Indian Rupee)",
                "MXN": "Mex$ (Mexican Peso)", "BRL": "R$ (Brazilian Real)", "ZAR": "R (South African Rand)",
                "NZD": "NZ$ (New Zealand Dollar)", "THB": "฿ (Thai Baht)", "MYR": "RM (Malaysian Ringgit)",
                "PHP": "₱ (Philippine Peso)", "IDR": "Rp (Indonesian Rupiah)", "VND": "₫ (Vietnamese Dong)"
            }
            
            # Determine initial values for outside widgets
            initial_currency = selected_expense.get('original_currency', event_currency)
            initial_amount_orig = selected_expense.get('original_amount', selected_expense['amount'])
            initial_amount_base = selected_expense['amount']
            
            # Use session state to initialize widgets only once per selection
            if 'edit_curr' not in st.session_state or st.session_state.get('last_edit_id') != selected_expense['id']:
                st.session_state.edit_curr = initial_currency
                st.session_state.last_edit_id = selected_expense['id']
                # Default mode: Manual if we have original amount, else Auto
                st.session_state.edit_mode = "Manual (Set Base Amount)" if selected_expense.get('original_amount') else "Auto (Market Rate)"

            col_curr, col_mode = st.columns([1, 2])
            with col_curr:
                # Find the index of the initial currency
                currency_list = list(currencies.keys())
                try:
                    initial_index = currency_list.index(initial_currency)
                except ValueError:
                    initial_index = currency_list.index(event_currency) if event_currency in currency_list else 0
                
                new_currency = st.selectbox(
                    "Currency",
                    options=currency_list,
                    index=initial_index,
                    format_func=lambda x: currencies[x],
                    key="edit_exp_curr"
                )
                # Show original currency as reference
                if initial_currency:
                    st.caption(f"💡 Original: {currencies.get(initial_currency, initial_currency)}")
            
            conversion_mode = "Auto"
            if new_currency != event_currency:
                with col_mode:
                    conversion_mode = st.radio(
                        "Conversion Method", 
                        ["Auto (Market Rate)", "Manual (Set Base Amount)"], 
                        horizontal=True,
                        key="edit_exp_mode"
                    )
            
            # Show current expense summary
            with st.expander("📋 Current Expense Details", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Title:** {selected_expense['title']}")
                    st.write(f"**Amount:** {format_expense_display(selected_expense, event_currency)}")
                    st.write(f"**Paid By:** {selected_expense['payer']}")
                    st.write(f"**Date:** {selected_expense['date']}")
                with col2:
                    st.write(f"**Category:** {selected_expense.get('category', 'N/A')}")
                    st.write(f"**Split Among:** {', '.join(selected_expense.get('involved', current_event['members']))}")
                    st.write(f"**Status:** {'✓ Settled' if selected_expense.get('settled', False) else '⏳ Pending'}")

            # Comprehensive Category System (duplicated here for now, could be shared)
            DEFAULT_CATEGORIES = {
                "🍔 Food & Dining": ["Restaurant", "Groceries", "Fast Food", "Cafe", "Delivery"],
                "🚗 Transportation": ["Gas/Fuel", "Public Transit", "Taxi/Uber", "Parking", "Car Maintenance"],
                "🏠 Housing": ["Rent", "Utilities", "Internet", "Furniture", "Home Supplies"],
                "🎬 Entertainment": ["Movies", "Concerts", "Games", "Streaming", "Hobbies"],
                "🛍️ Shopping": ["Clothing", "Electronics", "Books", "Gifts", "Personal Care"],
                "💊 Health": ["Medical", "Pharmacy", "Gym", "Wellness", "Insurance"],
                "✈️ Travel": ["Flights", "Hotels", "Activities", "Souvenirs", "Visa/Fees"],
                "📚 Education": ["Tuition", "Books", "Courses", "Supplies", "Software"],
                "💼 Work": ["Office Supplies", "Equipment", "Professional Development"],
                "🎉 Events": ["Parties", "Celebrations", "Weddings", "Birthdays"],
                "🐾 Pets": ["Food", "Vet", "Supplies", "Grooming"],
                "💰 Other": ["Miscellaneous", "Uncategorized"]
            }
            
            custom_categories = current_event.get('custom_categories', [])
            all_categories = []
            for main_cat, subcats in DEFAULT_CATEGORIES.items():
                all_categories.append(main_cat)
                all_categories.extend([f"  → {sub}" for sub in subcats])
            all_categories.extend(custom_categories)

            with st.form("edit_expense_form"):
                st.caption("✏️ Edit the fields below (pre-filled with current values)")
                new_title = st.text_input("Description", value=selected_expense['title'])
                
                # Dynamic Inputs
                new_amount_base = 0.0
                new_amount_orig = 0.0
                
                if new_currency == event_currency:
                    new_amount_base = st.number_input(f"Amount ({event_currency})", min_value=0.01, value=float(initial_amount_base))
                else:
                    if conversion_mode == "Auto (Market Rate)":
                        # If switching to Auto, try to use original amount if available, else base
                        val = float(initial_amount_orig) if initial_currency == new_currency else 1.0
                        new_amount_orig = st.number_input(f"Amount ({new_currency})", min_value=0.01, value=val)
                        st.caption(f"Will be converted to {event_currency} on submit.")
                    else:
                        c1, c2 = st.columns(2)
                        with c1:
                            val_orig = float(initial_amount_orig) if initial_currency == new_currency else 1.0
                            new_amount_orig = st.number_input(f"Spent ({new_currency})", min_value=0.01, value=val_orig)
                        with c2:
                            val_base = float(initial_amount_base)
                            new_amount_base = st.number_input(f"Equivalent ({event_currency})", min_value=0.01, value=val_base)
                
                # Get all participants (users + custom names)
                all_participants = current_event.get('all_participants', current_event['members'])
                
                # Get current payer index
                try:
                    payer_idx = all_participants.index(selected_expense['payer'])
                except ValueError:
                    payer_idx = 0
                
                new_payer = st.selectbox("Paid By", all_participants, index=payer_idx)
                
                # Get current category index
                try:
                    cat_idx = all_categories.index(selected_expense['category'])
                except ValueError:
                    cat_idx = 0
                
                new_category = st.selectbox("Category", all_categories, index=cat_idx)
                
                # Handle involved members
                current_involved = selected_expense.get('involved', all_participants)
                new_involved = st.multiselect("Split Among", all_participants, default=current_involved)
                
                # Parse date
                try:
                    current_date = datetime.strptime(selected_expense['date'], '%Y-%m-%d').date()
                except:
                    current_date = datetime.today().date()
                
                new_date = st.date_input("Date", value=current_date)
                
                submitted = st.form_submit_button("Update Expense", type="primary")
                
                if submitted:
                    if new_title and new_involved:
                        with st.spinner("✏️ Updating expense..."):
                            # Logic to determine final amounts
                            final_amount = 0.0
                            original_amt = None
                            original_curr = None
                            exch_rate = None
                            
                            if new_currency == event_currency:
                                final_amount = new_amount_base
                            else:
                                original_curr = new_currency
                                original_amt = new_amount_orig
                                
                                if conversion_mode == "Auto (Market Rate)":
                                    rate = get_exchange_rate(new_currency, event_currency)
                                    if rate:
                                        final_amount = new_amount_orig * rate
                                        exch_rate = rate
                                    else:
                                        st.error("Could not fetch rate. Using 1:1.")
                                        final_amount = new_amount_orig
                                        exch_rate = 1.0
                                else:
                                    final_amount = new_amount_base
                                    if new_amount_orig > 0:
                                        exch_rate = final_amount / new_amount_orig
                            
                            updates = {
                                'title': new_title,
                                'amount': final_amount,
                                'original_amount': original_amt,
                                'original_currency': original_curr,
                                'exchange_rate': exch_rate,
                                'payer': new_payer,
                                'category': new_category,
                                'involved': new_involved,
                                'date': str(new_date),
                                'settled': selected_expense.get('settled', False)
                            }
                            
                            if update_expense(selected_expense['id'], updates):
                                st.session_state.expense_updated = True
                                st.rerun()
                            else:
                                st.error("Failed to update expense.")
                    else:
                        st.error("Please fill all required fields.")
            
            
            # Delete button with confirmation
            st.divider()
            
            # Initialize delete confirmation state
            if 'confirm_delete_expense' not in st.session_state:
                st.session_state.confirm_delete_expense = None
            
            if st.session_state.confirm_delete_expense == selected_expense['id']:
                # Show confirmation dialog
                st.warning("⚠️ Are you sure you want to delete this expense? This action cannot be undone!")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete", type="primary", key="confirm_delete_yes"):
                        with st.spinner("🗑️ Deleting expense..."):
                            if delete_expense(selected_expense['id']):
                                st.toast("✅ Expense deleted successfully!", icon="🗑️")
                                st.session_state.confirm_delete_expense = None
                                st.rerun()
                            else:
                                st.error("Failed to delete expense.")
                                st.session_state.confirm_delete_expense = None
                with col2:
                    if st.button("❌ Cancel", key="confirm_delete_no"):
                        st.session_state.confirm_delete_expense = None
                        st.rerun()
            else:
                # Show initial delete button
                if st.button("🗑️ Delete Expense", type="secondary"):
                    st.session_state.confirm_delete_expense = selected_expense['id']
                    st.rerun()
