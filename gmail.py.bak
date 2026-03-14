# -*- coding: utf-8 -*-
import os
import base64
import email
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/calendar"
]

CREDS_FILE = os.path.expanduser("~/jarvis/credentials.json")
TOKEN_FILE = os.path.expanduser("~/jarvis/token.json")

def get_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def get_unread_emails(max_results=5, structured=False):
    try:
        service = get_service()
        results = service.users().messages().list(
            userId="me", labelIds=["INBOX"], q="is:unread", maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return [] if structured else "No unread emails."
        items = []
        for msg in messages:
            data = service.users().messages().get(
                userId="me", id=msg["id"], format="full",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in data["payload"]["headers"]}
            sender = headers.get("From", "Unknown")
            subject = headers.get("Subject", "No subject")
            date = headers.get("Date", "")
            snippet = data.get("snippet", "")[:120]
            msg_id = msg["id"]
            items.append({
                "id": msg_id,
                "from": sender,
                "subject": subject,
                "date": date,
                "snippet": snippet
            })
        if structured:
            return items
        return "\n".join([f"From {i['from']}: {i['subject']}" for i in items])
    except Exception as e:
        return [] if structured else f"Gmail error: {str(e)}"

def search_emails(query, max_results=5):
    try:
        service = get_service()
        results = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return f"No emails found for: {query}"
        summaries = []
        for msg in messages:
            data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()
            headers = {h["name"]: h["value"] for h in data["payload"]["headers"]}
            sender = headers.get("From", "Unknown")
            subject = headers.get("Subject", "No subject")
            date = headers.get("Date", "")
            summaries.append(f"{date} — From {sender}: {subject}")
        return "\n".join(summaries)
    except Exception as e:
        return f"Gmail search error: {str(e)}"


def get_email_body(sender_query, subject_query=None, max_results=3):
    """Fetch the actual body of an email matching sender/subject."""
    try:
        service = get_service()
        q = f"from:{sender_query}"
        if subject_query:
            q += f" subject:{subject_query}"
        results = service.users().messages().list(
            userId="me", q=q, maxResults=max_results
        ).execute()
        messages = results.get("messages", [])
        if not messages:
            return f"No emails found matching that search."
        msg_id = messages[0]["id"]
        data = service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in data["payload"]["headers"]}
        sender = headers.get("From", "Unknown")
        subject = headers.get("Subject", "No subject")
        date = headers.get("Date", "")

        # Extract body
        body = ""
        payload = data.get("payload", {})
        if payload.get("body", {}).get("data"):
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        elif payload.get("parts"):
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                    break
            if not body:
                for part in payload["parts"]:
                    if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
                        import re
                        html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                        body = re.sub(r'<[^>]+>', ' ', html)
                        body = re.sub(r'\s+', ' ', body).strip()
                        break

        body = body.strip()[:3000]  # cap at 3000 chars
        return f"From: {sender}\nDate: {date}\nSubject: {subject}\n\n{body}"
    except Exception as e:
        return f"Gmail error: {str(e)}"

def send_email(to, subject, body):
    try:
        service = get_service()
        message = email.message.EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(
            userId="me", body={"raw": encoded}
        ).execute()
        return f"Email sent to {to}."
    except Exception as e:
        return f"Failed to send email: {str(e)}"
