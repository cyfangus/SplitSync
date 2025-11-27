import google.generativeai as genai
import json
import streamlit as st

def get_gemini_response(query, context_data, api_key):
    """
    Get a response from Gemini based on the user query and data context.
    """
    if not api_key:
        return "⚠️ Please provide a valid Gemini API Key."

    try:
        genai.configure(api_key=api_key)
        
        # Use a lightweight model for speed
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        
        # Prepare the context
        # We'll summarize the data to avoid hitting token limits if the event is huge
        # But for most personal events, passing the full JSON is fine.
        
        # Clean up data to remove unnecessary fields for the AI
        clean_expenses = []
        for exp in context_data.get('expenses', []):
            clean_expenses.append({
                'date': exp.get('date'),
                'title': exp.get('title'),
                'amount': exp.get('amount'),
                'payer': exp.get('payer'),
                'category': exp.get('category'),
                'involved': exp.get('involved')
            })
            
        clean_settlements = context_data.get('settlements', [])
        
        data_summary = {
            "event_name": context_data.get('name'),
            "currency": context_data.get('currency'),
            "members": context_data.get('members'),
            "expenses": clean_expenses,
            "settlements": clean_settlements
        }
        
        prompt = f"""
        You are a helpful financial assistant for an expense sharing group.
        
        Here is the data for the event "{data_summary['event_name']}":
        ```json
        {json.dumps(data_summary, indent=2)}
        ```
        
        User Question: {query}
        
        Instructions:
        1. Answer the question based ONLY on the provided data.
        2. Be concise and friendly.
        3. If the answer involves numbers, format them with the event currency ({data_summary['currency']}).
        4. If you can't answer based on the data, say so.
        5. You can calculate totals, averages, and identify trends.
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ Error: {str(e)}"
