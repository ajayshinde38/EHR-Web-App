"""
File Storage Manager for EHR Application
Handles images, PDFs, documents, and OCR files with proper organization
"""

import os
import hashlib
import shutil
from datetime import datetime
from pathlib import Path
import mimetypes
import logging
from typing import Dict, List, Optional, Tuple
import base64
import io
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EHRFileStorage:
    """
    Comprehensive file storage system for EHR application
    Handles all types of medical documents with proper organization
    """
    
    def __init__(self, base_storage_path: str = "ehr_storage"):
        self.base_path = Path(base_storage_path)
        self.setup_storage_structure()
    
    def setup_storage_structure(self):
        """Create organized storage directory structure"""
        
        # Main storage directories
        directories = [
            "documents/pdf",           # PDF medical reports, forms
            "documents/word",          # DOC/DOCX files
            "documents/text",          # Plain text files
            "images/original",         # Original uploaded images
            "images/processed",        # Processed/enhanced images
            "images/thumbnails",       # Small preview images
            "ocr/extracted",          # OCR extracted text files
            "ocr/confidence",         # OCR confidence data
            "backups/daily",          # Daily backups
            "backups/weekly",         # Weekly backups
            "temp/uploads",           # Temporary upload processing
            "temp/processing",        # Temporary processing files
            "patient_data",           # Patient-specific folders
            "metadata",               # File metadata storage
            "logs"                    # Storage operation logs
        ]
        
        for directory in directories:
            dir_path = self.base_path / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created storage directory: {dir_path}")
        
        # Create index file
        self._create_storage_index()
    
    def _create_storage_index(self):
        """Create storage index and configuration"""
        index_data = {
            "created": datetime.now().isoformat(),
            "version": "1.0.0",
            "total_files": 0,
            "storage_structure": {
                "documents": "Medical documents (PDF, DOC, TXT)",
                "images": "Medical images and scans",
                "ocr": "OCR processing results",
                "patient_data": "Patient-specific file organization",
                "backups": "System backups",
                "metadata": "File metadata and indexing"
            },
            "supported_formats": {
                "images": [".jpg", ".jpeg", ".png", ".tiff", ".bmp"],
                "documents": [".pdf", ".doc", ".docx", ".txt"],
                "ocr": [".json", ".txt", ".xml"]
            }
        }
        
        index_file = self.base_path / "storage_index.json"
        import json
        with open(index_file, 'w') as f:
            json.dump(index_data, f, indent=2)
    
    def store_patient_file(self, file_data: bytes, filename: str, 
                          patient_id: str, file_type: str, 
                          metadata: Dict = None) -> Dict:
        """
        Store a file for a specific patient with proper organization
        
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
            # Create patient-specific directory
            patient_dir = self.base_path / "patient_data" / patient_id
            patient_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = Path(filename).suffix.lower()
            unique_filename = f"{timestamp}_{filename}"
            
            # Determine storage subdirectory based on file type
            if file_type == "image":
                storage_dir = patient_dir / "images"
            elif file_type == "pdf":
                storage_dir = patient_dir / "documents" / "pdf"
            elif file_type == "document":
                storage_dir = patient_dir / "documents" / "other"
            elif file_type == "ocr":
                storage_dir = patient_dir / "ocr_results"
            else:
                storage_dir = patient_dir / "misc"
            
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Store the file
            file_path = storage_dir / unique_filename
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # Calculate file hash for integrity
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            # Create metadata
            file_metadata = {
                "original_filename": filename,
                "stored_filename": unique_filename,
                "patient_id": patient_id,
                "file_type": file_type,
                "file_size": len(file_data),
                "file_hash": file_hash,
                "storage_path": str(file_path.relative_to(self.base_path)),
                "mime_type": mimetypes.guess_type(filename)[0],
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # Store metadata
            metadata_file = storage_dir / f"{unique_filename}.metadata.json"
            import json
            with open(metadata_file, 'w') as f:
                json.dump(file_metadata, f, indent=2)
            
            # Create thumbnail for images
            if file_type == "image":
                self._create_thumbnail(file_data, patient_id, unique_filename)
            
            logger.info(f"Stored file: {filename} for patient {patient_id}")
            
            return {
                "success": True,
                "file_path": str(file_path),
                "file_id": file_hash[:16],  # Use first 16 chars of hash as ID
                "metadata": file_metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to store file {filename}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _create_thumbnail(self, image_data: bytes, patient_id: str, filename: str):
        """Create thumbnail for image files"""
        try:
            # Create thumbnail directory
            thumb_dir = self.base_path / "patient_data" / patient_id / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)
            
            # Create thumbnail
            image = Image.open(io.BytesIO(image_data))
            image.thumbnail((200, 200), Image.Resampling.LANCZOS)
            
            # Save thumbnail
            thumb_filename = f"thumb_{filename}"
            thumb_path = thumb_dir / thumb_filename
            image.save(thumb_path, "JPEG", quality=85)
            
            logger.info(f"Created thumbnail: {thumb_filename}")
            
        except Exception as e:
            logger.warning(f"Failed to create thumbnail: {e}")
    
    def get_patient_files(self, patient_id: str, file_type: str = None) -> List[Dict]:
        """
        Retrieve all files for a patient
        
        Args:
            patient_id: Patient identifier
            file_type: Optional filter by file type
        
        Returns:
            List of file information dictionaries
        """
        try:
            patient_dir = self.base_path / "patient_data" / patient_id
            if not patient_dir.exists():
                return []
            
            files = []
            
            # Search for metadata files
            for metadata_file in patient_dir.rglob("*.metadata.json"):
                try:
                    import json
                    with open(metadata_file, 'r') as f:
                        file_info = json.load(f)
                    
                    # Filter by file type if specified
                    if file_type and file_info.get("file_type") != file_type:
                        continue
                    
                    # Add full path information
                    file_info["full_path"] = str(self.base_path / file_info["storage_path"])
                    file_info["relative_path"] = file_info["storage_path"]
                    
                    files.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to read metadata {metadata_file}: {e}")
            
            # Sort by creation date (newest first)
            files.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to get patient files: {e}")
            return []
    
    def get_file_content(self, file_path: str) -> Optional[bytes]:
        """Retrieve file content by path"""
        try:
            full_path = self.base_path / file_path
            if full_path.exists():
                with open(full_path, 'rb') as f:
                    return f.read()
            return None
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None
    
    def delete_file(self, file_path: str, patient_id: str) -> bool:
        """
        Safely delete a file and its metadata
        
        Args:
            file_path: Relative path to the file
            patient_id: Patient identifier for security
        
        Returns:
            True if deleted successfully
        """
        try:
            # Verify the file belongs to the patient
            if not file_path.startswith(f"patient_data/{patient_id}/"):
                logger.warning(f"Attempted to delete file outside patient directory: {file_path}")
                return False
            
            full_path = self.base_path / file_path
            metadata_path = full_path.with_suffix(f"{full_path.suffix}.metadata.json")
            
            # Delete file and metadata
            if full_path.exists():
                full_path.unlink()
            if metadata_path.exists():
                metadata_path.unlink()
            
            logger.info(f"Deleted file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict:
        """Get storage usage statistics"""
        try:
            stats = {
                "total_files": 0,
                "total_size": 0,
                "by_type": {},
                "by_patient": {},
                "storage_path": str(self.base_path.absolute())
            }
            
            # Count files and calculate sizes
            for metadata_file in self.base_path.rglob("*.metadata.json"):
                try:
                    import json
                    with open(metadata_file, 'r') as f:
                        file_info = json.load(f)
                    
                    stats["total_files"] += 1
                    file_size = file_info.get("file_size", 0)
                    stats["total_size"] += file_size
                    
                    # Count by type
                    file_type = file_info.get("file_type", "unknown")
                    if file_type not in stats["by_type"]:
                        stats["by_type"][file_type] = {"count": 0, "size": 0}
                    stats["by_type"][file_type]["count"] += 1
                    stats["by_type"][file_type]["size"] += file_size
                    
                    # Count by patient
                    patient_id = file_info.get("patient_id", "unknown")
                    if patient_id not in stats["by_patient"]:
                        stats["by_patient"][patient_id] = {"count": 0, "size": 0}
                    stats["by_patient"][patient_id]["count"] += 1
                    stats["by_patient"][patient_id]["size"] += file_size
                    
                except Exception as e:
                    logger.warning(f"Failed to process metadata {metadata_file}: {e}")
            
            # Convert sizes to human readable
            stats["total_size_mb"] = round(stats["total_size"] / (1024 * 1024), 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}

# Utility functions for integration
def init_ehr_storage(storage_path: str = None) -> EHRFileStorage:
    """Initialize EHR file storage system"""
    if storage_path is None:
        # Use directory relative to application
        storage_path = os.path.join(os.getcwd(), "ehr_storage")
    
    return EHRFileStorage(storage_path)

def store_uploaded_file(uploaded_file, patient_id: str, file_type: str = "document") -> Dict:
    """Store a Streamlit uploaded file"""
    storage = init_ehr_storage()
    
    # Read file content
    file_content = uploaded_file.read()
    
    # Create metadata
    metadata = {
        "upload_source": "streamlit",
        "original_size": len(file_content)
    }
    
    return storage.store_patient_file(
        file_content, 
        uploaded_file.name, 
        patient_id, 
        file_type, 
        metadata
    )

def store_ocr_result(ocr_data: Dict, patient_id: str, original_image_path: str = None) -> Dict:
    """Store OCR processing results"""
    storage = init_ehr_storage()
    
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
        "original_image": original_image_path,
        "extracted_text_length": len(ocr_data.get("text", ""))
    }
    
    return storage.store_patient_file(
        ocr_bytes,
        filename,
        patient_id,
        "ocr",
        metadata
    )