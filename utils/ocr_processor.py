"""
OCR (Optical Character Recognition) Module for EHR Application
Handles extraction of text from medical documents, handwritten notes, and prescriptions
"""

import os
import io
import cv2
import numpy as np
import logging
import warnings
import pandas as pd
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter
from typing import Dict, List, Tuple, Optional, Union
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global OCR processor instance (singleton pattern)
_ocr_processor_instance = None

class OCRProcessor:
    """
    Advanced OCR processor for medical documents with support for:
    - Handwritten text recognition
    - Printed text extraction
    - Image preprocessing and enhancement
    - Multiple OCR engines (Tesseract, EasyOCR)
    """
    
    def __init__(self, suppress_warnings: bool = True):
        self.tesseract_available = False
        self.easyocr_available = False
        self.suppress_warnings = suppress_warnings
        self._initialize_ocr_engines()
    
    def _initialize_ocr_engines(self):
        """Initialize available OCR engines with optional warning suppression"""
        
        # Suppress warnings if requested
        if self.suppress_warnings:
            # Suppress specific EasyOCR warnings
            warnings.filterwarnings('ignore', category=UserWarning, module='easyocr')
            
            # Set environment variable to suppress EasyOCR GPU warnings
            os.environ['EASYOCR_QUIET'] = '1'
            
            # Temporarily set log level to ERROR to suppress INFO/WARNING messages
            old_level = logger.level
            logger.setLevel(logging.ERROR)
            
            # Also suppress easyocr logger
            easyocr_logger = logging.getLogger('easyocr.easyocr')
            old_easyocr_level = easyocr_logger.level
            easyocr_logger.setLevel(logging.ERROR)
        
        try:
            import pytesseract
            # Try to get tesseract version to verify it's working
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
            if not self.suppress_warnings:
                logger.info("Tesseract OCR engine initialized successfully")
        except Exception as e:
            if not self.suppress_warnings:
                logger.warning(f"Tesseract not available: {e}")
                logger.warning("Please install Tesseract: https://github.com/UB-Mannheim/tesseract/wiki")
        
        try:
            # Suppress stdout during EasyOCR initialization if warnings are suppressed
            if self.suppress_warnings:
                import sys
                from contextlib import redirect_stderr, redirect_stdout
                with redirect_stdout(open(os.devnull, 'w')), redirect_stderr(open(os.devnull, 'w')):
                    import easyocr
                    self.easyocr_reader = easyocr.Reader(['en'])
            else:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['en'])
            
            self.easyocr_available = True
            if not self.suppress_warnings:
                logger.info("EasyOCR engine initialized successfully")
        except Exception as e:
            if not self.suppress_warnings:
                logger.warning(f"EasyOCR not available: {e}")
        
        # Restore log levels if warnings were suppressed
        if self.suppress_warnings:
            logger.setLevel(old_level)
            easyocr_logger.setLevel(old_easyocr_level)
    
    def preprocess_image(self, image: Union[np.ndarray, Image.Image], 
                        enhancement_type: str = "auto") -> np.ndarray:
        """
        Preprocess image for better OCR results
        
        Args:
            image: Input image (PIL Image or numpy array)
            enhancement_type: Type of enhancement ("handwritten", "printed", "auto")
        
        Returns:
            Preprocessed image as numpy array
        """
        # Convert PIL Image to numpy array if needed
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # Convert to grayscale if colored
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        if enhancement_type == "handwritten":
            return self._preprocess_handwritten(gray)
        elif enhancement_type == "printed":
            return self._preprocess_printed(gray)
        else:  # auto
            return self._preprocess_auto(gray)
    
    def _preprocess_handwritten(self, gray: np.ndarray) -> np.ndarray:
        """Preprocessing optimized for handwritten text"""
        # Noise reduction
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Adaptive thresholding for handwritten text
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((1,1), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def _preprocess_printed(self, gray: np.ndarray) -> np.ndarray:
        """Preprocessing optimized for printed text"""
        # Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (1, 1), 0)
        
        # Otsu's thresholding
        _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _preprocess_auto(self, gray: np.ndarray) -> np.ndarray:
        """Automatic preprocessing based on image characteristics"""
        # Calculate image statistics to determine best approach
        mean_intensity = np.mean(gray)
        std_intensity = np.std(gray)
        
        if std_intensity > 50 and mean_intensity < 150:
            # Likely handwritten or poor quality
            return self._preprocess_handwritten(gray)
        else:
            # Likely printed text
            return self._preprocess_printed(gray)
    
    def extract_text_tesseract(self, image: np.ndarray, 
                              config: str = "--psm 6") -> Dict[str, any]:
        """
        Extract text using Tesseract OCR
        
        Args:
            image: Preprocessed image
            config: Tesseract configuration string
        
        Returns:
            Dictionary with extracted text and confidence scores
        """
        if not self.tesseract_available:
            return {"text": "", "confidence": 0, "error": "Tesseract not available"}
        
        try:
            import pytesseract
            
            # Extract text with confidence
            data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            # Filter out low confidence results and convert to Python native types
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            texts = [data['text'][i] for i in range(len(data['text'])) if int(data['conf'][i]) > 30]
            
            extracted_text = ' '.join(texts).strip()
            avg_confidence = float(np.mean(confidences)) if confidences else 0.0
            
            # Convert data dictionary to MongoDB-compatible format
            converted_data = {}
            for key, values in data.items():
                if isinstance(values, list):
                    converted_data[key] = [int(val) if isinstance(val, (np.integer, int)) 
                                         else float(val) if isinstance(val, (np.floating, float))
                                         else str(val) for val in values]
                else:
                    converted_data[key] = values
            
            return {
                "text": extracted_text,
                "confidence": avg_confidence,
                "engine": "tesseract",
                "word_details": converted_data
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return {"text": "", "confidence": 0, "error": str(e)}
    
    def extract_text_easyocr(self, image: np.ndarray) -> Dict[str, any]:
        """
        Extract text using EasyOCR
        
        Args:
            image: Preprocessed image
        
        Returns:
            Dictionary with extracted text and confidence scores
        """
        if not self.easyocr_available:
            return {"text": "", "confidence": 0, "error": "EasyOCR not available"}
        
        try:
            results = self.easyocr_reader.readtext(image)
            
            extracted_text = ""
            confidences = []
            word_details = []
            
            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # Filter low confidence results
                    extracted_text += text + " "
                    confidences.append(float(confidence))
                    
                    # Convert numpy types to Python native types for MongoDB compatibility
                    converted_bbox = []
                    for point in bbox:
                        if isinstance(point, (list, tuple)):
                            converted_point = [float(coord) for coord in point]
                        else:
                            converted_point = [float(point[0]), float(point[1])]
                        converted_bbox.append(converted_point)
                    
                    word_details.append({
                        "text": str(text),
                        "confidence": float(confidence),
                        "bbox": converted_bbox
                    })
            
            avg_confidence = float(np.mean(confidences)) if confidences else 0.0
            
            return {
                "text": extracted_text.strip(),
                "confidence": avg_confidence * 100,  # Convert to percentage
                "engine": "easyocr",
                "word_details": word_details
            }
            
        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return {"text": "", "confidence": 0, "error": str(e)}
    
    def process_medical_document(self, image: Union[np.ndarray, Image.Image, str],
                               document_type: str = "auto") -> Dict[str, any]:
        """
        Process medical document with OCR
        
        Args:
            image: Image data (numpy array, PIL Image, or base64 string)
            document_type: Type of document ("prescription", "handwritten_notes", 
                          "printed_report", "auto")
        
        Returns:
            Comprehensive OCR results with medical context
        """
        try:
            # Handle different input types
            if isinstance(image, str):
                # Assume base64 encoded image
                image_data = base64.b64decode(image)
                image = Image.open(io.BytesIO(image_data))
            
            # Determine preprocessing strategy based on document type
            if document_type == "prescription":
                enhancement_type = "handwritten"
                tesseract_config = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:-()mg/ml"
            elif document_type == "handwritten_notes":
                enhancement_type = "handwritten"
                tesseract_config = "--psm 6"
            elif document_type == "printed_report":
                enhancement_type = "printed"
                tesseract_config = "--psm 6"
            else:  # auto
                enhancement_type = "auto"
                tesseract_config = "--psm 6"
            
            # Preprocess image
            processed_image = self.preprocess_image(image, enhancement_type)
            
            # Try both OCR engines and combine results
            results = {}
            
            # Tesseract OCR
            tesseract_result = self.extract_text_tesseract(processed_image, tesseract_config)
            results["tesseract"] = tesseract_result
            
            # EasyOCR
            easyocr_result = self.extract_text_easyocr(processed_image)
            results["easyocr"] = easyocr_result
            
            # Combine results for best accuracy
            best_result = self._combine_ocr_results(tesseract_result, easyocr_result)
            
            # Medical text post-processing
            medical_processed = self._post_process_medical_text(best_result["text"], document_type)
            
            # Prepare final results and sanitize for MongoDB
            final_results = {
                "extracted_text": medical_processed["text"],
                "confidence": best_result["confidence"],
                "document_type": document_type,
                "medical_entities": medical_processed["entities"],
                "engine_results": results,
                "processing_notes": medical_processed["notes"]
            }
            
            # Sanitize all data for MongoDB compatibility
            return self._sanitize_for_mongodb(final_results)
            
        except Exception as e:
            logger.error(f"Medical document processing error: {e}")
            error_result = {
                "extracted_text": "",
                "confidence": 0,
                "error": str(e),
                "document_type": document_type
            }
            return self._sanitize_for_mongodb(error_result)
    
    def _combine_ocr_results(self, tesseract_result: Dict, easyocr_result: Dict) -> Dict:
        """Combine results from multiple OCR engines for better accuracy"""
        
        # If one engine failed, use the other
        if tesseract_result.get("error") and not easyocr_result.get("error"):
            return easyocr_result
        elif easyocr_result.get("error") and not tesseract_result.get("error"):
            return tesseract_result
        elif tesseract_result.get("error") and easyocr_result.get("error"):
            return {"text": "", "confidence": 0, "error": "Both OCR engines failed"}
        
        # Compare confidence scores
        tesseract_conf = tesseract_result.get("confidence", 0)
        easyocr_conf = easyocr_result.get("confidence", 0)
        
        if tesseract_conf > easyocr_conf:
            primary_result = tesseract_result
            secondary_result = easyocr_result
        else:
            primary_result = easyocr_result
            secondary_result = tesseract_result
        
        # For medical documents, we can potentially combine words from both
        # but for now, we'll use the higher confidence result
        return {
            "text": primary_result["text"],
            "confidence": primary_result["confidence"],
            "engine": primary_result["engine"],
            "backup_text": secondary_result["text"],
            "backup_confidence": secondary_result["confidence"]
        }
    
    def _post_process_medical_text(self, text: str, document_type: str) -> Dict[str, any]:
        """Post-process extracted text for medical context"""
        
        processed_text = text
        entities = []
        notes = []
        
        # Common medical text corrections
        medical_corrections = {
            "mg": ["ing", "nig", "mq"],
            "ml": ["ini", "nil", "mi"],
            "tablet": ["tahlet", "tabiets", "tabiet"],
            "capsule": ["capsuie", "capsuies", "capsuule"],
            "twice": ["twlce", "twtce", "twice"],
            "daily": ["dally", "dailly", "dailv"],
            "morning": ["moming", "morninq", "mornlng"],
            "evening": ["eveninq", "evenlng", "evenmg"]
        }
        
        # Apply corrections
        for correct, variations in medical_corrections.items():
            for variation in variations:
                processed_text = processed_text.replace(variation, correct)
        
        # Extract medical entities (basic patterns)
        import re
        
        # Dosage patterns
        dosage_pattern = r'\d+\s*(?:mg|ml|g|mcg|units?)'
        dosages = re.findall(dosage_pattern, processed_text, re.IGNORECASE)
        if dosages:
            entities.append({"type": "dosage", "values": dosages})
        
        # Frequency patterns
        frequency_pattern = r'(?:once|twice|thrice|\d+\s*times?)\s*(?:daily|per day|a day)'
        frequencies = re.findall(frequency_pattern, processed_text, re.IGNORECASE)
        if frequencies:
            entities.append({"type": "frequency", "values": frequencies})
        
        # Time patterns
        time_pattern = r'(?:morning|evening|noon|night|bedtime|before meals|after meals)'
        times = re.findall(time_pattern, processed_text, re.IGNORECASE)
        if times:
            entities.append({"type": "timing", "values": times})
        
        return {
            "text": processed_text,
            "entities": entities,
            "notes": notes
        }
    
    def _sanitize_for_mongodb(self, data: any) -> any:
        """
        Recursively convert numpy types and other non-MongoDB types to native Python types
        
        Args:
            data: Data to sanitize
            
        Returns:
            MongoDB-compatible data
        """
        if isinstance(data, dict):
            return {key: self._sanitize_for_mongodb(value) for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return [self._sanitize_for_mongodb(item) for item in data]
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

    def get_ocr_engines_status(self) -> Dict[str, bool]:
        """Get status of available OCR engines"""
        return {
            "tesseract": self.tesseract_available,
            "easyocr": self.easyocr_available,
            "at_least_one_available": self.tesseract_available or self.easyocr_available
        }
    
    def get_engine_status_message(self) -> str:
        """Get user-friendly status message about OCR engines"""
        if self.tesseract_available and self.easyocr_available:
            return "✅ Both Tesseract and EasyOCR engines available"
        elif self.easyocr_available:
            return "✅ EasyOCR engine available (Tesseract optional)"
        elif self.tesseract_available:
            return "✅ Tesseract engine available (EasyOCR unavailable)"
        else:
            return "❌ No OCR engines available"

# Utility functions for Streamlit integration
def create_image_from_upload(uploaded_file) -> Optional[Image.Image]:
    """Create PIL Image from Streamlit uploaded file"""
    try:
        return Image.open(uploaded_file)
    except Exception as e:
        logger.error(f"Error opening uploaded image: {e}")
        return None

def save_ocr_result_to_record(ocr_result: Dict, patient_id: str, record_type: str = "ocr_document"):
    """Save OCR result to patient medical record"""
    from utils.records import save_medical_record
    
    try:
        record_data = {
            "patient_id": patient_id,
            "record_type": record_type,
            "extracted_text": ocr_result.get("extracted_text", ""),
            "confidence": ocr_result.get("confidence", 0),
            "document_type": ocr_result.get("document_type", "unknown"),
            "medical_entities": ocr_result.get("medical_entities", []),
            "processing_notes": ocr_result.get("processing_notes", []),
            "ocr_metadata": {
                "engines_used": list(ocr_result.get("engine_results", {}).keys()),
                "processing_timestamp": str(datetime.now())
            }
        }
        
        return save_medical_record(record_data)
    
    except Exception as e:
        logger.error(f"Error saving OCR result to record: {e}")
        return False

def get_ocr_processor(suppress_warnings: bool = True) -> OCRProcessor:
    """
    Get singleton OCR processor instance
    
    Args:
        suppress_warnings: Whether to suppress initialization warnings
    
    Returns:
        OCRProcessor instance
    """
    global _ocr_processor_instance
    
    if _ocr_processor_instance is None:
        _ocr_processor_instance = OCRProcessor(suppress_warnings=suppress_warnings)
    
    return _ocr_processor_instance

def reset_ocr_processor():
    """
    Reset the singleton OCR processor instance to force re-initialization
    """
    global _ocr_processor_instance
    _ocr_processor_instance = None