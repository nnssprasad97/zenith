"""
JARVIS AI — System Module (Upgraded)
Handles OS-level operations: open apps, shutdown, restart, lock, volume, brightness, etc.

NEW in v2:
  - Uses app_resolver for fuzzy app name matching
  - All outputs are clean strings
  - Better error handling
"""

import logging
import os
import platform
import subprocess

logger = logging.getLogger("jarvis.modules.system")


def open_app(app_name: str) -> str:
    """Open a desktop application by name using app_resolver."""
    if not app_name:
        return "Please tell me which application to open."

    app_lower = app_name.lower().strip()

    # Use app_resolver for intelligent matching
    from core.app_resolver import resolve_app, get_app_suggestions

    resolved = resolve_app(app_lower)
    if resolved:
        try:
            os.system(resolved["command"])
            logger.info(f"Opened app: {resolved['name']} ({resolved['command']})")
            return f"Opening {resolved['name']}"
        except Exception as e:
            logger.error(f"Failed to open {resolved['name']}: {e}")
            return f"Failed to open {resolved['name']}: {e}"

    # Not found — try running directly
    try:
        # Check if the command exists or try to start it
        if os.system(f"start {app_lower}") == 0:
            logger.info(f"Attempted to open app: {app_name}")
            return f"Attempting to open {app_name}"
        else:
            raise Exception("App not found")
    except Exception:
        # App fallback to YouTube
        from core.speech import speak, listen
        speak(f"Sir, no such app found for {app_name}. Would you like to play it on YouTube?")
        response = listen()
        
        if response and any(w in response.lower() for w in ["yes", "yeah", "sure", "play it"]):
            from modules.browser import search_youtube
            return search_youtube(app_name)
            
        return f"I couldn't find an application called '{app_name}'"


def shutdown_system() -> str:
    """Shutdown the system."""
    os.system("shutdown /s /t 5")
    return "Shutting down system in 5 seconds"


def restart_system() -> str:
    """Restart the system."""
    os.system("shutdown /r /t 5")
    return "Restarting system in 5 seconds"


def lock_system() -> str:
    """Lock the workstation."""
    os.system("rundll32.exe user32.dll,LockWorkStation")
    return "System locked"


def sleep_system() -> str:
    """Put system to sleep."""
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "System going to sleep"


def system_control(action: str) -> str:
    """Execute a system control action."""
    if not action:
        return "Please specify what system action to perform."

    actions = {
        "shutdown": shutdown_system,
        "restart": restart_system,
        "lock": lock_system,
        "sleep": sleep_system,
    }
    func = actions.get(action.lower())
    if func:
        return func()
    return f"Unknown system action: {action}. Available: shutdown, restart, lock, sleep."


def volume_control(action: str) -> str:
    """Control system volume."""
    if not action:
        return "Please specify: volume up, volume down, or mute."

    try:
        import pyautogui
        actions = {
            "volume_up": ("volumeup", "Volume increased"),
            "volume_down": ("volumedown", "Volume decreased"),
            "mute": ("volumemute", "Volume muted"),
        }
        key, msg = actions.get(action, (None, None))
        if key:
            pyautogui.press(key)
            return msg
        return f"Unknown volume action: {action}"
    except ImportError:
        logger.warning("pyautogui not installed for volume control")
        return "Volume control requires pyautogui to be installed."


def get_battery_status() -> str:
    """Get battery percentage."""
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            status = "plugged in" if battery.power_plugged else "on battery"
            return f"Battery is at {battery.percent}% ({status})"
        return "No battery detected — you might be on a desktop PC."
    except ImportError:
        return "Battery check requires psutil to be installed."


def get_system_info() -> str:
    """Get basic system information."""
    info = platform.uname()
    return (
        f"System: {info.system} {info.release}, "
        f"Machine: {info.machine}, "
        f"Processor: {info.processor}"
    )


def check_internet() -> str:
    """Check internet connectivity."""
    try:
        import requests
        requests.get("https://google.com", timeout=5)
        return "Internet connection is active."
    except Exception:
        return "Internet connection is not available."


def get_info(query: str) -> str:
    """Get system/general info based on query."""
    import datetime

    if not query:
        return "What information would you like?"

    query_lower = query.lower()

    if query_lower == "time":
        return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}"
    elif query_lower == "date":
        return f"Today is {datetime.datetime.now().strftime('%B %d, %Y')}"
    elif query_lower == "battery":
        return get_battery_status()
    elif query_lower == "system_info":
        return get_system_info()
    elif query_lower == "internet":
        return check_internet()
    elif query_lower == "joke":
        try:
            import pyjokes
            return pyjokes.get_joke()
        except ImportError:
            return "Why did the programmer quit? Because they didn't get arrays!"
    else:
        return f"I don't have info about '{query}'."


