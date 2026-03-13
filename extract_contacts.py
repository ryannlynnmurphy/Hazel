from gmail import get_service
from contacts import _load, _save
import re

def extract_from_gmail():
    service = get_service()
    seen = {}
    
    # Get sent messages
    results = service.users().messages().list(userId='me', labelIds=['SENT'], maxResults=500).execute()
    messages = results.get('messages', [])
    print(f"Scanning {len(messages)} sent messages...")
    
    for i, msg in enumerate(messages):
        if i % 50 == 0:
            print(f"  Processing {i}/{len(messages)}...")
        try:
            full = service.users().messages().get(userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['To','Cc','Bcc']).execute()
            headers = full.get('payload', {}).get('headers', [])
            for h in headers:
                if h['name'] in ['To','Cc','Bcc']:
                    # Parse "Name <email>" or just "email"
                    for match in re.finditer(r'([^<,]+?)\s*<([^>]+)>|([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', h['value']):
                        if match.group(2):
                            name = match.group(1).strip().strip('"')
                            email = match.group(2).strip()
                        else:
                            name = match.group(3).split('@')[0]
                            email = match.group(3).strip()
                        if email and email not in seen:
                            seen[email] = name
        except Exception as e:
            continue
    
    # Merge into local contacts
    local = _load()
    local_emails = {c.get('email','').lower() for c in local}
    added = 0
    for email, name in seen.items():
        if email.lower() not in local_emails:
            local.append({'name': name, 'email': email, 'phone': '', 'note': 'imported from gmail'})
            added += 1
    
    _save(local)
    print(f"\nDone! Added {added} new contacts from Gmail. Total: {len(local)}")

extract_from_gmail()
