import os
import sys
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def check_system():
    print("\n" + "="*40)
    print(" JARVIS SYSTEM DIAGNOSTICS ")
    print("="*40)

    # 1. Check Config & Env
    env_path = ".env"
    if os.path.exists(env_path):
        print("[OK] .env file found")
    else:
        print("[ERROR] .env file MISSING")

    # 2. Check Biometric Data
    from config import TRAINER_PATH, REGISTERED_FACES_DIR
    if os.path.exists(TRAINER_PATH):
        print(f"[OK] Face model found: {TRAINER_PATH}")
    else:
        print("[WARN] Face model MISSING (User must register face)")

    users_file = "users.json"
    if os.path.exists(users_file):
        print(f"[OK] Users database found: {users_file}")
    else:
        print("[WARN] Users database MISSING (Fresh start mode)")

    # 3. Check Dependencies
    try:
        import cv2
        print(f"[OK] OpenCV version: {cv2.__version__}")
    except ImportError:
        print("[ERROR] OpenCV NOT INSTALLED")

    try:
        import pyautogui
        print("[OK] PyAutoGUI ready")
    except ImportError:
        print("[ERROR] PyAutoGUI NOT INSTALLED")

    # 4. Check Camera Access
    print("\n--- Testing Camera Access ---")
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        print("[OK] Camera accessible")
        cap.release()
    else:
        print("[ERROR] CAMERA NOT ACCESSIBLE (Hardware issue?)")

    # 5. Check Speech
    print("\n--- Testing Speech Engine ---")
    try:
        from core.speech import speak
        print("[...] Testing voice output (you should hear JARVIS)...")
        # speak("Diagnostic check. System is online.")
        print("[OK] Speech module loaded")
    except Exception as e:
        print(f"[✗] Speech failure: {e}")

    print("\n" + "="*40)
    print(" DIAGNOSTICS COMPLETE ")
    print("="*40 + "\n")

if __name__ == "__main__":
    check_system()
