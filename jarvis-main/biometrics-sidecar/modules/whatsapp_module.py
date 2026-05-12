"""
JARVIS AI — WhatsApp Module
Handles WhatsApp messaging via Windows Desktop URI scheme and PyAutoGUI.
"""

import logging
import json
import os
import time
import subprocess
import urllib.parse
import pyautogui

logger = logging.getLogger("jarvis.modules.whatsapp")

_CONTACTS_FILE = os.path.join(os.path.dirname(__file__), "contacts.json")

def _load_contacts():
    """Load contact mapping from JSON."""
    if os.path.exists(_CONTACTS_FILE):
        try:
            with open(_CONTACTS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load contacts: {e}")
    return {"prasad": "+911234567890"}  # Default placeholder

def _resolve_contact(name: str) -> str:
    """Convert name to phone number."""
    contacts = _load_contacts()
    # Handle potential None values or mismatched casing
    return contacts.get(str(name).lower().strip(), name)

def send_whatsapp(recipient: str, body: str = "", **kwargs) -> str:
    """
    Send a WhatsApp message autonomously.
    """
    if not recipient:
        return "No recipient specified."
    if not body:
        return "No message body specified."

    # Resolve contact name to number and clean formatting
    phone = _resolve_contact(recipient).replace(" ", "").replace("-", "")
    
    if not phone.startswith("+") and not phone.isdigit():
        return f"I don't have a phone number for '{recipient}'. Please add them to my contacts."

    if not phone.startswith("+"):
        phone = f"+91{phone}"

    try:
        # Format the message for the URI
        encoded_message = urllib.parse.quote(body)
        
        # Use the WhatsApp desktop app URI scheme
        whatsapp_uri = f"whatsapp://send/?phone={phone}&text={encoded_message}"
        
        logger.info(f"Opening Local WhatsApp for {phone}...")
        
        # Start the local app
        # Using start "" prevents command prompt window hanging on Windows
        subprocess.run(f'start "" "{whatsapp_uri}"', shell=True)
        
        # Give the app time to open, load the chat, and establish focus
        # 5 seconds is usually good, but consider 7 if cold-starting WhatsApp
        time.sleep(6) 
        
        # Press Enter to send the message
        pyautogui.press("enter")
        
        logger.info(f"Local WhatsApp message triggered for {phone}")
        return f"Message sent to {recipient}"
        
    except Exception as e:
        logger.error(f"Local WhatsApp error: {e}")
        return f"Failed to send via local app: {e}"

# Module capabilities
CAPABILITIES = {
    "send_whatsapp": {
        "handler": lambda entities: send_whatsapp(
            recipient=entities.get("recipient", entities.get("contact", "")),
            body=entities.get("body", entities.get("message", "")),
        ),
        "description": "Send an autonomous WhatsApp message",
    },
}