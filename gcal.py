# -*- coding: utf-8 -*-
import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import pytz
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts"
]

TOKEN_FILE = os.path.expanduser("~/jarvis/token.json")

def get_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)

def get_upcoming_events(max_results=5):
    try:
        service = get_service()
        now = datetime.datetime.utcnow().isoformat() + "Z"
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        events = events_result.get("items", [])
        if not events:
            return "No upcoming events."
        summaries = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            if "T" in start:
                dt = datetime.datetime.fromisoformat(start)
                start_str = dt.strftime("%A %B %d at %I:%M %p")
            else:
                dt = datetime.datetime.fromisoformat(start)
                start_str = dt.strftime("%A %B %d")
            summaries.append(f"{start_str}: {event.get('summary', 'No title')}")
        return "\n".join(summaries)
    except Exception as e:
        return f"Calendar error: {str(e)}"

def add_event(title, date_str, time_str=None):
    try:
        service = get_service()
        if time_str:
            start = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end = start + datetime.timedelta(hours=1)
            event = {
                "summary": title,
                "start": {"dateTime": start.isoformat(), "timeZone": "America/New_York"},
                "end": {"dateTime": end.isoformat(), "timeZone": "America/New_York"},
            }
        else:
            event = {
                "summary": title,
                "start": {"date": date_str},
                "end": {"date": date_str},
            }
        service.events().insert(calendarId="primary", body=event).execute()
        return f"Event '{title}' added to your calendar."
    except Exception as e:
        return f"Failed to add event: {str(e)}"

def get_events_range(start_date, end_date, max_results=50):
    """Get events between two dates. Dates as YYYY-MM-DD strings."""
    try:
        service = get_service()

        tz = pytz.timezone('America/New_York')
        start_dt = tz.localize(datetime.datetime.strptime(start_date, '%Y-%m-%d'))
        end_dt = tz.localize(datetime.datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_dt.isoformat(),
            timeMax=end_dt.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        if not events:
            return f"No events between {start_date} and {end_date}."
        summaries = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                dt = datetime.datetime.fromisoformat(start)
                start_str = dt.strftime('%A %B %d at %I:%M %p')
            else:
                dt = datetime.datetime.fromisoformat(start)
                start_str = dt.strftime('%A %B %d')
            summaries.append(f"{start_str}: {event.get('summary', 'No title')}")
        return "\n".join(summaries)
    except Exception as e:
        return f"Calendar range error: {str(e)}"
