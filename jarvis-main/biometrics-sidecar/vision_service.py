"""
JARVIS — Vision & Identity Microservice
Combines YOLOv8n (person detection) + LBPH (face recognition) + Tesseract OCR
into a single authenticate_user() entrypoint.

Flow:
  1. YOLOv8n detects a person in the camera frame.
  2. The upper-body region (approx. face) is cropped and resized.
  3. cv2.face.LBPHFaceRecognizer verifies the identity against trainer.yml.
  4. Tesseract OCR is available as a utility for reading on-screen text.
  5. Returns {"authenticated": True/False, "user": name, "confidence": score}
"""

import cv2
import json
import logging
import os
import time
import numpy as np
from pathlib import Path

logger = logging.getLogger("jarvis.vision")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
YOLO_MODEL_PATH   = str(BASE_DIR / "yolov8n.pt")
TRAINER_PATH      = str(BASE_DIR / "Face Recognition" / "trainer" / "trainer.yml")
CASCADE_PATH      = str(BASE_DIR / "Face Recognition" / "haarcascade_frontalface_default.xml")
USERS_JSON        = str(BASE_DIR / "users.json")

CONFIDENCE_THRESHOLD = int(os.getenv("FACE_CONFIDENCE_THRESHOLD", "65"))

# ── Optional imports (graceful fallback) ───────────────────────────────────
try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False
    logger.warning("ultralytics not installed — falling back to Haar-only detection.")

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not installed — OCR unavailable.")

# ── Singletons ─────────────────────────────────────────────────────────────
_yolo_model      = None
_lbph_recognizer = None
_face_cascade    = None


def _load_user_names() -> dict:
    """Load {id: name} mapping from users.json."""
    if os.path.exists(USERS_JSON):
        try:
            with open(USERS_JSON) as f:
                return {int(k): v for k, v in json.load(f).items()}
        except Exception as e:
            logger.error(f"users.json parse error: {e}")
    return {1: "Manikanta"}


def get_yolo_model():
    global _yolo_model
    if _yolo_model is None and _YOLO_AVAILABLE:
        if not os.path.exists(YOLO_MODEL_PATH):
            raise FileNotFoundError(f"YOLOv8 model not found: {YOLO_MODEL_PATH}")
        logger.info("Loading YOLOv8n model…")
        _yolo_model = YOLO(YOLO_MODEL_PATH)
    return _yolo_model


def get_lbph_recognizer():
    global _lbph_recognizer
    if _lbph_recognizer is None:
        if not os.path.exists(TRAINER_PATH):
            raise FileNotFoundError(
                f"LBPH trainer not found: {TRAINER_PATH}\n"
                "Run 'Face Recognition/Model Trainer.py' first."
            )
        _lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
        _lbph_recognizer.read(TRAINER_PATH)
        logger.info("LBPH recognizer loaded from trainer.yml")
    return _lbph_recognizer


def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        xml_path = CASCADE_PATH if os.path.exists(CASCADE_PATH) else \
                   cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _face_cascade = cv2.CascadeClassifier(xml_path)
        logger.info(f"Haar cascade loaded from {xml_path}")
    return _face_cascade


# ── Detection helpers ──────────────────────────────────────────────────────

def _yolo_person_to_face_roi(frame: np.ndarray) -> list:
    """
    Use YOLOv8n to detect a person, then return the bounding box of the
    face region (top ~30% of the person bounding box, clamped to frame).
    Returns list of (x, y, w, h) tuples.
    """
    model = get_yolo_model()
    results = model(frame, stream=False, verbose=False)
    rois = []
    for r in results:
        for box in r.boxes:
            if int(box.cls[0]) != 0:      # class 0 = person
                continue
            x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            person_h = y2 - y1
            # Face occupies roughly the top 28% of a standing person
            face_y2 = y1 + int(person_h * 0.28)
            face_y2 = min(face_y2, frame.shape[0])
            x1 = max(0, x1)
            y1 = max(0, y1)
            w = x2 - x1
            h = face_y2 - y1
            if w > 20 and h > 20:
                rois.append((x1, y1, w, h))
    return rois


def _haar_detect_faces(gray: np.ndarray) -> list:
    """Haar cascade face detection as fallback or refinement."""
    cascade = get_face_cascade()
    faces = cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
    )
    return [tuple(f) for f in faces] if len(faces) > 0 else []


