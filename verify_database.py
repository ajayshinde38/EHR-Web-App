"""
Database verification script to check cleaned data structure
"""

import logging
from utils.database import init_db, get_records_collection
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_cleaned_data():
    """Verify the cleaned database structure"""
    try:
        collection = get_records_collection()
        
        # Get all records
        records = list(collection.find({}))
        
        logger.info(f"Found {len(records)} medical records in database")
        
        if records:
            logger.info("\nSample record structure:")
            sample_record = records[0]
            
            # Show the clean structure
            for field, value in sample_record.items():
                if field == '_id':
                    continue
                logger.info(f"  {field}: {type(value).__name__}")
            
            logger.info("\nEssential fields present in all records:")
            
            # Check essential fields
            essential_fields = ['patient_id', 'title', 'content', 'record_type', 'created_at']
            
            for field in essential_fields:
                count = sum(1 for record in records if field in record)
                logger.info(f"  {field}: {count}/{len(records)} records")
            
            # Check for removed fields
            logger.info("\nRemoved unnecessary fields:")
            removed_fields = ['summary', 'ai_summary', 'insights', 'original_text', 'timestamp', 'uploaded_at']
            
            for field in removed_fields:
                count = sum(1 for record in records if field in record)
                if count == 0:
                    logger.info(f"  ✅ {field}: Successfully removed")
                else:
                    logger.info(f"  ❌ {field}: Still present in {count} records")
            
            # Show file storage info
            db = init_db()
            file_count = db.medical_files.files.count_documents({})
            metadata_count = db.file_metadata.count_documents({})
            
            logger.info(f"\nFile storage:")
            logger.info(f"  GridFS files: {file_count}")
            logger.info(f"  File metadata records: {metadata_count}")
            
        else:
            logger.info("No records found in database")
            
    except Exception as e:
        logger.error(f"Error verifying data: {e}")

if __name__ == "__main__":
    logger.info("=== Database Verification ===")
    verify_cleaned_data()
    logger.info("=== Verification Complete ===")