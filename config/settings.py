"""
Configuration settings for EHR Web App
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Automatically sync Streamlit Cloud secrets into os.environ
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        for key, value in st.secrets.items():
            if isinstance(value, (str, int, float, bool)):
                os.environ[str(key)] = str(value)
except Exception:
    pass

# Application Configuration
APP_CONFIG = {
    "app_name": "EHR Web App",
    "version": "1.0.0",
    "debug": True,
    "max_file_size": 10 * 1024 * 1024,  # 10MB
    "allowed_file_types": ["pdf", "txt", "docx", "jpg", "jpeg", "png"]
}

# MongoDB Configuration
MONGODB_CONFIG = {
    "connection_string": os.getenv("MONGODB_CONNECTION_STRING", "mongodb://localhost:27017/"),
    "database_name": os.getenv("MONGODB_DATABASE", "ehr_app"),
    "collections": {
        "users": "users",
        "records": "medical_records",
        "assignments": "assignments",
        "files": "files",
        "file_metadata": "file_metadata"
    },
    "gridfs": {
        "bucket_name": "medical_files",
        "chunk_size": 255 * 1024  # 255KB chunks
    }
}

# Hugging Face Configuration
HUGGINGFACE_CONFIG = {
    "model_name": os.getenv("HF_MODEL_NAME", "facebook/bart-large-cnn"),
    "max_length": 150,
    "min_length": 50,
    "do_sample": False,
    "api_token": os.getenv("HUGGINGFACE_API_TOKEN", None)
}

# Security Configuration
SECURITY_CONFIG = {
    "secret_key": os.getenv("SECRET_KEY", "your-secret-key-here"),
    "bcrypt_rounds": 12,
    "session_timeout": 3600  # 1 hour
}

# File Upload Configuration
UPLOAD_CONFIG = {
    "upload_folder": "uploads",
    "max_file_size": 50 * 1024 * 1024,  # 50MB for medical images
    "allowed_extensions": {'.pdf', '.txt', '.docx', '.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
}

# File Storage Configuration - MongoDB GridFS
STORAGE_CONFIG = {
    "storage_type": "mongodb_gridfs",  # Changed from local to MongoDB
    "max_file_size": 50 * 1024 * 1024,  # 50MB
    "thumbnail_size": (200, 200),
    "gridfs_bucket": "medical_files",
    "supported_formats": {
        "images": [".jpg", ".jpeg", ".png", ".tiff", ".bmp"],
        "documents": [".pdf", ".doc", ".docx", ".txt"],
        "medical_images": [".dcm", ".nii", ".tiff"],  # DICOM, NIfTI
        "ocr_results": [".json", ".txt", ".xml"]
    },
    "file_categories": {
        "image": "Medical images and scans",
        "document": "Medical documents and reports", 
        "ocr": "OCR processing results",
        "prescription": "Prescription documents",
        "lab_result": "Laboratory results"
    }
}