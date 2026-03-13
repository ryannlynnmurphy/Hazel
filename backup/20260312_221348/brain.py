# -*- coding: utf-8 -*-
import anthropic
import os
import re
import datetime
from memory import save_message, get_recent, get_all_facts
from weather import get_weather
from gmail import get_unread_emails, search_emails, send_email
from gcal import get_upcoming_events, add_event, get_events_range
from search import web_search
from contacts import add_contact, find_contact, delete_contact, contacts_summary
from integrations import parse_and_route, INTEGRATION_PROMPT

client = anthropic.Anthropic()

COMPLEX_KEYWORDS = r"(explain|analyze|debug|code|write|compare|how does|build|create|script|program|difference between|essay|poem|email|send|draft|brief|journal|project)"

def get_model(user_message):
    if re.search(COMPLEX_KEYWORDS, user_message.lower()):
        return "claude-sonnet-4-5"
    return "claude-haiku-4-5-20251001"

def _get_health_context():
    try:
        from health import get_health_context
        return get_health_context()
    except Exception:
        return ""
def _get_creative_context():
    try:
        from creative import get_creative_context, get_focus_state
        ctx = get_creative_context()
        focus = get_focus_state()
        return ctx, focus
    except Exception:
        return "", None

def build_system_prompt():
    facts = get_all_facts()
    facts_text = ""
    if facts:
        lines = [f"  - {k}: {v}" for _, k, v in facts]
        facts_text = "\n\nThings I know about you:\n" + "\n".join(lines)

    now = datetime.datetime.now().strftime("%A, %B %d %Y at %I:%M %p")
    weather = get_weather()
    weather_text = f"\nCurrent weather in Garden City, NY: {weather}" if weather else ""

    # Creative context injection
    creative_ctx, focus_state = _get_creative_context()
    creative_text = f"\n\n## CREATIVE CONTEXT\n{creative_ctx}" if creative_ctx else ""
    focus_text = ""
    if focus_state:
        flow = " — in flow state, do not interrupt unless urgent" if focus_state["in_flow"] else ""
        focus_text = f"\n\nFOCUS MODE ACTIVE{flow}: {focus_state['elapsed_min']} min on {focus_state['project'] or 'general work'}. Keep responses brief."

    # Health context injection
    health_ctx = _get_health_context()
    health_text = f"\n\n## HEALTH CONTEXT\n{health_ctx}" if health_ctx else ""

    return f"""You are Hazel — a personal AI assistant built by Ryann Murphy, running locally on a Raspberry Pi 5 as part of HZL AI.
You are sharp, warm, and direct. You never waste words. You follow through on everything you say you will do.
Ryann is a multi-hyphenate creative: visual designer, photographer, writer, marketer, AI developer, theatre maker, film/TV producer, musician.
Current date and time: {now}{weather_text}{facts_text}{creative_text}{focus_text}{health_text}

## CORE RULES
- Keep responses to 1-3 sentences unless more detail is requested.
- Never open with filler: no "Certainly!", "Of course!", "Great question!", "Sure!", or "Absolutely!"
- Never say "let me pull that up" or "I'll check that for you" and then not do it. Always follow through immediately.
- Never say you "can't access" something you have a tag for.
- Be confident. Answer directly. If you don't know something, say so plainly.
- If the user asks you to remember something, confirm it.

## FOLLOW-THROUGH RULES
- When asked about a news topic, ALWAYS use [NEWS: search QUERY] to get current info, then give a full summary. Never give a surface answer on news.
- When asked about a calendar event, use [GCAL: check] or [GCAL: range] to pull details before responding.
- When asked to research or explain something, use [SEARCH: query] to get current information first.
- When a topic has multiple angles, address all of them — do not stop at one sentence if depth is needed.
- Chain actions when necessary: search → summarize → suggest next steps.
- When generating a long structured response (plan, brief, summary, code), also send [NOTIFY: deliverable ready] so the UI captures it.
- Always finish what you start. If you say you will do something, do it in the same response.

## EMAIL RULES
- Always write emails with proper structure: greeting, body, sign-off.
- Greeting: "Hi [Name]," or "Dear [Name]," depending on tone.
- Sign-off: Always close with a suitable valediction and Ryann's name.
- Match tone to context — professional for work, warm for personal.
- Format the full email in the BODY field of [GMAIL: send TO|SUBJECT|BODY].

## CALENDAR RULES
- Next few events: [GCAL: check]
- Add event: [GCAL: add TITLE|YYYY-MM-DD|HH:MM]
- Any week/range request: MUST use [GCAL: range YYYY-MM-DD|YYYY-MM-DD]

## CREATIVE RULES
- When Ryann mentions a new project, create it: [PROJECT: create NAME|DISCIPLINE|BRIEF]
- When Ryann says "focus mode", "I'm going in", or "deep work": [FOCUS: start PROJECT_NAME]
- When Ryann says "focus off", "I'm done", "taking a break": [FOCUS: end]
- When Ryann wants to journal or think out loud: [JOURNAL: ENTRY TEXT]
- When Ryann asks for a creative brief: [BRIEF: PROJECT_ID|CLIENT|OBJECTIVE|AUDIENCE|DELIVERABLES|DEADLINE|TONE]
- When Ryann asks "what am I working on" or "my projects": [PROJECT: list]
- When Ryann asks about energy or what to work on: [ENERGY: check]
- When Ryann asks for a daily debrief or end-of-day summary: [DEBRIEF: today]
- Disciplines: visual_design, photography, writing, marketing, ai_development, theatre, film_tv, music, audio

## HEALTH RULES
- Log mood: [MOOD: label|score|energy|notes] — label: great/good/okay/low/rough/anxious/energized/tired
- Log sleep: [SLEEP: bedtime HH:MM|wake HH:MM|quality 1-10|notes]
- Log exercise: [EXERCISE: type|duration_min|intensity|notes] — intensity: light/moderate/intense
- Log medication taken: [MED: taken NAME|dose]
- Add new medication: [MED: add NAME|dose|frequency|times HH:MM,HH:MM]
- Remove medication: [MED: remove NAME]
- Health summary: [HEALTH: summary]
- When Ryann mentions how they feel, their sleep, or working out — log it automatically with the right tag
- When Ryann says "I took my meds" or similar — log it
- Check for missed meds if it's past their scheduled time and no log exists
Smart Home: [ACTION: turn_on/turn_off ENTITY_ID]
Reminders: [REMINDER: HH:MM MESSAGE]
Gmail: [GMAIL: check] / [GMAIL: search QUERY] / [GMAIL: send TO|SUBJECT|BODY]
Code: [CODE: run LANGUAGE|CODE] / [CODE: snippet_save NAME|LANGUAGE|CODE] / [CODE: snippet_run NAME] / [CODE: snippet_list]
GitHub: [GITHUB: list] / [GITHUB: files REPO|PATH] / [GITHUB: commits REPO] / [GITHUB: push REPO|FILEPATH|CONTENT|MESSAGE]
Contacts: [CONTACT: find NAME] / [CONTACT: add NAME|EMAIL|PHONE] / [CONTACT: delete NAME] / [CONTACT: list]
Calendar: [GCAL: check] / [GCAL: range START|END] / [GCAL: add TITLE|DATE|TIME]
Search: [SEARCH: query]
Spotify: [SPOTIFY: play QUERY] / [SPOTIFY: pause] / [SPOTIFY: skip] / [SPOTIFY: previous] / [SPOTIFY: volume LEVEL] / [SPOTIFY: now_playing] / [SPOTIFY: queue QUERY]
Tasks: [TASK: check] / [TASK: add CONTENT|DUE] / [TASK: done NAME]
News: [NEWS: headlines CATEGORY] / [NEWS: search QUERY]
Notifications: [NOTIFY: MESSAGE] / [NOTIFY: urgent MESSAGE] / [NOTIFY: reminder MESSAGE]
Shopping: [SHOP: check] / [SHOP: add ITEM|QTY] / [SHOP: add_many ITEMS] / [SHOP: remove ITEM] / [SHOP: clear]
Code: [CODE: run LANGUAGE|CODE] / [CODE: snippet_save NAME|LANGUAGE|CODE] / [CODE: snippet_run NAME] / [CODE: snippet_list]
GitHub: [GITHUB: list] / [GITHUB: files REPO|PATH] / [GITHUB: commits REPO] / [GITHUB: push REPO|FILEPATH|CONTENT|MESSAGE]
Contacts: [CONTACT: list] / [CONTACT: find NAME] / [CONTACT: add NAME|EMAIL|PHONE|NOTE] / [CONTACT: delete NAME]
Health: [MOOD: label|score|energy|notes] / [SLEEP: bedtime|wake|quality|notes] / [EXERCISE: type|duration|intensity|notes] / [MED: taken NAME] / [MED: add NAME|dose|freq|times] / [MED: remove NAME] / [HEALTH: summary]
Creative: [PROJECT: create NAME|DISCIPLINE|BRIEF] / [PROJECT: list] / [FOCUS: start NAME] / [FOCUS: end] / [JOURNAL: TEXT] / [BRIEF: fields] / [ENERGY: check] / [DEBRIEF: today]

## CRITICAL
- Strip ALL action tags from spoken responses. Never read a tag aloud.
- When a user asks for something that needs a tag, emit the tag in the SAME response immediately.
- Only use [NOTIFY:] when the user explicitly asks to be notified or sets a reminder.""" + INTEGRATION_PROMPT


