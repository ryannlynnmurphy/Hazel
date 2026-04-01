import json, os, re
_HZL_DIR = os.path.dirname(os.path.abspath(__file__))
CONTACTS_FILE = os.path.join(_HZL_DIR, "contacts.json")

def _load():
    if not os.path.exists(CONTACTS_FILE):
        return []
    with open(CONTACTS_FILE) as f:
        return json.load(f)

def _save(contacts):
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)

def get_all():
    return _load()

def add_contact(name, email="", phone="", note=""):
    contacts = _load()
    contacts.append({"name":name,"email":email,"phone":phone,"note":note})
    _save(contacts)
    return f"Contact saved: {name}"

def find_contact(query):
    q = query.lower()
    return [c for c in _load() if q in c["name"].lower() or q in c.get("email","").lower()]

def delete_contact(name):
    contacts = [c for c in _load() if c["name"].lower() != name.lower()]
    _save(contacts)
    return f"Removed {name} from contacts"

def contacts_summary():
    contacts = _load()
    if not contacts:
        return "No contacts saved."
    return "\n".join([f"{c['name']} — {c.get('email','')} {c.get('phone','')}".strip() for c in contacts])
