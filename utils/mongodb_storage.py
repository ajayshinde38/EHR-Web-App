"""
MongoDB GridFS File Storage Manager for EHR Application
Stores images, PDFs, documents in MongoDB instead of local filesystem
"""

import os
import hashlib
import io
import mimetypes
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import base64
from PIL import Image
import gridfs
from pymongo import MongoClient
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBFileStorage:
    """
    MongoDB GridFS-based file storage system for EHR application
    Stores all medical documents in MongoDB database
    """
    
    def __init__(self, connection_string: str = None, database_name: str = None):
        self.connection_string = connection_string or "mongodb://localhost:27017/"
        self.database_name = database_name or "ehr_app"
        self.client = None
        self.db = None
        self.fs = None
        self.metadata_collection = None
        self._connect()
    
    def _connect(self):
        """Establish MongoDB connection and initialize GridFS"""
        try:
            self.client = MongoClient(self.connection_string)
            self.db = self.client[self.database_name]
            
            # Initialize GridFS with custom bucket name
            self.fs = gridfs.GridFS(self.db, collection="medical_files")
            
            # Collection for file metadata and indexing
            self.metadata_collection = self.db.file_metadata
            
            # Create indexes for better performance
            self.metadata_collection.create_index("patient_id")
            self.metadata_collection.create_index("file_type") 
            self.metadata_collection.create_index("created_at")
            self.metadata_collection.create_index("file_hash")
            
            logger.info("MongoDB file storage initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    def store_patient_file(self, file_data: bytes, filename: str, 
                          patient_id: str, file_type: str, 
                          metadata: Dict = None) -> Dict:
        """
        Store a file for a specific patient in MongoDB GridFS
        
        Args:
            file_data: Raw file bytes
            filename: Original filename
            patient_id: Patient identifier
            file_type: Type of file (image, pdf, document, ocr)
            metadata: Additional file metadata
        
        Returns:
            Dictionary with storage information
        """
        try:
            # Calculate file hash for integrity and deduplication
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Check if file already exists (deduplication)
            existing_file = self.metadata_collection.find_one({
                "file_hash": file_hash,
                "patient_id": patient_id
            })
            
            if existing_file:
                logger.info(f"File already exists: {filename}")
                return {
                    "success": True,
                    "file_id": str(existing_file["file_id"]),
                    "message": "File already exists",
                    "metadata": existing_file
                }
            
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_filename = f"{timestamp}_{filename}"
            
            # Prepare GridFS metadata
            gridfs_metadata = {
                "patient_id": patient_id,
                "file_type": file_type,
                "original_filename": filename,
                "unique_filename": unique_filename,
                "upload_date": datetime.now(),
                "file_size": len(file_data),
                "file_hash": file_hash,
                "mime_type": mimetypes.guess_type(filename)[0],
                "metadata": metadata or {}
            }
            
            # Store file in GridFS
            file_id = self.fs.put(
                file_data, 
                filename=unique_filename,
                **gridfs_metadata
            )
            
            # Store metadata in separate collection for efficient querying
            file_metadata = {
                "file_id": file_id,
                "patient_id": patient_id,
                "file_type": file_type,
                "original_filename": filename,
                "unique_filename": unique_filename,
                "file_size": len(file_data),
                "file_hash": file_hash,
                "mime_type": mimetypes.guess_type(filename)[0],
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "is_active": True,
                "download_count": 0,
                "metadata": metadata or {}
            }
            
            # Insert metadata
            metadata_result = self.metadata_collection.insert_one(file_metadata)
            
            # Create thumbnail for images
            thumbnail_id = None
            if file_type == "image":
                thumbnail_id = self._create_thumbnail(file_data, patient_id, unique_filename, file_id)
            
            logger.info(f"Stored file in MongoDB: {filename} for patient {patient_id}")
            
            return {
                "success": True,
                "file_id": str(file_id),
                "metadata_id": str(metadata_result.inserted_id),
                "thumbnail_id": str(thumbnail_id) if thumbnail_id else None,
                "metadata": file_metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to store file {filename}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_thumbnail(self, image_data: bytes, patient_id: str, 
                         filename: str, original_file_id: ObjectId) -> Optional[ObjectId]:
        """Create thumbnail for image files and store in GridFS"""
        try:
            # Create thumbnail
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((200, 200), Image.Resampling.LANCZOS)
            
            # Convert thumbnail to bytes
            thumb_buffer = io.BytesIO()
            image.save(thumb_buffer, "JPEG", quality=85)
            thumb_data = thumb_buffer.getvalue()
            
            # Store thumbnail in GridFS
            thumb_filename = f"thumb_{filename}"
            thumbnail_id = self.fs.put(
                thumb_data,
                filename=thumb_filename,
                patient_id=patient_id,
                file_type="thumbnail",
                original_file_id=original_file_id,
                upload_date=datetime.now(),
                file_size=len(thumb_data),
                mime_type="image/jpeg"
            )
            
            logger.info(f"Created thumbnail: {thumb_filename}")
            return thumbnail_id
            
        except Exception as e:
            logger.warning(f"Failed to create thumbnail: {e}")
            return None
    
    def get_patient_files(self, patient_id: str, file_type: str = None) -> List[Dict]:
        """
        Retrieve all files for a patient from MongoDB
        
        Args:
            patient_id: Patient identifier
            file_type: Optional filter by file type
        
        Returns:
            List of file information dictionaries
        """
        try:
            # Build query
            query = {
                "patient_id": patient_id,
                "is_active": True
            }
            
            if file_type:
                query["file_type"] = file_type
            
            # Retrieve metadata
            files = list(self.metadata_collection.find(query).sort("created_at", -1))
            
            # Convert ObjectId to string for JSON serialization
            for file_info in files:
                file_info["_id"] = str(file_info["_id"])
                file_info["file_id"] = str(file_info["file_id"])
                if isinstance(file_info.get("created_at"), datetime):
                    file_info["created_at"] = file_info["created_at"].isoformat()
                if isinstance(file_info.get("updated_at"), datetime):
                    file_info["updated_at"] = file_info["updated_at"].isoformat()
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to get patient files: {e}")
            return []
    
    def get_file_content(self, file_id: str) -> Optional[bytes]:
        """Retrieve file content by GridFS file ID"""
        try:
            # Convert string to ObjectId
            object_id = ObjectId(file_id)
            
            # Retrieve file from GridFS
            grid_out = self.fs.get(object_id)
            content = grid_out.read()
            
            # Update download count
            self.metadata_collection.update_one(
                {"file_id": object_id},
                {"$inc": {"download_count": 1}, "$set": {"last_accessed": datetime.now()}}
            )
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to read file {file_id}: {e}")
            return None
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by file ID"""
        try:
            object_id = ObjectId(file_id)
            metadata = self.metadata_collection.find_one({"file_id": object_id})
            
            if metadata:
                metadata["_id"] = str(metadata["_id"])
                metadata["file_id"] = str(metadata["file_id"])
                if isinstance(metadata.get("created_at"), datetime):
                    metadata["created_at"] = metadata["created_at"].isoformat()
                if isinstance(metadata.get("updated_at"), datetime):
                    metadata["updated_at"] = metadata["updated_at"].isoformat()
            
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to get file metadata {file_id}: {e}")
            return None
    
    def delete_file(self, file_id: str, patient_id: str) -> bool:
        """
        Safely delete a file from MongoDB GridFS
        
        Args:
            file_id: GridFS file ID
            patient_id: Patient identifier for security
        
        Returns:
            True if deleted successfully
        """
        try:
            object_id = ObjectId(file_id)
            
            # Verify the file belongs to the patient (security check)
            metadata = self.metadata_collection.find_one({
                "file_id": object_id,
                "patient_id": patient_id
            })
            
            if not metadata:
                logger.warning(f"File {file_id} not found or doesn't belong to patient {patient_id}")
                return False
            
            # Soft delete - mark as inactive instead of permanent deletion
            self.metadata_collection.update_one(
                {"file_id": object_id},
                {
                    "$set": {
                        "is_active": False,
                        "deleted_at": datetime.now()
                    }
                }
            )
            
            # Optional: Actually delete from GridFS (uncomment for hard delete)
            # self.fs.delete(object_id)
            
            logger.info(f"Deleted file: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict:
        """Get storage usage statistics from MongoDB"""
        try:
            # Count active files
            total_files = self.metadata_collection.count_documents({"is_active": True})
            
            # Calculate total size
            pipeline = [
                {"$match": {"is_active": True}},
                {"$group": {
                    "_id": None,
                    "total_size": {"$sum": "$file_size"},
                    "avg_size": {"$avg": "$file_size"}
                }}
            ]
            
            size_stats = list(self.metadata_collection.aggregate(pipeline))
            total_size = size_stats[0]["total_size"] if size_stats else 0
            avg_size = size_stats[0]["avg_size"] if size_stats else 0
            
            # Count by file type
            type_pipeline = [
                {"$match": {"is_active": True}},
                {"$group": {
                    "_id": "$file_type",
                    "count": {"$sum": 1},
                    "size": {"$sum": "$file_size"}
                }}
            ]
            
            by_type = {}
            for type_stat in self.metadata_collection.aggregate(type_pipeline):
                by_type[type_stat["_id"]] = {
                    "count": type_stat["count"],
                    "size": type_stat["size"]
                }
            
            # Count by patient
            patient_pipeline = [
                {"$match": {"is_active": True}},
                {"$group": {
                    "_id": "$patient_id",
                    "count": {"$sum": 1},
                    "size": {"$sum": "$file_size"}
                }}
            ]
            
            by_patient = {}
            for patient_stat in self.metadata_collection.aggregate(patient_pipeline):
                by_patient[patient_stat["_id"]] = {
                    "count": patient_stat["count"],
                    "size": patient_stat["size"]
                }
            
            return {
                "total_files": total_files,
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "average_file_size": round(avg_size, 2),
                "storage_type": "MongoDB GridFS",
                "database_name": self.database_name,
                "by_type": by_type,
                "by_patient": by_patient
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}
    
    def search_files(self, query: str, patient_id: str = None) -> List[Dict]:
        """Search files by filename or metadata"""
        try:
            # Build search query
            search_query = {
                "is_active": True,
                "$or": [
                    {"original_filename": {"$regex": query, "$options": "i"}},
                    {"unique_filename": {"$regex": query, "$options": "i"}},
                    {"metadata.description": {"$regex": query, "$options": "i"}}
                ]
            }
            
            if patient_id:
                search_query["patient_id"] = patient_id
            
            files = list(self.metadata_collection.find(search_query).sort("created_at", -1))
            
            # Convert ObjectId to string
            for file_info in files:
                file_info["_id"] = str(file_info["_id"])
                file_info["file_id"] = str(file_info["file_id"])
                if isinstance(file_info.get("created_at"), datetime):
                    file_info["created_at"] = file_info["created_at"].isoformat()
            
            return files
            
        except Exception as e:
            logger.error(f"File search failed: {e}")
            return []
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

# Utility functions for integration
def init_mongodb_storage() -> MongoDBFileStorage:
    """Initialize MongoDB file storage system"""
    try:
        from config.settings import MONGODB_CONFIG
        
        return MongoDBFileStorage(
            connection_string=MONGODB_CONFIG["connection_string"],
            database_name=MONGODB_CONFIG["database_name"]
        )
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB storage: {e}")
        # Fallback to default values
        return MongoDBFileStorage()

def store_uploaded_file_mongodb(uploaded_file, patient_id: str, file_type: str = "document") -> Dict:
    """Store a Streamlit uploaded file in MongoDB"""
    storage = init_mongodb_storage()
    
    try:
        # Read file content
        uploaded_file.seek(0)  # Reset file pointer
        file_content = uploaded_file.read()
        
        # Create metadata
        metadata = {
            "upload_source": "streamlit_web_interface",
            "original_size": len(file_content),
            "upload_timestamp": datetime.now().isoformat()
        }
        
        result = storage.store_patient_file(
            file_content, 
            uploaded_file.name, 
            patient_id, 
            file_type, 
            metadata
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to store uploaded file: {e}")
        return {"success": False, "error": str(e)}
    finally:
        storage.close_connection()

def store_ocr_result_mongodb(ocr_data: Dict, patient_id: str, original_file_id: str = None) -> Dict:
    """Store OCR processing results in MongoDB"""
    storage = init_mongodb_storage()
    
    try:
        # Create OCR result file
        import json
        ocr_json = json.dumps(ocr_data, indent=2)
        ocr_bytes = ocr_json.encode('utf-8')
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ocr_result_{timestamp}.json"
        
        # Metadata
        metadata = {
            "ocr_confidence": ocr_data.get("confidence", 0),
            "ocr_engine": ocr_data.get("engine", "unknown"),
            "original_file_id": original_file_id,
            "extracted_text_length": len(ocr_data.get("text", "")),
            "processing_timestamp": datetime.now().isoformat()
        }
        
        result = storage.store_patient_file(
            ocr_bytes,
            filename,
            patient_id,
            "ocr",
            metadata
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to store OCR result: {e}")
        return {"success": False, "error": str(e)}
    finally:
        storage.close_connection()