def detect_faces(frame: np.ndarray) -> list:
    """
    Unified detection pipeline:
      - If YOLO is available: YOLO → refine with Haar on cropped region
      - Else: pure Haar on full frame
    Returns list of (x, y, w, h) face bounding boxes.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)

    if _YOLO_AVAILABLE:
        person_rois = _yolo_person_to_face_roi(frame)
        all_faces = []
        for (px, py, pw, ph) in person_rois:
            roi_gray = gray[py:py + ph, px:px + pw]
            if roi_gray.size == 0:
                continue
            local_faces = _haar_detect_faces(roi_gray)
            for (fx, fy, fw, fh) in local_faces:
                # Translate back to full-frame coordinates
                all_faces.append((px + fx, py + fy, fw, fh))
            if not local_faces:
                # YOLO found a person but Haar didn't refine — use YOLO roi as face
                all_faces.append((px, py, pw, ph))
        return all_faces if all_faces else _haar_detect_faces(gray)
    else:
        return _haar_detect_faces(gray)


# ── OCR ───────────────────────────────────────────────────────────────────

def read_text_ocr(frame: np.ndarray, bbox: tuple = None) -> str:
    """
    Perform OCR on a frame or a specific bounding box (x, y, w, h).
    Returns extracted text string, or '' on failure / missing tesseract.
    """
    if not _TESSERACT_AVAILABLE:
        logger.warning("OCR requested but pytesseract is not installed.")
        return ""
    try:
        roi = frame[bbox[1]:bbox[1]+bbox[3], bbox[0]:bbox[0]+bbox[2]] if bbox else frame
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # THRESH_BINARY_INV + OTSU for dark-on-light and light-on-dark text
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        text = pytesseract.image_to_string(thresh, config="--psm 6").strip()
        return text
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return ""


# ── Main Authentication Function ───────────────────────────────────────────

def authenticate_user() -> dict:
    """
    Perform face authentication using the webcam.

    Pipeline:
      1. Open camera, warm-up 30 frames.
      2. Capture 20 frames, run detect_faces() on each.
      3. Run LBPH recognizer on each face ROI.
      4. Require majority vote (>50% of detection frames) with
         confidence < CONFIDENCE_THRESHOLD.

    Returns:
        {"authenticated": True, "user": "Manikanta", "confidence": 34.2}
        {"authenticated": False, "reason": "..."  }
    """
    try:
        recognizer = get_lbph_recognizer()
    except FileNotFoundError as e:
        return {"authenticated": False, "reason": str(e)}

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return {"authenticated": False, "reason": "Camera inaccessible"}

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    logger.info("Vision: warming up camera…")
    for _ in range(30):
        cap.read()

    user_names = _load_user_names()
    votes: list[dict] = []
    detection_frames = 0

    logger.info(f"Vision: scanning {20} frames for authentication…")
    for _ in range(20):
        ret, frame = cap.read()
        if not ret:
            continue

        faces = detect_faces(frame)
        if not faces:
            continue

        detection_frames += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Use the largest detected face for LBPH
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        # Clamp to frame boundaries
        fx, fy = max(0, fx), max(0, fy)
        fw = min(fw, frame.shape[1] - fx)
        fh = min(fh, frame.shape[0] - fy)

        face_roi = gray[fy:fy + fh, fx:fx + fw]
        if face_roi.size == 0:
            continue

        try:
            # Resize to 100×100 to match trainer (LBPH is resolution-sensitive)
            face_roi_resized = cv2.resize(face_roi, (100, 100))
            uid, conf = recognizer.predict(face_roi_resized)
            votes.append({"user_id": uid, "confidence": conf})
            logger.info(f"  Frame vote: user_id={uid}, confidence={conf:.1f}")
        except Exception as e:
            logger.debug(f"  LBPH predict error: {e}")

    cap.release()

    if not votes:
        return {"authenticated": False, "reason": "Could not detect a face in any frame"}

    # Filter votes below confidence threshold (lower = better in LBPH)
    good_votes = [v for v in votes if v["confidence"] < CONFIDENCE_THRESHOLD]
    logger.info(f"Vision: {len(good_votes)}/{len(votes)} votes passed confidence threshold (<{CONFIDENCE_THRESHOLD})")

    if len(good_votes) > len(votes) / 2:
        from collections import Counter
        uid_counts = Counter(v["user_id"] for v in good_votes)
        best_uid, _ = uid_counts.most_common(1)[0]
        user_name = user_names.get(best_uid, f"User_{best_uid}")
        best_conf = round(min(v["confidence"] for v in good_votes if v["user_id"] == best_uid), 1)
        logger.info(f"Vision: AUTHENTICATED — {user_name} (confidence={best_conf})")
        return {"authenticated": True, "user": user_name, "confidence": best_conf}
    else:
        logger.warning("Vision: REJECTED — face not recognised")
        return {"authenticated": False, "reason": "Unrecognised face"}