def get_weather(city: str = None) -> str:
    """Get weather for a city."""
    try:
        import requests
        from config import USER_CITY
        city = city or USER_CITY
        response = requests.get(f"https://wttr.in/{city}?format=3", timeout=10)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Weather error: {e}")
        return "Unable to fetch weather information right now."


def search_local_file(filename: str) -> str:
    """Search for a file in common user directories."""
    if not filename:
        return "Please specify a filename to search for."
    
    search_dirs = [
        os.path.expanduser("~/Desktop"),
        os.path.expanduser("~/Documents"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Videos"),
        os.path.expanduser("~/Music"),
        os.path.expanduser("~/Pictures"),
    ]
    
    logger.info(f"Searching for file: {filename}")
    found_files = []
    
    for d in search_dirs:
        if not os.path.exists(d): continue
        for root, dirs, files in os.walk(d):
            for f in files:
                if filename.lower() in f.lower():
                    found_files.append(os.path.join(root, f))
            if len(found_files) > 5: break # Cap results
            
    if found_files:
        resp = f"I found {len(found_files)} matching files. The first one is at: {found_files[0]}"
        if len(found_files) > 1:
            resp += f". There are also {len(found_files)-1} other matches."
        return resp
    
    return f"I couldn't find any file matching '{filename}' in your common folders."


def run_shell_command(command: str) -> str:
    """Execute a raw shell command."""
    if not command:
        return "No command provided."
    try:
        # Using subprocess for better control and security
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            output = result.stdout.strip()
            return f"Command executed successfully. Output: {output[:200]}"
        else:
            return f"Command failed with error: {result.stderr.strip()[:200]}"
    except Exception as e:
        return f"Failed to execute command: {e}"


def kill_process(process_name: str) -> str:
    """Kill a process by name with fuzzy matching."""
    if not process_name:
        return "Which process should I terminate?"
    
    # Common mappings
    proc_map = {
        "chrome": "chrome.exe",
        "browser": "chrome.exe",
        "code": "Code.exe",
        "vs code": "Code.exe",
        "explorer": "explorer.exe",
        "task manager": "taskmgr.exe",
        "whatsapp": "WhatsApp.exe",
        "spotify": "Spotify.exe",
    }
    
    target = proc_map.get(process_name.lower(), process_name)
    if not target.endswith(".exe") and platform.system() == "Windows":
        target += ".exe"

    try:
        # Use taskkill /f for forceful termination
        subprocess.run(["taskkill", "/F", "/IM", target], capture_output=True)
        logger.info(f"Terminated process: {target}")
        return f"Terminated {process_name}"
    except Exception as e:
        return f"Failed to terminate {process_name}: {e}"


def advanced_ui_control(app_name: str, action: str, target_element: str = "") -> str:
    """Elite level UI control using pywinauto."""
    try:
        from pywinauto import Application
        import pygetwindow as gw
        
        # Find window
        wins = gw.getWindowsWithTitle(app_name)
        if not wins:
            return f"Could not find window for {app_name}"
        
        # Connect to app
        app = Application(backend="uia").connect(title_re=f".*{app_name}.*", timeout=5)
        main_win = app.window(title_re=f".*{app_name}.*")
        
        if action == "click":
            # This is complex; for now we use fuzzy child window matching
            main_win.child_window(title_re=f".*{target_element}.*").click_input()
            return f"Clicked {target_element} in {app_name}"
        
        elif action == "type":
            main_win.type_keys(target_element, with_spaces=True)
            return f"Typed into {app_name}"
            
        return "Unknown advanced UI action"
    except Exception as e:
        logger.error(f"Advanced UI error: {e}")
        return f"Advanced UI control failed: {e}"


# Module capabilities for auto-registration
CAPABILITIES = {
    "open_app": {
        "handler": lambda entities: open_app(entities.get("app", "")),
        "description": "Open a desktop application",
    },
    "advanced_ui": {
        "handler": lambda entities: advanced_ui_control(
            app_name=entities.get("app", ""),
            action=entities.get("action", ""),
            target_element=entities.get("target", ""),
        ),
        "description": "Elite UI element interaction",
    },
    "system_control": {
        "handler": lambda entities: system_control(entities.get("action", "")),
        "description": "System control (shutdown, restart, lock, sleep)",
        "dangerous": True,
    },
    "volume_control": {
        "handler": lambda entities: volume_control(entities.get("action", "")),
        "description": "Control system volume",
    },
    "get_info": {
        "handler": lambda entities: get_info(entities.get("query", "")),
        "description": "Get system info, time, date, battery, jokes",
    },
    "weather": {
        "handler": lambda entities: get_weather(entities.get("city")),
        "description": "Get weather information",
    },
    "search_file": {
        "handler": lambda entities: search_local_file(entities.get("filename", entities.get("target", ""))),
        "description": "Search for local files",
    },
    "run_command": {
        "handler": lambda entities: run_shell_command(entities.get("command", "")),
        "description": "Execute shell commands",
        "dangerous": True,
    },
}
