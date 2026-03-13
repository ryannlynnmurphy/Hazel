import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TOKEN_FILE = os.path.expanduser("~/jarvis/token.json")
CREDS_FILE = os.path.expanduser("~/jarvis/credentials.json")
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/calendar",
]

def _get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("people", "v1", credentials=creds)

def list_google_contacts(max=100):
    service = _get_service()
    result = service.people().connections().list(
        resourceName="people/me",
        pageSize=max,
        personFields="names,emailAddresses,phoneNumbers"
    ).execute()
    contacts = []
    for p in result.get("connections", []):
        name = p.get("names", [{}])[0].get("displayName", "")
        email = p.get("emailAddresses", [{}])[0].get("value", "")
        phone = p.get("phoneNumbers", [{}])[0].get("value", "")
        resource = p.get("resourceName", "")
        contacts.append({"name": name, "email": email, "phone": phone, "resource": resource})
    return contacts

def add_google_contact(name, email="", phone=""):
    service = _get_service()
    body = {"names": [{"givenName": name}]}
    if email:
        body["emailAddresses"] = [{"value": email}]
    if phone:
        body["phoneNumbers"] = [{"value": phone}]
    result = service.people().createContact(body=body).execute()
    return result.get("resourceName", "")

def delete_google_contact(resource_name):
    service = _get_service()
    service.people().deleteContact(resourceName=resource_name).execute()

def sync_from_google():
    """Pull Google contacts into local contacts.json"""
    from contacts import _load, _save
    google = list_google_contacts()
    local = _load()
    local_names = {c["name"].lower() for c in local}
    added = 0
    for c in google:
        if c["name"] and c["name"].lower() not in local_names:
            local.append({"name": c["name"], "email": c["email"], "phone": c["phone"], "note": "", "resource": c["resource"]})
            added += 1
    _save(local)
    return f"Synced {added} new contacts from Google."

def sync_to_google():
    """Push local contacts to Google if they don't have a resource ID"""
    from contacts import _load, _save
    local = _load()
    updated = 0
    for c in local:
        if not c.get("resource"):
            resource = add_google_contact(c["name"], c.get("email",""), c.get("phone",""))
            c["resource"] = resource
            updated += 1
    _save(local)
    return f"Pushed {updated} local contacts to Google."

def full_sync():
    r1 = sync_from_google()
    r2 = sync_to_google()
    return f"{r1} {r2}"
