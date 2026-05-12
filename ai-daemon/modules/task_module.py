"""
JARVIS AI — Task Management Module
Handles local task lists saved in tasks.json.
"""

import os
import json
import logging

logger = logging.getLogger("jarvis.modules.task")
TASKS_FILE = os.path.join(os.path.dirname(__file__), "tasks.json")

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_tasks(tasks):
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump(tasks, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save tasks: {e}")

def add_task(text: str) -> str:
    if not text:
        return "Please specify what task to add."
    tasks = load_tasks()
    tasks.append({"text": text, "status": "pending"})
    save_tasks(tasks)
    return f"Task added: {text}"

def list_tasks() -> str:
    tasks = load_tasks()
    if not tasks:
        return "You have no tasks in your list."
    
    resp = "Your tasks are: "
    for i, t in enumerate(tasks, 1):
        resp += f"{i}. {t['text']} ({t['status']}). "
    return resp

def clear_tasks() -> str:
    save_tasks([])
    return "All tasks cleared."

def manage_tasks(entities: dict) -> str:
    action = entities.get("action", "list").lower()
    text = entities.get("text", entities.get("target", ""))
    
    if action == "add":
        return add_task(text)
    elif action == "clear" or action == "delete_all":
        return clear_tasks()
    else:
        return list_tasks()

CAPABILITIES = {
    "manage_tasks": {
        "handler": manage_tasks,
        "description": "Manage local task list (add, list, clear)",
    }
}