def auto_inject_calendar_tag(user_message):
    keywords = ['weekly', 'this week', 'next week', 'week ahead', 'rest of the week',
                'thursday through', 'friday through', 'rundown', 'briefing', 'week brief']
    lower = user_message.lower()
    if any(k in lower for k in keywords):
        today = datetime.date.today()
        days_until_sunday = 6 - today.weekday() if today.weekday() != 6 else 0
        end = today + datetime.timedelta(days=max(days_until_sunday, 6))
        tag = f"[GCAL: range {today.isoformat()}|{end.isoformat()}]"
        return tag
    return None


def _handle_creative_actions(reply):
    """Parse and execute creative action tags. Returns cleaned reply."""
    clean = reply

    try:
        from creative import (
            create_project, get_active_projects, enter_focus_mode, exit_focus_mode,
            add_journal_entry, save_brief, infer_energy_from_calendar,
            get_task_recommendations, build_daily_debrief, get_focus_stats
        )
        from memory import get_all_facts

        # PROJECT: create
        for match in re.finditer(r'\[PROJECT:\s*create\s+([^\|]+)\|?([^\|]*)\|?([^\]]*)\]', reply, re.IGNORECASE):
            name = match.group(1).strip()
            discipline = match.group(2).strip() or None
            brief = match.group(3).strip() or None
            pid = create_project(name, discipline=discipline, brief=brief)
            print(f"[Creative] Project created: {name} (id={pid})")
            clean = clean.replace(match.group(0), "").strip()

        # PROJECT: list — inject list into reply
        for match in re.finditer(r'\[PROJECT:\s*list\]', reply, re.IGNORECASE):
            projects = get_active_projects()
            if projects:
                proj_text = ", ".join(p["name"] for p in projects)
            else:
                proj_text = "No active projects."
            clean = clean.replace(match.group(0), proj_text).strip()

        # FOCUS: start
        for match in re.finditer(r'\[FOCUS:\s*start\s*([^\]]*)\]', reply, re.IGNORECASE):
            project = match.group(1).strip() or None
            enter_focus_mode(project)
            clean = clean.replace(match.group(0), "").strip()

        # FOCUS: end
        for match in re.finditer(r'\[FOCUS:\s*end\]', reply, re.IGNORECASE):
            exit_focus_mode()
            clean = clean.replace(match.group(0), "").strip()

        # JOURNAL: entry
        for match in re.finditer(r'\[JOURNAL:\s*([^\]]+)\]', reply, re.IGNORECASE):
            entry = match.group(1).strip()
            add_journal_entry(entry)
            print(f"[Creative] Journal entry saved.")
            clean = clean.replace(match.group(0), "").strip()

        # BRIEF: create
        for match in re.finditer(r'\[BRIEF:\s*([^\]]+)\]', reply, re.IGNORECASE):
            parts = [p.strip() for p in match.group(1).split("|")]
            try:
                save_brief(
                    project_id=int(parts[0]) if parts[0].isdigit() else 0,
                    title=parts[0] if not parts[0].isdigit() else "Brief",
                    client=parts[1] if len(parts) > 1 else None,
                    objective=parts[2] if len(parts) > 2 else None,
                    audience=parts[3] if len(parts) > 3 else None,
                    deliverables=parts[4] if len(parts) > 4 else None,
                    deadline=parts[5] if len(parts) > 5 else None,
                    tone=parts[6] if len(parts) > 6 else None,
                )
                print(f"[Creative] Brief saved.")
            except Exception as e:
                print(f"[Creative] Brief save error: {e}")
            clean = clean.replace(match.group(0), "").strip()

        # ENERGY: check
        for match in re.finditer(r'\[ENERGY:\s*check\]', reply, re.IGNORECASE):
            try:
                from gcal import get_upcoming_events
                cal = get_upcoming_events(max_results=5)
                events = cal.split("\n") if cal else []
                level = infer_energy_from_calendar(events)
                rec = get_task_recommendations(level)
                energy_text = f"Energy reading: {level}. {rec}"
            except Exception:
                energy_text = "Energy check unavailable."
            clean = clean.replace(match.group(0), energy_text).strip()

        # DEBRIEF: today
        for match in re.finditer(r'\[DEBRIEF:\s*today\]', reply, re.IGNORECASE):
            debrief = build_daily_debrief()
            clean = clean.replace(match.group(0), debrief).strip()

    except Exception as e:
        print(f"[Creative] Action handler error: {e}")

    return clean


