"""Generate a Telethon StringSession for use on headless hosts.

Usage (PowerShell):
    $env:API_ID = 'your_api_id'
    $env:API_HASH = 'your_api_hash'
    python create_string_session.py

Usage (Git Bash / WSL):
    export API_ID=your_api_id
    export API_HASH=your_api_hash
    python create_string_session.py

The script opens an interactive Telethon client in this terminal for you to sign in.
After sign-in it prints the StringSession value you can copy into your hosting provider's secret.
"""
from telethon import TelegramClient
from telethon.sessions import StringSession
import os

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

if not API_ID or not API_HASH:
        print('ERROR: API_ID and API_HASH must be set as environment variables')
        print('PowerShell example:')
        print("  $env:API_ID = 'your_api_id'; $env:API_HASH = 'your_api_hash'; python create_string_session.py")
        print('Git Bash example:')
        print('  export API_ID=your_api_id; export API_HASH=your_api_hash; python create_string_session.py')
        raise SystemExit(1)

API_ID = int(API_ID)

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        print('Sign in interactively in this terminal when prompted.')
        print('After successful sign-in the script will print a StringSession you can copy.')
        print('String session:')
        print(client.session.save()) 