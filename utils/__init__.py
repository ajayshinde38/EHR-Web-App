"""Utils package initializer.

This file makes `utils` a regular Python package which ensures imports like
`from utils.records import ...` work consistently across different
execution environments (Streamlit, tests, or direct python). Keep this file
minimal to avoid heavy imports during package import time.
"""

# Optional: expose commonly used submodules for convenience (avoid heavy imports here)
__all__ = [
    'auth', 'database', 'file_storage', 'health_card', 'llm', 'mongodb_storage',
    'ocr_processor', 'advanced_ocr_processor', 'records', 'twilio_helper'
]