def ask(user_message, use_history=True):
    try:
        save_message("user", user_message)
        if use_history:
            auto_tag = auto_inject_calendar_tag(user_message)
            if auto_tag:
                return auto_tag
        messages = []
        if use_history:
            recent = get_recent(20)
            messages = [{"role": r, "content": c} for r, c in recent]
        else:
            messages = [{"role": "user", "content": user_message}]
        model = get_model(user_message)
        print(f"[Brain] Using model: {model}")
        response = client.messages.create(
            model=model,
            max_tokens=512,
            system=build_system_prompt(),
            messages=messages,
        )
        reply = response.content[0].text
        save_message("assistant", reply)
        return reply
    except anthropic.APIConnectionError:
        return "I'm having trouble connecting to the internet. Check your connection and try again."
    except anthropic.AuthenticationError:
        return "API key error. Please check your ANTHROPIC_API_KEY."
    except anthropic.RateLimitError:
        return "Too many requests right now. Give me a moment and try again."
    except Exception as e:
        return f"Something went wrong: {str(e)}"


def parse_actions(reply):
    actions = []
    clean = reply

    # Health actions
    try:
        from health import (log_mood, log_sleep, log_exercise,
                            log_medication_taken, add_medication,
                            remove_medication, get_health_summary)

        for match in re.finditer(r'\[MOOD:\s*([^\]]+)\]', clean, re.IGNORECASE):
            parts = [p.strip() for p in match.group(1).split("|")]
            label = parts[0] if parts else None
            score = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            energy = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            notes = parts[3] if len(parts) > 3 else None
            log_mood(mood_label=label, score=score, energy=energy, notes=notes)
            clean = clean.replace(match.group(0), "").strip()

        for match in re.finditer(r'\[SLEEP:\s*([^\]]+)\]', clean, re.IGNORECASE):
            parts = [p.strip() for p in match.group(1).split("|")]
            bedtime = parts[0] if parts else "23:00"
            wake = parts[1] if len(parts) > 1 else "07:00"
            quality = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
            notes = parts[3] if len(parts) > 3 else None
            log_sleep(bedtime, wake, quality=quality, notes=notes)
            clean = clean.replace(match.group(0), "").strip()

        for match in re.finditer(r'\[EXERCISE:\s*([^\]]+)\]', clean, re.IGNORECASE):
            parts = [p.strip() for p in match.group(1).split("|")]
            etype = parts[0] if parts else "workout"
            duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
            intensity = parts[2] if len(parts) > 2 else None
            notes = parts[3] if len(parts) > 3 else None
            log_exercise(etype, duration_min=duration, intensity=intensity, notes=notes)
            clean = clean.replace(match.group(0), "").strip()

        for match in re.finditer(r'\[MED:\s*taken\s+([^\]]+)\]', clean, re.IGNORECASE):
            parts = [p.strip() for p in match.group(1).split("|")]
            name = parts[0]
            dose = parts[1] if len(parts) > 1 else None
            log_medication_taken(name, dose=dose)
            clean = clean.replace(match.group(0), "").strip()

        for match in re.finditer(r'\[MED:\s*add\s+([^\]]+)\]', clean, re.IGNORECASE):
            parts = [p.strip() for p in match.group(1).split("|")]
            name = parts[0]
            dose = parts[1] if len(parts) > 1 else None
            freq = parts[2] if len(parts) > 2 else None
            times = parts[3].split(",") if len(parts) > 3 else []
            add_medication(name, dose=dose, frequency=freq, times=times)
            clean = clean.replace(match.group(0), "").strip()

        for match in re.finditer(r'\[MED:\s*remove\s+([^\]]+)\]', clean, re.IGNORECASE):
            remove_medication(match.group(1).strip())
            clean = clean.replace(match.group(0), "").strip()

        for match in re.finditer(r'\[HEALTH:\s*summary\]', clean, re.IGNORECASE):
            summary = get_health_summary()
            clean = clean.replace(match.group(0), summary).strip()

    except Exception as e:
        print(f"[Health] Action handler error: {e}")

    # Creative actions first
    clean = _handle_creative_actions(clean)

    for match in re.finditer(r'\[ACTION:\s*(turn_on|turn_off)\s+([^\]]+)\]', reply):
        actions.append({"type": "home", "command": match.group(1), "entity": match.group(2).strip()})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[REMINDER:\s*(\d{1,2}:\d{2})\s+([^\]]+)\]', reply):
        actions.append({"type": "reminder", "time": match.group(1), "message": match.group(2).strip()})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[GMAIL:\s*check\]', reply, re.IGNORECASE):
        actions.append({"type": "gmail", "command": "check"})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[GMAIL:\s*search\s+([^\]]+)\]', reply, re.IGNORECASE):
        actions.append({"type": "gmail", "command": "search", "query": match.group(1).strip()})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[GMAIL:\s*send\s+([^\|]+)\|([^\|]+)\|([^\]]+)\]', reply, re.IGNORECASE):
        actions.append({"type": "gmail", "command": "send",
                        "to": match.group(1).strip(), "subject": match.group(2).strip(),
                        "body": match.group(3).strip()})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[GCAL:\s*range\s+([\d-]+)\|([\d-]+)\]', reply, re.IGNORECASE):
        actions.append({"type": "gcal", "command": "range",
                        "start": match.group(1), "end": match.group(2)})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[GCAL:\s*check\]', reply, re.IGNORECASE):
        actions.append({"type": "gcal", "command": "check"})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[GCAL:\s*add\s+([^\|]+)\|([^\|]+)\|?([^\]]*)\]', reply, re.IGNORECASE):
        actions.append({"type": "gcal", "command": "add",
                        "title": match.group(1).strip(), "date": match.group(2).strip(),
                        "time": match.group(3).strip() or None})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r'\[SEARCH:\s*([^\]]+)\]', reply, re.IGNORECASE):
        query = match.group(1).strip()
        search_result = web_search(query)
        summary_prompt = f"Based on these search results, give a concise 1-2 sentence answer to: '{query}'\n\nResults:\n{search_result}"
        summary = ask(summary_prompt, use_history=False)
        actions.append({"type": "search", "result": summary})
        clean = clean.replace(match.group(0), summary).strip()

    for match in re.finditer(r'\[CONTACT:\s*([^\]]+)\]', reply, re.IGNORECASE):
        raw = match.group(1).strip()
        cmd = raw.split()[0].lower()
        args = raw[len(cmd):].strip()
        actions.append({"type": "contact", "command": cmd, "args": args})
        clean = clean.replace(match.group(0), "").strip()

    for match in re.finditer(r"\[CODE:\s*(run|snippet_save|snippet_run|snippet_list)\s*([^\]]*?)\]", reply, re.IGNORECASE):
        parts = match.group(2).split("|")
        cmd = match.group(1).lower()
        if cmd == "run":
            actions.append({"type": "code", "command": "run", "language": parts[0].strip() if parts else "python", "code": parts[1].strip() if len(parts) > 1 else ""})
        elif cmd == "snippet_save":
            actions.append({"type": "code", "command": "snippet_save", "name": parts[0].strip() if parts else "", "language": parts[1].strip() if len(parts) > 1 else "python", "code": parts[2].strip() if len(parts) > 2 else ""})
        elif cmd in ("snippet_run", "snippet_list"):
            actions.append({"type": "code", "command": cmd, "name": parts[0].strip() if parts else ""})
        clean = clean.replace(match.group(0), "").strip()
    for match in re.finditer(r"\[GITHUB:\s*(list|files|commits|push)\s*([^\]]*?)\]", reply, re.IGNORECASE):
        parts = match.group(2).split("|")
        cmd = match.group(1).lower()
        a = {"type": "github", "command": cmd}
        if cmd == "files": a.update({"repo": parts[0].strip() if parts else "", "path": parts[1].strip() if len(parts) > 1 else ""})
        elif cmd == "commits": a["repo"] = parts[0].strip() if parts else ""
        elif cmd == "push": a.update({"repo": parts[0].strip() if parts else "", "filepath": parts[1].strip() if len(parts) > 1 else "", "content": parts[2].strip() if len(parts) > 2 else "", "message": parts[3].strip() if len(parts) > 3 else "Update from Hazel"})
        actions.append(a)
        clean = clean.replace(match.group(0), "").strip()
    parse_and_route(reply)
    return clean, actions
