# SplitSync

A smart expense sharing application built with Streamlit and Supabase.

## Features
- **Authentication**: Secure login and registration.
- **Event Management**: Create and join events with access codes.
- **Expense Tracking**: Add expenses with smart categorization and currency conversion.
- **Settlements**: Calculate debts and record payments.
- **Analytics**: Visualize spending with interactive charts.

## Deployment on Streamlit Cloud

1. **Push to GitHub**: Ensure the following files are in your repository:
    - `app.py`
    - `auth.py`
    - `database.py`
    - `utils.py`
    - `requirements.txt`
    - `views/` (directory)

2. **Connect to Streamlit Cloud**:
    - Go to [share.streamlit.io](https://share.streamlit.io/).
    - Connect your GitHub account and select your repository.
    - Set the **Main file path** to `app.py`.

3. **Configure Secrets**:
    - In the Streamlit Cloud dashboard for your app, go to **Settings** > **Secrets**.
    - Add your Supabase and Email secrets in the TOML format:

    ```toml
    [supabase]
    url = "YOUR_SUPABASE_URL"
    key = "YOUR_SUPABASE_KEY"

    [email]
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    sender_email = "your_email@gmail.com"
    sender_password = "your_app_password"
    ```

4. **Deploy**: Click **Deploy**!

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:
   ```bash
   streamlit run app.py
   ```
