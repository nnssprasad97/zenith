import utils
from .vision_engine import VisionEngine

def face_auth(params):
    """Handle face authentication intent"""
    engine = VisionEngine()
    result = engine.authenticate_face()
    
    if result.get('authenticated'):
        return utils.output('end', 'face_auth', utils.translate('face_auth'))
    else:
        return utils.output('end', 'error', 'Authentication failed.')

def ocr_scan(params):
    """Handle OCR scanning intent"""
    engine = VisionEngine()
    text = engine.extract_text()
    
    if text:
        return utils.output('end', 'ocr_scan', utils.translate('ocr_scan', text))
    else:
        return utils.output('end', 'error', 'No text could be extracted.')

def detect_person(params):
    """Handle person detection intent"""
    engine = VisionEngine()
    detected = engine.detect_person()
    
    if detected:
        return utils.output('end', 'detect_person', utils.translate('detect_person'))
    else:
        return utils.output('end', 'detect_person', 'No one is currently visible in the frame.')
