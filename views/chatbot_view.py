import streamlit as st
from ai_utils import get_gemini_response

def render_chatbot(current_event):
    """Render the AI Chatbot interface."""
    st.title("🤖 Spending Insights Chatbot")
    st.caption("Ask questions about your event's expenses and get instant answers powered by Gemini.")
    
    # API Key Management
    api_key = None
    if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
        api_key = st.secrets["gemini"]["api_key"]
    else:
        with st.expander("🔑 API Key Setup", expanded=True):
            st.info("To use this feature, you need a Google Gemini API Key.")
            api_key_input = st.text_input("Enter your Gemini API Key", type="password", help="Get one at aistudio.google.com")
            if api_key_input:
                api_key = api_key_input
                st.success("API Key provided!")
    
    st.divider()

    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": f"Hi! I'm your financial assistant for **{current_event['name']}**. Ask me anything about your spending!"}
        ]

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Ask a question (e.g., 'How much did we spend on food?')"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)

        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            if not api_key:
                response = "⚠️ Please provide a Gemini API Key to continue."
                st.error(response)
            else:
                with st.spinner("Thinking..."):
                    response = get_gemini_response(prompt, current_event, api_key)
                st.markdown(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
