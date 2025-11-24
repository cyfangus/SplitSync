# SplitSync - SQLite Migration

## 🎉 Database Migration Complete!

Your application has been successfully migrated from Google Sheets to **SQLite** for improved security and performance.

## ✅ What Changed

### Before (Google Sheets)
- Data stored in Google Sheets
- Required Google Cloud credentials
- Dependent on internet connection
- Limited query performance

### After (SQLite)
- Data stored locally in `splitsync.db`
- No external dependencies
- Works offline
- Fast and secure

## 📁 New Files

- **`database.py`**: SQLite database operations
- **`splitsync.db`**: Your secure local database (auto-created)
- **`migrate_to_sqlite.py`**: One-time migration script (already run)
- **`.gitignore`**: Protects your database from being committed to git

## 🔒 Security Improvements

1. **Local Storage**: Your data stays on your machine
2. **No Cloud Sync**: No risk of accidental data exposure
3. **File Permissions**: Database file can be encrypted at the OS level
4. **Git-Ignored**: Database automatically excluded from version control

## 🚀 Running the App

Nothing changes for you! Just run:

```bash
streamlit run app.py
```

## 📊 Database Schema

### Tables
- **users**: User accounts with authentication
- **events**: Expense sharing events
- **event_members**: User-event relationships with roles
- **expenses**: Individual expenses
- **expense_participants**: Who's involved in each expense
- **settlements**: Payment records

## 🔄 Backup & Restore

### Backup
```bash
cp splitsync.db splitsync_backup_$(date +%Y%m%d).db
```

### Restore
```bash
cp splitsync_backup_YYYYMMDD.db splitsync.db
```

## ⚙️ Configuration

The app no longer requires Google Sheets credentials. You can remove the `gcp_service_account` section from `.streamlit/secrets.toml` if you want.

Email functionality still requires the `[email]` section in secrets.

## 🆘 Troubleshooting

### Database locked error
- Close any other instances of the app
- Check file permissions on `splitsync.db`

### Data not persisting
- Ensure `splitsync.db` has write permissions
- Check that you're running from the correct directory

## 📝 Notes

- Your old `data.json` has been backed up to `data.json.backup`
- The database file (`splitsync.db`) is automatically created on first run
- All existing data has been migrated successfully
