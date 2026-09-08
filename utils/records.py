"""
Medical records management utilities
"""
import streamlit as st
import logging
import numpy as np
from datetime import datetime
from bson import ObjectId
import io
import base64
from utils.database import get_records_collection

logger = logging.getLogger(__name__)

def sanitize_for_mongodb(data):
    """
    Recursively sanitize data to ensure MongoDB compatibility
    Converts numpy types to Python native types
    """
    if isinstance(data, dict):
        return {key: sanitize_for_mongodb(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        return [sanitize_for_mongodb(item) for item in data]
    elif isinstance(data, np.integer):
        return int(data)
    elif isinstance(data, np.floating):
        return float(data)
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif hasattr(data, 'item'):  # numpy scalar
        return data.item()
    else:
        return data

# Conditional import for LLM utilities
try:
    from llm_integration import summarize_text, summarize_with_metadata
    LLM_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LLM utilities not available: {str(e)}")
    LLM_AVAILABLE = False

# Fallback functions (always available)
def summarize_text_fallback(text):
    # Simple fallback summarization
    sentences = text.split('.')[:3]  # Take first 3 sentences
    return '. '.join(sentences) + '.' if sentences else "Summary not available."

def generate_medical_insights(text):
    """Generate medical insights using LLM or fallback"""
    if LLM_AVAILABLE:
        try:
            return summarize_with_metadata(text)
        except Exception as e:
            logger.warning(f"LLM summarization failed, using fallback: {e}")
            return generate_medical_insights_fallback(text)
    else:
        return generate_medical_insights_fallback(text)

def generate_medical_insights_fallback(text):
    """Fallback function for medical insights when LLM is not available"""
    return {
        "summary": text[:200] + "..." if len(text) > 200 else text,
        "key_information": {"symptoms": [], "medications": [], "conditions": [], "procedures": []},
        "statistics": {"word_count": len(text.split()), "character_count": len(text), "estimated_reading_time": 1},
        "generated_at": str(datetime.utcnow())
    }

def save_medical_record(record_data_or_patient_id, original_text=None, file_name=None, file_type=None):
    """
    Save a medical record to the database
    Args:
        record_data_or_patient_id: Dictionary containing record information OR patient_id for backward compatibility
        original_text: Original medical record text (for backward compatibility)
        file_name: Name of uploaded file (for backward compatibility)
        file_type: Type of uploaded file (for backward compatibility)
    Returns:
        str: Record ID if successful, None otherwise
    """
    try:
        records_collection = get_records_collection()
        
        # Handle both old and new calling patterns
        if isinstance(record_data_or_patient_id, dict):
            # New format - complete record data
            record_data = record_data_or_patient_id
            patient_id = record_data['patient_id']
            
            # Essential fields only
            content = record_data.get('content', record_data.get('original_text', ''))
            title = record_data.get('title', 'Medical Record')
            record_type = record_data.get('record_type', 'General Consultation')
            record_date = record_data.get('record_date')
            priority = record_data.get('priority', 'Normal')
            additional_notes = record_data.get('additional_notes', '')
            
            # File information (if available)
            file_info = record_data.get('file_info')
            
            # OCR information (if available)
            ocr_info = record_data.get('ocr_info')
            
        else:
            # Old format - for backward compatibility
            patient_id = record_data_or_patient_id
            content = original_text or ''
            title = 'Medical Record'
            record_type = 'General Consultation'
            record_date = datetime.now().isoformat()
            priority = 'Normal'
            additional_notes = ''
            file_info = None
            ocr_info = None
        
        # Create clean record document with only essential fields
        record_doc = {
            # Core medical record fields
            "patient_id": patient_id,
            "title": title,
            "content": content,
            "record_type": record_type,
            "record_date": record_date,
            "priority": priority,
            "additional_notes": additional_notes,
            
            # Timestamps
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            
            # Optional file information
            "file_info": file_info,
            
            # Optional OCR information
            "ocr_info": ocr_info
        }
        
        # Remove None values to keep database clean
        record_doc = {k: v for k, v in record_doc.items() if v is not None}
        
        # Sanitize all data for MongoDB compatibility
        record_doc = sanitize_for_mongodb(record_doc)
        
        # Insert record
        result = records_collection.insert_one(record_doc)
        
        if result.inserted_id:
            logger.info(f"Medical record saved for patient {patient_id}")
            return str(result.inserted_id)
        else:
            return None
            
    except Exception as e:
        logger.error(f"Failed to save medical record: {str(e)}")
        if hasattr(st, 'error'):
            st.error(f"Failed to save record: {str(e)}")
        return None

def get_patient_records(patient_id, limit=None):
    """
    Get all medical records for a patient
    Args:
        patient_id: ID of the patient
        limit: Maximum number of records to return
    Returns:
        list: List of medical records
    """
    try:
        records_collection = get_records_collection()
        
        query = {"patient_id": patient_id}
        cursor = records_collection.find(query).sort("uploaded_at", -1)
        
        if limit:
            cursor = cursor.limit(limit)
        
        records = list(cursor)
        logger.info(f"Retrieved {len(records)} records for patient {patient_id}")
        return records
        
    except Exception as e:
        logger.error(f"Failed to get patient records: {str(e)}")
        return []

def get_record_by_id(record_id):
    """
    Get a specific medical record by ID
    Args:
        record_id: ID of the record
    Returns:
        dict: Medical record or None
    """
    try:
        records_collection = get_records_collection()
        record = records_collection.find_one({"_id": ObjectId(record_id)})
        return record
        
    except Exception as e:
        logger.error(f"Failed to get record: {str(e)}")
        return None

def update_doctor_notes(record_id, doctor_notes, doctor_id):
    """
    Update doctor's notes for a medical record
    Args:
        record_id: ID of the record
        doctor_notes: Doctor's notes
        doctor_id: ID of the doctor
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        records_collection = get_records_collection()
        
        update_data = {
            "doctor_notes": doctor_notes,
            "last_updated_by": doctor_id,
            "updated_at": datetime.utcnow()
        }
        
        result = records_collection.update_one(
            {"_id": ObjectId(record_id)},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        logger.error(f"Failed to update doctor notes: {str(e)}")
        return False

def delete_record(record_id, user_id):
    """
    Delete a medical record
    Args:
        record_id: ID of the record to delete
        user_id: ID of the user requesting deletion
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        records_collection = get_records_collection()
        
        # First check if record exists and user has permission
        record = records_collection.find_one({"_id": ObjectId(record_id)})
        
        if not record:
            return False
        
        # Check if user is the patient or has admin role
        if record["patient_id"] != user_id and not st.session_state.get("user_role") == "admin":
            return False
        
        result = records_collection.delete_one({"_id": ObjectId(record_id)})
        return result.deleted_count > 0
        
    except Exception as e:
        logger.error(f"Failed to delete record: {str(e)}")
        return False

def search_records(query, patient_id=None, doctor_id=None):
    """
    Search medical records
    Args:
        query: Search query
        patient_id: Filter by patient ID (optional)
        doctor_id: Filter by doctor ID (optional)
    Returns:
        list: List of matching records
    """
    try:
        records_collection = get_records_collection()
        
        # Build search criteria
        search_criteria = {
            "$or": [
                {"original_text": {"$regex": query, "$options": "i"}},
                {"summary": {"$regex": query, "$options": "i"}},
                {"doctor_notes": {"$regex": query, "$options": "i"}}
            ]
        }
        
        # Add filters
        if patient_id:
            search_criteria["patient_id"] = patient_id
        
        records = list(records_collection.find(search_criteria).sort("uploaded_at", -1))
        return records
        
    except Exception as e:
        logger.error(f"Failed to search records: {str(e)}")
        return []

def get_records_stats(patient_id=None):
    """
    Get statistics about medical records
    Args:
        patient_id: Filter by patient ID (optional)
    Returns:
        dict: Statistics
    """
    try:
        records_collection = get_records_collection()
        
        match_stage = {}
        if patient_id:
            match_stage = {"patient_id": patient_id}
        
        pipeline = []
        
        if match_stage:
            pipeline.append({"$match": match_stage})
        
        pipeline.extend([
            {
                "$group": {
                    "_id": None,
                    "total_records": {"$sum": 1},
                    "avg_text_length": {"$avg": {"$strLenCP": "$original_text"}},
                    "latest_record": {"$max": "$uploaded_at"},
                    "earliest_record": {"$min": "$uploaded_at"}
                }
            }
        ])
        
        result = list(records_collection.aggregate(pipeline))
        
        if result:
            stats = result[0]
            stats.pop("_id", None)
            return stats
        else:
            return {
                "total_records": 0,
                "avg_text_length": 0,
                "latest_record": None,
                "earliest_record": None
            }
            
    except Exception as e:
        logger.error(f"Failed to get records stats: {str(e)}")
        return {}

def export_patient_records(patient_id, format="json"):
    """
    Export patient records in specified format
    Args:
        patient_id: ID of the patient
        format: Export format (json, csv, txt)
    Returns:
        str: Exported data
    """
    try:
        records = get_patient_records(patient_id)
        
        if format == "json":
            import json
            # Convert ObjectId to string for JSON serialization
            for record in records:
                record["_id"] = str(record["_id"])
                if "uploaded_at" in record:
                    record["uploaded_at"] = record["uploaded_at"].isoformat()
                if "created_at" in record:
                    record["created_at"] = record["created_at"].isoformat()
                if "updated_at" in record:
                    record["updated_at"] = record["updated_at"].isoformat()
            
            return json.dumps(records, indent=2)
        
        elif format == "csv":
            import pandas as pd
            if records:
                df = pd.DataFrame(records)
                return df.to_csv(index=False)
            else:
                return "No records found"
        
        elif format == "txt":
            text_export = f"Medical Records Export for Patient: {patient_id}\n"
            text_export += "=" * 50 + "\n\n"
            
            for i, record in enumerate(records, 1):
                text_export += f"Record {i}:\n"
                text_export += f"Date: {record.get('uploaded_at', 'N/A')}\n"
                text_export += f"Original Text:\n{record.get('original_text', 'N/A')}\n\n"
                text_export += f"AI Summary:\n{record.get('summary', 'N/A')}\n\n"
                if record.get('doctor_notes'):
                    text_export += f"Doctor's Notes:\n{record['doctor_notes']}\n\n"
                text_export += "-" * 30 + "\n\n"
            
            return text_export
        
        else:
            return "Unsupported format"
            
    except Exception as e:
        logger.error(f"Failed to export records: {str(e)}")
        return f"Export failed: {str(e)}"