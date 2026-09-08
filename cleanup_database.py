"""
Database cleanup script to remove unnecessary data from MongoDB
This script will:
1. Remove redundant fields from medical records
2. Clean up duplicate data
3. Optimize the database structure
4. Keep only essential medical data
"""

import logging
from pymongo import MongoClient
from datetime import datetime
from utils.database import init_db, get_records_collection
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def cleanup_medical_records():
    """Clean up redundant fields in medical records collection"""
    try:
        collection = get_records_collection()
        
        # Fields to remove (unnecessary/redundant data)
        fields_to_remove = [
            "summary",           # Automatic summaries
            "ai_summary",        # Duplicate summary field
            "insights",          # Auto-generated insights
            "original_text",     # Duplicate of content
            "timestamp",         # Duplicate of created_at
            "uploaded_at",       # Duplicate of created_at
            "doctor_notes",      # Empty field
            "created_by_doctor", # Unused doctor fields
            "doctor_id",         # Unused doctor fields
            "is_doctor_observation"  # Unused doctor fields
        ]
        
        logger.info("Starting cleanup of medical records...")
        
        # Get all records
        records = list(collection.find({}))
        logger.info(f"Found {len(records)} records to process")
        
        cleaned_count = 0
        for record in records:
            record_id = record['_id']
            updates = {}
            fields_to_unset = {}
            
            # Check for fields to remove
            for field in fields_to_remove:
                if field in record:
                    fields_to_unset[field] = ""
            
            # Standardize date formats
            if 'created_at' in record:
                created_at = record['created_at']
                if not isinstance(created_at, str):
                    updates['created_at'] = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at)
            
            if 'updated_at' in record:
                updated_at = record['updated_at']
                if not isinstance(updated_at, str):
                    updates['updated_at'] = updated_at.isoformat() if hasattr(updated_at, 'isoformat') else str(updated_at)
            
            # Ensure essential fields exist
            if 'title' not in record:
                updates['title'] = record.get('file_name', 'Medical Record')
            
            if 'priority' not in record:
                updates['priority'] = 'Normal'
            
            # Apply updates if any
            if updates or fields_to_unset:
                update_doc = {}
                if updates:
                    update_doc['$set'] = updates
                if fields_to_unset:
                    update_doc['$unset'] = fields_to_unset
                
                collection.update_one({'_id': record_id}, update_doc)
                cleaned_count += 1
                
                logger.info(f"Cleaned record {record_id}")
        
        logger.info(f"Successfully cleaned {cleaned_count} medical records")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Error cleaning medical records: {e}")
        return 0

def cleanup_file_storage():
    """Clean up file storage metadata"""
    try:
        db = init_db()
        
        # Clean up file metadata collection
        metadata_collection = db.file_metadata
        files_collection = db.medical_files.files
        
        logger.info("Starting cleanup of file storage...")
        
        # Remove orphaned metadata (metadata without corresponding files)
        metadata_docs = list(metadata_collection.find({}))
        orphaned_count = 0
        
        for metadata in metadata_docs:
            file_id = metadata.get('file_id')
            if file_id:
                # Check if corresponding file exists
                file_exists = files_collection.find_one({'_id': file_id})
                if not file_exists:
                    # Remove orphaned metadata
                    metadata_collection.delete_one({'_id': metadata['_id']})
                    orphaned_count += 1
                    logger.info(f"Removed orphaned metadata: {metadata['_id']}")
        
        logger.info(f"Removed {orphaned_count} orphaned file metadata records")
        
        # Clean up unnecessary indexes
        try:
            # Remove old indexes if they exist
            db.medical_records.drop_index("patient_id_1_timestamp_1")
        except:
            pass  # Index might not exist
        
        # Create optimized indexes
        db.medical_records.create_index([("patient_id", 1), ("created_at", -1)])
        db.medical_records.create_index([("record_type", 1)])
        db.medical_records.create_index([("priority", 1)])
        
        logger.info("Updated database indexes")
        return orphaned_count
        
    except Exception as e:
        logger.error(f"Error cleaning file storage: {e}")
        return 0

def get_database_stats():
    """Get database statistics before and after cleanup"""
    try:
        db = init_db()
        
        stats = {
            'medical_records': db.medical_records.count_documents({}),
            'file_metadata': db.file_metadata.count_documents({}),
            'gridfs_files': db.medical_files.files.count_documents({}),
            'gridfs_chunks': db.medical_files.chunks.count_documents({})
        }
        
        # Get collection sizes
        for collection_name in ['medical_records', 'file_metadata']:
            try:
                collection_stats = db.command("collStats", collection_name)
                stats[f'{collection_name}_size'] = collection_stats.get('size', 0)
            except:
                stats[f'{collection_name}_size'] = 0
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {}

def main():
    """Main cleanup function"""
    logger.info("=== MongoDB Database Cleanup Started ===")
    
    # Get initial stats
    logger.info("Getting initial database statistics...")
    initial_stats = get_database_stats()
    logger.info(f"Initial stats: {initial_stats}")
    
    # Perform cleanup
    records_cleaned = cleanup_medical_records()
    files_cleaned = cleanup_file_storage()
    
    # Get final stats
    logger.info("Getting final database statistics...")
    final_stats = get_database_stats()
    logger.info(f"Final stats: {final_stats}")
    
    # Summary
    logger.info("=== Cleanup Summary ===")
    logger.info(f"Medical records cleaned: {records_cleaned}")
    logger.info(f"Orphaned files removed: {files_cleaned}")
    
    if initial_stats and final_stats:
        for key in initial_stats:
            if key.endswith('_size'):
                initial_size = initial_stats.get(key, 0)
                final_size = final_stats.get(key, 0)
                saved_bytes = initial_size - final_size
                if saved_bytes > 0:
                    logger.info(f"Space saved in {key}: {saved_bytes} bytes")
    
    logger.info("=== Database Cleanup Completed ===")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)