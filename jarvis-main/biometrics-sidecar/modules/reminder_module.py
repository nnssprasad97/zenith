"""
JARVIS AI — Reminder Module
Handles scheduling and listing reminders.
"""

import os
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("jarvis.modules.reminder")
REMINDERS_FILE = os.path.join(os.path.dirname(__file__), "reminders.json")

def load_reminders():
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_reminders(reminders):
    try:
        with open(REMINDERS_FILE, "w") as f:
            json.dump(reminders, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save reminders: {e}")

def add_reminder(text: str, time_str: str) -> str:
    """Add a reminder. time_str can be 'in 5 minutes' or a specific time."""
    if not text:
        return "What should I remind you about?"
    
    # Simple time parsing for 'in X minutes'
    target_time = None
    if "minute" in time_str:
        try:
            mins = int(''.join(filter(str.isdigit, time_str)))
            target_time = datetime.now() + timedelta(minutes=mins)
        except ValueError:
            pass
    elif "hour" in time_str:
        try:
            hrs = int(''.join(filter(str.isdigit, time_str)))
            target_time = datetime.now() + timedelta(hours=hrs)
        except ValueError:
            pass
            
    if not target_time:
        # Fallback to 10 minutes if parsing fails
        target_time = datetime.now() + timedelta(minutes=10)
        time_str = "10 minutes (default)"

    reminders = load_reminders()
    reminders.append({
        "text": text,
        "time": target_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "pending"
    })
    save_reminders(reminders)
    return f"Reminder set: {text} at {target_time.strftime('%I:%M %p')}"

def list_reminders() -> str:
    reminders = load_reminders()
    if not reminders:
        return "You have no pending reminders."
    
    resp = "Your upcoming reminders are: "
    for r in reminders:
        if r['status'] == 'pending':
            resp += f"{r['text']} at {r['time']}. "
    return resp

def manage_reminders(entities: dict) -> str:
    action = entities.get("action", "add").lower()
    text = entities.get("text", entities.get("target", ""))
    time_info = entities.get("time", "10 minutes")
    
    if action == "list":
        return list_reminders()
    else:
        return add_reminder(text, time_info)

CAPABILITIES = {
    "schedule_reminder": {
        "handler": manage_reminders,
        "description": "Schedule and manage reminders",
    }
}
