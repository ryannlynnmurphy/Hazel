import os
import sys
import time
import signal
import datetime
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brain import ask, parse_actions
from voice import listen, speak, detect_mic
from memory import save_reminder, get_pending_reminders, mark_reminder_fired
from smarthome import execute_action
from gmail import get_unread_emails, search_emails, send_email
from contacts import get_all, add_contact, find_contact, delete_contact, contacts_summary
from gcal import get_upcoming_events, add_event, get_events_range
from hazel_ambient import start_ambient, trigger_now, invalidate_cache, set_interacting
from hzl_ws import broadcast_sync as broadcast, set_message_handler, start_ws_server
# from wakeword import start as start_wakeword  # disabled until custom model

print("=" * 50)
print("  Hazel — Personal AI Assistant")
print(f"  Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 50)

if not os.environ.get("JARVIS_MIC_CARD"):
    mic = detect_mic()
    os.environ["JARVIS_MIC_CARD"] = mic

RUNNING = True
SPEAKING = False

def shutdown(sig=None, frame=None):
    global RUNNING
    print("\n[Hazel] Shutting down...")
    RUNNING = False
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

def check_reminders():
    pending = get_pending_reminders()
    for reminder_id, message in pending:
        print(f"[Hazel] Reminder: {message}")
        broadcast({"type": "notify", "message": message, "priority": "reminder"})
        speak(f"Reminder: {message}")
        mark_reminder_fired(reminder_id)
        trigger_now("reminder fired")

def process_response(reply):
    clean_text, actions = parse_actions(reply)
    global SPEAKING
    if clean_text:
        broadcast({"state": "speaking", "transcript": clean_text})
        SPEAKING = True
        speak(clean_text)
        SPEAKING = False
        # Auto-save long structured responses as deliverables
        if len(clean_text) > 300 and any(marker in clean_text.lower() for marker in [
            "here's", "here is", "plan", "summary", "brief", "schedule", "list",
            "step", "option", "recommendation", "report", "outline", "draft"
        ]):
            import re as _re
            first_line = clean_text.strip().split("\n")[0][:60]
            broadcast({"type": "deliverable", "dtype": "document", "title": first_line, "content": clean_text})

    for action in actions:

        if action["type"] == "home":
            result = execute_action(action)
            print(f"[SmartHome] {result}")

        elif action["type"] == "reminder":
            try:
                now = datetime.datetime.now()
                hour, minute = map(int, action["time"].split(":"))
                remind_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if remind_at < now:
                    remind_at += datetime.timedelta(days=1)
                save_reminder(remind_at, action["message"])
                label = remind_at.strftime("%I:%M %p")
                print(f"[Reminder] Set for {label}: {action['message']}")
                broadcast({"type": "notify", "message": f"Reminder set for {label}: {action['message']}", "priority": "default"})
            except Exception as e:
                print(f"[Reminder] Error: {e}")

        elif action["type"] == "gmail":
            if action["command"] == "check":
                result = get_unread_emails()
                print(f"[Gmail] {result}")
                broadcast({"type": "email", "text": result})
                pass  # email summary disabled
            elif action["command"] == "search":
                result = search_emails(action["query"])
                print(f"[Gmail] {result}")
                broadcast({"type": "email", "text": result})
                pass  # search summary disabled
            elif action["command"] == "send":
                confirm_msg = f"Just to confirm — send this email to {action['to']} with subject '{action['subject']}'?"
                broadcast({"state": "speaking", "transcript": confirm_msg})
                speak(confirm_msg)
                broadcast({"type": "confirm", "confirm_type": "email", "action": action})
                broadcast({"state": "idle", "transcript": ""})

        elif action["type"] == "contact":
            cmd = action["command"]
            args = action["args"]
            if cmd == "list":
                result = contacts_summary()
                broadcast({"type": "contacts", "text": result})
                speak(result[:200] if len(result) > 200 else result)
            elif cmd == "add":
                parts = [p.strip() for p in args.split("|")]
                name  = parts[0] if len(parts) > 0 else ""
                email = parts[1] if len(parts) > 1 else ""
                phone = parts[2] if len(parts) > 2 else ""
                note  = parts[3] if len(parts) > 3 else ""
                result = add_contact(name, email, phone, note)
                broadcast({"type": "notify", "message": result})
                speak(result)
            elif cmd == "find":
                result = find_contact(args)
                broadcast({"type": "contacts", "text": result})
                speak(result)
            elif cmd == "delete":
                result = delete_contact(args)
                broadcast({"type": "notify", "message": result})
                speak(result)

        elif action["type"] == "gcal":
            if action["command"] == "check":
                result = get_upcoming_events()
                print(f"[Calendar] {result}")
                broadcast({"type": "calendar", "text": result})
                trigger_now("calendar updated")
                invalidate_cache("calendar")
            elif action["command"] == "add":
                confirm_msg = f"Should I add '{action['title']}' to your calendar on {action['date']}?"
                broadcast({"state": "speaking", "transcript": confirm_msg})
                speak(confirm_msg)
                broadcast({"type": "confirm", "confirm_type": "gcal_add", "action": action})
                broadcast({"state": "idle", "transcript": ""})
            elif action["command"] == "range":
                result = get_events_range(action["start"], action["end"])
                print(f"[Calendar] {result}")
                broadcast({"type": "calendar", "text": result})
                trigger_now("week view updated")

        elif action["type"] == "code":
            cmd = action["command"]
            if cmd == "run":
                from code_runner import run_code
                result = run_code(action["code"], action.get("language", "python"))
                speak(result[:300])
                broadcast({"type": "code_result", "text": result})
            elif cmd == "snippet_save":
                from coding import save_snippet
                result = save_snippet(action["name"], action["code"], action.get("language", "python"), action.get("description", ""))
                speak(result)
            elif cmd == "snippet_run":
                from coding import execute_snippet
                result = execute_snippet(action["name"])
                speak(result[:300])
                broadcast({"type": "code_result", "text": result})
            elif cmd == "snippet_list":
                from coding import list_snippets
                result = list_snippets()
                speak(result)
                broadcast({"type": "code_result", "text": result})

        elif action["type"] == "github":
            cmd = action["command"]
            from github_integration import list_repos, get_repo_files, get_recent_commits, push_file
            if cmd == "list":
                result = list_repos()
                speak(result[:300])
                broadcast({"type": "github", "text": result})
            elif cmd == "files":
                result = get_repo_files(action["repo"], action.get("path", ""))
                speak(result[:300])
                broadcast({"type": "github", "text": result})
            elif cmd == "commits":
                result = get_recent_commits(action["repo"])
                speak(result[:300])
                broadcast({"type": "github", "text": result})
            elif cmd == "push":
                result = push_file(action["repo"], action["filepath"], action["content"], action.get("message", "Update from Hazel"))
                speak(result)


def main():
    global RUNNING

    def handle_voice_input():
        broadcast({"state": "listening", "transcript": ""})
        heard = listen()
        if not heard:
            broadcast({"state": "idle", "transcript": ""})
            return
        broadcast({"state": "voice_input", "transcript": heard})
        handle_chat_input(heard)

    def handle_chat_input(text):
        set_interacting(True)
        pass  # chat handled by hzl_ws.py — disabled here
        set_interacting(False)

    def handle_ws_message(msg):
        if isinstance(msg, str):
            return handle_chat_input(msg)
        msg_type = msg.get("type")
        if msg_type == "confirm_yes":
            action = msg.get("action", {})
            ctype  = msg.get("confirm_type", "")
            if ctype == "email":
                to = action.get("to", "")
                result = send_email(to, action.get("subject", ""), action.get("body", ""))
                broadcast({"type": "notify", "message": f"Email sent to {to}", "priority": "default"})
                speak(result)
            elif ctype == "gcal_add":
                title  = action.get("title", "")
                result = add_event(title, action.get("date", ""), action.get("time"))
                broadcast({"type": "notify", "message": f"Added: {title}", "priority": "default"})
                speak(result)
        elif msg_type == "confirm_no":
            speak("Got it, cancelled.")
        elif msg_type == "voice":
            threading.Thread(target=handle_voice_input, daemon=True).start()
        else:
            handle_chat_input(msg.get("text", ""))

    set_message_handler(handle_ws_message)
    threading.Thread(target=start_ws_server, daemon=True).start()
    time.sleep(2)

    # start_ambient(broadcast)  # disabled — causes spam

    # startup speak disabled

    # Start wake word detection
    print("[Hazel] Ready — use mic button or chat to talk to Hazel.")
    last_reminder_check = time.time()

    while RUNNING:
        try:
            if time.time() - last_reminder_check > 30:
                check_reminders()
                last_reminder_check = time.time()
            time.sleep(5)
        except KeyboardInterrupt:
            shutdown()
            break
        except Exception as e:
            print(f"[Hazel] Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
