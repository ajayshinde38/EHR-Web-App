"""
Advanced Medical OCR Pipeline with Maximum Accuracy
Implements comprehensive preprocessing, extraction, and post-processing steps
"""

import os
import io
import cv2
import numpy as np
import logging
import warnings
import pandas as pd
import re
import json
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from typing import Dict, List, Tuple, Optional, Union, Any
import base64
from dataclasses import dataclass

# Advanced image processing
from skimage import filters, morphology, measure, restoration
from skimage.filters import threshold_otsu
from skimage.morphology import disk, opening, closing, dilation, erosion
from skimage.segmentation import clear_border

# NLP and medical entity extraction
try:
    import spacy
    from spacy.lang.en import English
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class OCRConfig:
    """Configuration for OCR processing pipeline"""
    # Image preprocessing
    noise_reduction: bool = True
    contrast_enhancement: bool = True
    deskewing: bool = True
    morphological_operations: bool = True
    
    # OCR engines
    use_tesseract: bool = True
    use_easyocr: bool = True
    tesseract_config: str = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:-()mg/ml μg"
    
    # Text processing
    spell_correction: bool = True
    medical_entity_extraction: bool = True
    confidence_threshold: float = 0.3
    
    # Output
    include_debug_images: bool = False
    structured_output: bool = True

@dataclass
class HandwritingOCRConfig(OCRConfig):
    """Specialized configuration for handwritten medical documents"""
    # Enhanced preprocessing for handwriting
    handwriting_optimizations: bool = True
    stroke_normalization: bool = True
    ink_bleed_reduction: bool = True
    border_removal: bool = True
    
    # Adjusted OCR settings for handwriting
    tesseract_config: str = "--psm 6 --oem 1 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:-()mg/mlμg×/"
    confidence_threshold: float = 0.2  # Lower threshold for handwriting
    
    # EasyOCR optimizations
    easyocr_detail: int = 0  # More detailed text detection
    easyocr_width_ths: float = 0.7  # Text width threshold
    easyocr_height_ths: float = 0.7  # Text height threshold

def create_handwriting_config() -> HandwritingOCRConfig:
    """Create an optimized configuration for handwritten medical documents"""
    return HandwritingOCRConfig(
        # Enhanced preprocessing for handwriting
        noise_reduction=True,
        contrast_enhancement=True,
        deskewing=True,
        morphological_operations=True,
        handwriting_optimizations=True,
        stroke_normalization=True,
        ink_bleed_reduction=True,
        border_removal=True,
        
        # Optimized OCR settings
        use_tesseract=True,
        use_easyocr=True,
        confidence_threshold=0.2,  # Lower threshold for handwriting
        
        # Enhanced text processing
        spell_correction=True,
        medical_entity_extraction=True,
        
        # EasyOCR optimization for handwriting
        easyocr_detail=0,
        easyocr_width_ths=0.6,  # More lenient for handwriting
        easyocr_height_ths=0.6,  # More lenient for handwriting
        
        # Output settings
        include_debug_images=False,
        structured_output=True
    )

def create_handwriting_config() -> HandwritingOCRConfig:
    """Create optimized configuration for handwritten medical documents"""
    return HandwritingOCRConfig(
        noise_reduction=True,
        contrast_enhancement=True,
        deskewing=True,
        morphological_operations=True,
        handwriting_optimizations=True,
        stroke_normalization=True,
        ink_bleed_reduction=True,
        border_removal=True,
        use_tesseract=True,
        use_easyocr=True,
        spell_correction=True,
        medical_entity_extraction=True,
        confidence_threshold=0.2,  # Lower for handwriting
        include_debug_images=False
    )

class AdvancedOCRProcessor:
    """
    Advanced OCR processor for medical documents with maximum accuracy
    
    Pipeline Steps:
    1. Input Validation & Format Conversion
    2. Advanced Image Preprocessing
    3. Multi-Engine OCR Extraction
    4. Text Cleaning & Spell Correction
    5. Medical Entity Extraction
    6. Table Detection & Extraction
    7. Structured Output Generation
    """
    
    def __init__(self, config: Optional[OCRConfig] = None, suppress_warnings: bool = True):
        self.config = config or OCRConfig()
        self.suppress_warnings = suppress_warnings
        
        # Engine availability flags
        self.tesseract_available = False
        self.easyocr_available = False
        self.spacy_available = SPACY_AVAILABLE
        self.textblob_available = TEXTBLOB_AVAILABLE
        
        # Initialize components
        self._initialize_ocr_engines()
        self._initialize_nlp_models()
        self._initialize_medical_patterns()
    
    def _initialize_ocr_engines(self):
        """Initialize OCR engines with advanced configurations"""
        if self.suppress_warnings:
            warnings.filterwarnings('ignore', category=UserWarning, module='easyocr')
            os.environ['EASYOCR_QUIET'] = '1'
        
        # Initialize Tesseract with better error handling
        try:
            import pytesseract
            # Test if tesseract is actually accessible
            test_version = pytesseract.get_tesseract_version()
            self.tesseract_available = True
            if not self.suppress_warnings:
                logger.info(f"Tesseract OCR engine initialized - Version: {test_version}")
        except Exception as e:
            self.tesseract_available = False
            if not self.suppress_warnings:
                logger.warning("Tesseract not available - install from: https://github.com/UB-Mannheim/tesseract/wiki")
        
        # Initialize EasyOCR with better configuration
        try:
            if self.suppress_warnings:
                import sys
                from contextlib import redirect_stderr, redirect_stdout
                with redirect_stdout(open(os.devnull, 'w')), redirect_stderr(open(os.devnull, 'w')):
                    import easyocr
                    # Use higher accuracy settings
                    self.easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False, 
                                                       download_enabled=True, detector=True, recognizer=True)
            else:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['en'], gpu=False, verbose=True)
            
            self.easyocr_available = True
            if not self.suppress_warnings:
                logger.info("EasyOCR engine initialized successfully")
        except Exception as e:
            self.easyocr_available = False
            if not self.suppress_warnings:
                logger.warning(f"EasyOCR not available: {e}")
    
    def _initialize_nlp_models(self):
        """Initialize NLP models for text processing"""
        self.nlp = None
        if self.spacy_available:
            try:
                # Try to load English model
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                try:
                    # Fallback to basic English
                    self.nlp = English()
                except Exception:
                    self.spacy_available = False
    
    def _initialize_medical_patterns(self):
        """Initialize medical regex patterns for entity extraction"""
        self.medical_patterns = {
            'medications': [
                # Generic patterns for handwritten prescriptions
                r'\b\w+\s*(?:mg|ml|g|mcg|units?|IU|mEq|gm|GM|ML|MG)\b',
                r'\b(?:tab|tablet|cap|capsule|syrup|injection|drops?|Tab|Tablet|Cap|Capsule)\b',
                r'\b\w+(?:cillin|mycin|statin|prazole|sartan|pine|zole|tide|lone|ol|in|ide|ine|ate)\b',
                # Common prescription formats
                r'\bR[xp]?\s*[A-Z][a-z]+\b',  # Rx prescriptions
                r'\b[A-Z][a-z]+\s*\d+(?:mg|ml|g|mcg)?\b',  # Medication with dosage
                # Handwritten common medications (case variations)
                r'\b(?:[Pp]aracetamol|[Aa]cetaminophen|[Aa]spirin|[Ii]buprofen|[Dd]iclofenac)\b',
                r'\b(?:[Mm]etformin|[Ii]nsulin|[Aa]mlodipine|[Ll]isinopril|[Oo]meprazole)\b'
            ],
            'dosage': [
                r'\b\d+(?:\.\d+)?\s*(?:mg|ml|g|mcg|μg|units?|IU|mEq|gm|GM|ML|MG)\b',
                r'\b\d+(?:\.\d+)?%\b',
                r'\b\d+(?:\.\d+)?\s*x\s*\d+\b',  # Pattern like "500mg x 2"
                r'\b(?:half|1/2|quarter|1/4|one|two|three)\s*(?:tablet|tab|capsule|cap|tsp|tbsp)\b',
                r'\b\d+(?:\.\d+)?\s*(?:tablet|tab|capsule|cap|ml|cc)s?\b'
            ],
            'frequency': [
                r'\b(?:once|twice|thrice|\d+\s*times?)\s*(?:daily|per day|a day|weekly|monthly)\b',
                r'\b(?:BID|TID|QID|QD|PRN|HS|AC|PC|BD|TDS|QDS|OD|bid|tid|qid|qd|prn)\b',
                r'\b(?:morning|evening|noon|night|bedtime|after food|before food)\b',
                r'\b\d+(?:\-\d+)?\-\d+(?:\-\d+)?\b',  # Pattern like "1-0-1" or "1-1-1"
                r'\b(?:as needed|when required|if needed|prn|PRN)\b',
                r'\b(?:for|x)\s*\d+\s*(?:days?|weeks?|months?)\b'  # Duration patterns
            ],
            'instructions': [
                r'\b(?:take|apply|use|insert|inject|swallow|chew)\b',
                r'\b(?:with food|after food|before food|on empty stomach|with water)\b',
                r'\b(?:for \d+ days?|for \d+ weeks?|continue|stop|discontinue)\b',
                r'\b(?:do not|avoid|if symptoms persist)\b'
            ],
            'vital_signs': [
                r'\bBP:?\s*\d+/\d+\b',
                r'\b(?:pulse|heart rate|HR):?\s*\d+\b',
                r'\b(?:temperature|temp):?\s*\d+(?:\.\d+)?°?[CF]?\b',
                r'\b(?:weight|wt):?\s*\d+(?:\.\d+)?\s*(?:kg|lbs?)\b'
            ],
            'lab_values': [
                r'\b(?:hemoglobin|Hb|HGB):?\s*\d+(?:\.\d+)?\b',
                r'\b(?:glucose|sugar):?\s*\d+(?:\.\d+)?\b',
                r'\b(?:cholesterol|HDL|LDL):?\s*\d+(?:\.\d+)?\b'
            ],
            'dates': [
                r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
                r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b'
            ]
        }
    
    def preprocess_image_advanced(self, image: Union[np.ndarray, Image.Image]) -> Dict[str, np.ndarray]:
        """
        Advanced image preprocessing for maximum OCR accuracy
        
        Steps:
        1. Format conversion and validation
        2. Noise reduction and enhancement
        3. Multiple preprocessing variants
        4. Document-specific optimizations
        """
        try:
            # Convert to numpy array
            if isinstance(image, Image.Image):
                image = np.array(image)
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            else:
                gray = image.copy()
            
            processed_images = {'original': gray}
            
            # Step 1: Basic noise reduction
            if self.config.noise_reduction:
                # Gaussian blur for noise reduction
                denoised = cv2.GaussianBlur(gray, (1, 1), 0)
                
                # Bilateral filter for edge-preserving smoothing
                denoised = cv2.bilateralFilter(denoised, 9, 75, 75)
                
                # Non-local means denoising for better quality
                denoised = cv2.fastNlMeansDenoising(denoised, h=10, templateWindowSize=7, searchWindowSize=21)
                processed_images['denoised'] = denoised
            else:
                denoised = gray
            
            # Step 2: Enhanced contrast processing
            if self.config.contrast_enhancement:
                # CLAHE for adaptive histogram equalization
                clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                enhanced = clahe.apply(denoised)
                
                # Additional contrast stretching
                enhanced = cv2.convertScaleAbs(enhanced, alpha=1.3, beta=15)
                
                # Gamma correction for better visibility
                gamma = 1.2
                gamma_corrected = np.power(enhanced / 255.0, gamma) * 255.0
                enhanced = gamma_corrected.astype(np.uint8)
                
                processed_images['enhanced'] = enhanced
            else:
                enhanced = denoised
            
            # Step 3: Deskewing with improved algorithm
            if self.config.deskewing:
                deskewed = self._deskew_image_improved(enhanced)
                processed_images['deskewed'] = deskewed
            else:
                deskewed = enhanced
            
            # Step 4: Multiple binarization techniques
            binary_images = self._apply_multiple_binarization(deskewed)
            processed_images.update(binary_images)
            
            # Step 5: Morphological operations for text enhancement
            if self.config.morphological_operations:
                morphed_images = self._apply_enhanced_morphology(processed_images.get('adaptive_gaussian', deskewed))
                processed_images.update(morphed_images)
            
            # Step 6: Document-specific preprocessing
            document_optimized = self._apply_document_optimizations(processed_images.get('enhanced', enhanced))
            processed_images.update(document_optimized)
            
            # Additional preprocessing for handwritten documents
            processed_images.update(self._apply_handwriting_optimizations(gray))
            
            return processed_images
            
        except Exception as e:
            logger.error(f"Error in preprocess_image_advanced: {e}")
            # Return at least the original image
            return {'original': gray if 'gray' in locals() else image}
    def _deskew_image_improved(self, image: np.ndarray) -> np.ndarray:
        """Improved deskewing algorithm for medical documents"""
        try:
            # Convert to binary for better line detection
            _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Use HoughLines to detect text lines
            edges = cv2.Canny(binary, 50, 150, apertureSize=3)
            lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
            
            if lines is not None and len(lines) > 0:
                # Calculate average angle of detected lines
                angles = []
                for line in lines:
                    rho, theta = line[0]
                    angle = theta * 180 / np.pi
                    # Convert to rotation angle (-90 to 90 degrees)
                    if angle > 90:
                        angle = angle - 180
                    angles.append(angle)
                
                # Use median angle to avoid outliers
                if angles:
                    median_angle = np.median(angles)
                    
                    # Only correct significant skews (> 0.5 degrees)
                    if abs(median_angle) > 0.5:
                        # Rotate image to correct skew
                        (h, w) = image.shape[:2]
                        center = (w // 2, h // 2)
                        rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                        deskewed = cv2.warpAffine(image, rotation_matrix, (w, h), 
                                                flags=cv2.INTER_CUBIC, 
                                                borderMode=cv2.BORDER_REPLICATE)
                        return deskewed
            
            # Return original if no significant skew detected
            return image
            
        except Exception as e:
            logger.warning(f"Deskewing failed: {e}")
            return image
    
    def _apply_handwriting_optimizations(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Advanced preprocessing specifically for handwritten medical documents"""
        variants = {}
        
        try:
            # 1. High contrast enhancement for handwriting
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            enhanced = clahe.apply(image)
            variants['handwriting_enhanced'] = enhanced
            
            # 2. Stroke thickness normalization
            kernel = np.ones((2,2), np.uint8)
            stroke_normalized = cv2.morphologyEx(enhanced, cv2.MORPH_CLOSE, kernel)
            variants['stroke_normalized'] = stroke_normalized
            
            # 3. Ink bleed reduction
            median_filtered = cv2.medianBlur(enhanced, 3)
            variants['ink_bleed_reduced'] = median_filtered
            
            # 4. Multiple binarization for handwriting
            # Otsu with different preprocessing
            _, otsu_handwriting = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            variants['otsu_handwriting'] = otsu_handwriting
            
            # Adaptive threshold for varying lighting (common in prescriptions)
            adaptive_mean = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 8)
            variants['adaptive_handwriting'] = adaptive_mean
            
            # Adaptive Gaussian for smoother handwritten text
            adaptive_gaussian = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            variants['gaussian_handwriting'] = adaptive_gaussian
            
            # 5. Connected components analysis for handwriting
            # Remove very small components (noise) while preserving text
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(otsu_handwriting, connectivity=8)
            cleaned = np.zeros_like(otsu_handwriting)
            
            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                width = stats[i, cv2.CC_STAT_WIDTH]
                height = stats[i, cv2.CC_STAT_HEIGHT]
                
                # Keep components that are likely to be text (reasonable size for handwriting)
                if area > 15 and width > 2 and height > 2 and area < 8000:
                    cleaned[labels == i] = 255
            
            variants['components_cleaned'] = cleaned
            
            # 6. Prescription-specific skew correction
            coords = np.column_stack(np.where(otsu_handwriting > 0))
            if len(coords) > 100:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
                
                # Only correct if skew is significant but not too extreme
                if abs(angle) > 0.5 and abs(angle) < 20:
                    (h, w) = enhanced.shape[:2]
                    center = (w // 2, h // 2)
                    M = cv2.getRotationMatrix2D(center, angle, 1.0)
                    deskewed = cv2.warpAffine(enhanced, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                    variants['prescription_deskewed'] = deskewed
            
            # 7. Handwriting-specific enhancement
            # Gamma correction for faded handwriting
            gamma = 0.8  # Darken faded handwriting
            gamma_corrected = np.array(255 * (enhanced / 255) ** gamma, dtype='uint8')
            variants['gamma_handwriting'] = gamma_corrected
            
            # 8. Border and margin removal (common in prescription pads)
            h, w = enhanced.shape
            border_size = 20
            if h > border_size * 2 and w > border_size * 2:
                border_removed = enhanced[border_size:h-border_size, border_size:w-border_size]
                # Resize back to original size
                border_removed = cv2.resize(border_removed, (w, h))
                variants['border_removed'] = border_removed
            
            # 9. Prescription line detection and removal
            # Detect horizontal lines (common in prescription forms)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            detected_lines = cv2.morphologyEx(otsu_handwriting, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
            # Subtract lines to enhance handwritten text
            line_enhanced = cv2.subtract(otsu_handwriting, detected_lines)
            variants['prescription_lines_removed'] = line_enhanced
            
        except Exception as e:
            logger.warning(f"Handwriting optimization error: {e}")
        
        return variants
    
    def _deskew_image_improved(self, image: np.ndarray) -> np.ndarray:
        """Enhanced deskew algorithm with better rotation detection"""
        try:
            # Apply edge detection
            edges = cv2.Canny(image, 50, 150, apertureSize=3)
            
            # Use probabilistic Hough transform for better line detection
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
            
            if lines is not None and len(lines) > 0:
                angles = []
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Calculate angle
                    angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi
                    
                    # Normalize angle
                    if angle < -45:
                        angle += 90
                    elif angle > 45:
                        angle -= 90
                    
                    angles.append(angle)
                
                if angles:
                    # Use median angle for more robust estimation
                    median_angle = np.median(angles)
                    
                    # Only rotate if angle is significant (> 0.5 degrees)
                    if abs(median_angle) > 0.5:
                        rows, cols = image.shape
                        center = (cols // 2, rows // 2)
                        M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                        
                        # Calculate new image size
                        cos_angle = abs(M[0, 0])
                        sin_angle = abs(M[0, 1])
                        new_width = int((rows * sin_angle) + (cols * cos_angle))
                        new_height = int((rows * cos_angle) + (cols * sin_angle))
                        
                        # Adjust translation
                        M[0, 2] += (new_width / 2) - center[0]
                        M[1, 2] += (new_height / 2) - center[1]
                        
                        return cv2.warpAffine(image, M, (new_width, new_height), 
                                            flags=cv2.INTER_CUBIC, 
                                            borderMode=cv2.BORDER_CONSTANT,
                                            borderValue=255)
        except Exception:
            pass  # Return original if deskewing fails
        
        return image
    
    def _apply_multiple_binarization(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Apply multiple improved binarization techniques"""
        binary_images = {}
        
        # Otsu's thresholding
        _, otsu = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        binary_images['otsu'] = otsu
        
        # Adaptive thresholding (mean)
        adaptive_mean = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, 
                                            cv2.THRESH_BINARY, 15, 8)
        binary_images['adaptive_mean'] = adaptive_mean
        
        # Adaptive thresholding (gaussian) - usually best for documents
        adaptive_gaussian = cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                                cv2.THRESH_BINARY, 15, 8)
        binary_images['adaptive_gaussian'] = adaptive_gaussian
        
        # Triangle thresholding (good for documents with varying illumination)
        _, triangle = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_TRIANGLE)
        binary_images['triangle'] = triangle
        
        # Custom threshold based on image statistics
        mean_val = np.mean(image)
        std_val = np.std(image)
        threshold_val = max(0, min(255, mean_val - 0.5 * std_val))
        _, custom = cv2.threshold(image, threshold_val, 255, cv2.THRESH_BINARY)
        binary_images['custom'] = custom
        
        return binary_images
    
    def _apply_enhanced_morphology(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Apply enhanced morphological operations for text cleanup"""
        morphed_images = {}
        
        # Different kernel sizes for different purposes
        kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 1))
        kernel_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        kernel_line_h = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 1))
        kernel_line_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
        
        # Opening to remove noise
        opened = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel_small)
        morphed_images['opened'] = opened
        
        # Closing to fill gaps in characters
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_small)
        morphed_images['closed'] = closed
        
        # Remove horizontal lines that might interfere with text
        temp = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel_line_h)
        no_h_lines = cv2.subtract(image, temp)
        morphed_images['no_horizontal_lines'] = no_h_lines
        
        # Remove vertical lines
        temp = cv2.morphologyEx(no_h_lines, cv2.MORPH_OPEN, kernel_line_v)
        clean_text = cv2.subtract(no_h_lines, temp)
        morphed_images['clean_text'] = clean_text
        
        return morphed_images
    
    def _apply_document_optimizations(self, image: np.ndarray) -> Dict[str, np.ndarray]:
        """Apply document-specific optimizations"""
        optimized_images = {}
        
        # High contrast version for clear documents
        high_contrast = cv2.convertScaleAbs(image, alpha=2.0, beta=-50)
        optimized_images['high_contrast'] = high_contrast
        
        # Sharpening filter for blurry text
        kernel_sharpen = np.array([[-1,-1,-1],
                                 [-1, 9,-1],
                                 [-1,-1,-1]])
        sharpened = cv2.filter2D(image, -1, kernel_sharpen)
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        optimized_images['sharpened'] = sharpened
        
        # Unsharp masking for better edge definition
        gaussian = cv2.GaussianBlur(image, (0, 0), 2.0)
        unsharp = cv2.addWeighted(image, 2.0, gaussian, -1.0, 0)
        unsharp = np.clip(unsharp, 0, 255).astype(np.uint8)
        optimized_images['unsharp_mask'] = unsharp
        
        return optimized_images
    
    def extract_text_multi_engine(self, processed_images: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Extract text using multiple OCR engines and image variants with comprehensive testing"""
        results = {
            'tesseract_results': {},
            'easyocr_results': {},
            'combined_results': {}
        }
        
        # Prioritized image variants to test (best first)
        test_variants = [
            'adaptive_gaussian',   # Usually best for documents
            'unsharp_mask',       # Good for sharpening
            'clean_text',         # Morphologically cleaned
            'closed',             # Gap-filled text
            'triangle',           # Good for varying illumination
            'enhanced',           # Contrast enhanced
            'adaptive_mean',      # Alternative adaptive method
            'otsu',              # Classic binarization
            'sharpened',         # Sharpened version
            'high_contrast',     # High contrast version
            'custom',            # Custom threshold
            'deskewed',          # Rotation corrected
            'denoised',          # Noise reduced
            'original'           # Original as fallback
        ]
        
        # Filter to only available variants with None-safety
        available_variants = []
        if processed_images:
            available_variants = [v for v in test_variants if v in processed_images and processed_images.get(v) is not None]
        
        if not available_variants:
            logger.warning("No available image variants for OCR processing")
            return {
                'tesseract_results': {},
                'easyocr_results': {},
                'combined_results': {"text": "", "confidence": 0, "engine": "none"}
            }
        
        # Tesseract OCR with multiple configurations
        if self.tesseract_available and self.config.use_tesseract:
            for variant in available_variants[:8]:  # Test top 8 variants
                img = processed_images[variant]
                
                # Try different Tesseract configurations
                configs = [
                    self.config.tesseract_config,  # Default config
                    "--psm 6",                     # Uniform block of text
                    "--psm 4",                     # Single column of variable sizes
                    "--psm 3",                     # Fully automatic page segmentation
                    "--psm 8",                     # Single word
                    "--psm 7",                     # Single text line
                ]
                
                best_result = None
                best_confidence = 0
                
                for config in configs:
                    result = self._extract_text_tesseract(img, config)
                    confidence = result.get('confidence', 0)
                    
                    if confidence > best_confidence and result.get('text', '').strip():
                        best_confidence = confidence
                        best_result = result.copy()
                        best_result['source_variant'] = variant
                        best_result['tesseract_config'] = config
                
                if best_result and best_result.get('text', '').strip():
                    results['tesseract_results'][variant] = best_result
        
        # EasyOCR with multiple variants
        if self.easyocr_available and self.config.use_easyocr:
            for variant in available_variants[:10]:  # Test top 10 variants
                img = processed_images[variant]
                result = self._extract_text_easyocr(img)
                if result and result.get('confidence', 0) > 0:
                    result['variant'] = variant
                    results['easyocr_results'][variant] = result
        
        # Select and combine best results
        best_result = self._select_best_result_enhanced(results)
        results['combined_results'] = best_result
        
        return results
    
    def _select_best_result_enhanced(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced result selection with comprehensive scoring"""
        best_result = {"text": "", "confidence": 0, "engine": "none"}
        
        all_results = []
        
        # Collect all results from both engines
        for engine_results in [results.get('tesseract_results', {}), results.get('easyocr_results', {})]:
            for img_variant, result in engine_results.items():
                if (not result.get('error') and 
                    result.get('confidence', 0) > 0 and 
                    result.get('text', '').strip()):
                    all_results.append(result)
        
        if not all_results:
            return best_result
        
        # Enhanced scoring algorithm
        scored_results = []
        for result in all_results:
            text = result.get('text', '') or ""  # Ensure text is not None
            text = str(text).strip() if text else ""  # Convert to string and strip
            confidence = result.get('confidence', 0)
            word_count = result.get('word_count', 0)
            engine = result.get('engine', '')
            
            if not text:  # Skip empty text results
                continue
            
            # Base score from confidence (0-100)
            score = confidence * 0.5
            
            # Text length bonus (up to 20 points)
            text_length = len(text)
            if text_length > 10:
                score += min(text_length / 10, 20) * 0.3
            
            # Word count bonus (prefer multi-word results)
            if word_count > 2:
                score += min(word_count / 10, 15) * 0.2
            
            # Engine preference (slight preference for Tesseract on printed text)
            if engine == 'tesseract' and confidence > 60:
                score += 5
            elif engine == 'easyocr':
                score += 3  # EasyOCR is generally reliable
            
            # Variant quality scoring
            variant = result.get('source_variant', '')
            variant_bonuses = {
                'adaptive_gaussian': 8,
                'unsharp_mask': 6,
                'clean_text': 5,
                'triangle': 4,
                'enhanced': 3,
                'handwriting_enhanced': 7,  # Bonus for handwriting variants
                'stroke_normalized': 6,
                'components_cleaned': 5
            }
            score += variant_bonuses.get(variant, 0) * 0.1
            
            # Penalize very short results
            if text_length < 5:
                score *= 0.3
            
            # Bonus for medical-looking content
            if self._contains_medical_content(text):
                score += 10
            
            scored_results.append((score, result))
        
        # Select highest scoring result
        if scored_results:
            best_score, best_result = max(scored_results, key=lambda x: x[0])
            best_result['selection_score'] = best_score
        
        return best_result
    
    def _contains_medical_content(self, text: str) -> bool:
        """Check if text contains medical-related content"""
        if not text or text is None:
            return False
            
        medical_keywords = [
            'mg', 'ml', 'tablet', 'capsule', 'daily', 'twice', 'prescription',
            'patient', 'doctor', 'medicine', 'dose', 'treatment', 'symptoms',
            'diagnosis', 'medication', 'pharmacy', 'rx', 'bp', 'pulse'
        ]
        
        try:
            text_lower = text.lower()
            return any(keyword in text_lower for keyword in medical_keywords)
        except (AttributeError, TypeError):
            return False
    
    def _extract_text_tesseract(self, image: np.ndarray, config: str = None) -> Dict[str, Any]:
        """Extract text using Tesseract with enhanced error handling and configuration"""
        if not self.tesseract_available:
            return {"text": "", "confidence": 0, "error": "Tesseract not available"}
        
        try:
            import pytesseract
            
            # Use provided config or default
            tesseract_config = config or self.config.tesseract_config
            
            # Validate image
            if image is None or image.size == 0:
                return {"text": "", "confidence": 0, "error": "Invalid image"}
            
            # Ensure image is in correct format
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Extract text with detailed data
            try:
                data = pytesseract.image_to_data(image, config=tesseract_config, 
                                               output_type=pytesseract.Output.DICT)
            except Exception as ocr_error:
                # Fallback to simple text extraction if detailed extraction fails
                logger.warning(f"Detailed OCR failed, trying simple extraction: {ocr_error}")
                simple_text = pytesseract.image_to_string(image, config=tesseract_config)
                return {
                    "text": simple_text.strip(),
                    "confidence": 50.0,  # Default confidence for simple extraction
                    "engine": "tesseract",
                    "word_count": len(simple_text.split()),
                    "extraction_method": "simple"
                }
            
            # Process detailed OCR results
            if not data or 'text' not in data:
                return {"text": "", "confidence": 0, "error": "No OCR data returned"}
            
            # Filter and process results with better validation
            filtered_text = []
            confidences = []
            word_details = []
            
            confidence_threshold = self.config.confidence_threshold * 100  # Convert to percentage
            
            for i in range(len(data['text'])):
                try:
                    text = str(data['text'][i]).strip()
                    conf = int(data['conf'][i]) if data['conf'][i] not in [-1, None] else 0
                    
                    # Skip empty text and very low confidence
                    if text and conf > confidence_threshold:
                        filtered_text.append(text)
                        confidences.append(conf)
                        
                        # Add word details with validation
                        word_details.append({
                            'text': text,
                            'confidence': float(conf),
                            'bbox': {
                                'x': int(data['left'][i]) if data['left'][i] is not None else 0,
                                'y': int(data['top'][i]) if data['top'][i] is not None else 0,
                                'width': int(data['width'][i]) if data['width'][i] is not None else 0,
                                'height': int(data['height'][i]) if data['height'][i] is not None else 0
                            }
                        })
                        
                except (ValueError, TypeError, IndexError) as item_error:
                    logger.warning(f"Tesseract item processing error: {item_error}")
                    continue
            
            # Combine text and calculate average confidence
            extracted_text = ' '.join(filtered_text)
            avg_confidence = float(np.mean(confidences)) if confidences else 0.0
            
            # Post-process text to fix common OCR issues
            if extracted_text:
                extracted_text = self._clean_tesseract_text(extracted_text)
            
            return {
                "text": extracted_text,
                "confidence": avg_confidence,
                "engine": "tesseract",
                "word_count": len(filtered_text),
                "word_details": word_details,
                "extraction_method": "detailed",
                "config_used": tesseract_config
            }
            
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return {"text": "", "confidence": 0, "error": str(e)}
    
    def _clean_tesseract_text(self, text: str) -> str:
        """Clean Tesseract-specific OCR artifacts"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common Tesseract issues
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # Add space between cases
        text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)     # Join split numbers
        text = re.sub(r'\b([A-Z])\s+([a-z])', r'\1\2', text)  # Join split words
        
        return text.strip()
    
    def _extract_text_easyocr(self, image: np.ndarray) -> Dict[str, Any]:
        """Extract text using EasyOCR with handwriting-optimized processing"""
        if not self.easyocr_available:
            return {"text": "", "confidence": 0, "error": "EasyOCR not available"}
        
        try:
            # Enhanced parameters for handwritten text
            width_ths = getattr(self.config, 'easyocr_width_ths', 0.7)
            height_ths = getattr(self.config, 'easyocr_height_ths', 0.7)
            detail = getattr(self.config, 'easyocr_detail', 0)
            
            # Use optimized parameters for handwriting detection
            results = self.easyocr_reader.readtext(
                image, 
                width_ths=width_ths,
                height_ths=height_ths,
                detail=detail,
                paragraph=False  # Better for handwritten text
            )
            
            extracted_text = ""
            confidences = []
            word_details = []
            
            # Handle different EasyOCR result formats
            for result in results:
                try:
                    # EasyOCR returns list with 3 elements: [bbox, text, confidence]
                    # But sometimes returns only [text] or [bbox, text]
                    
                    text = ""
                    confidence = 0.0
                    bbox = [[0, 0], [100, 0], [100, 20], [0, 20]]  # Default bbox
                    
                    if isinstance(result, (list, tuple)):
                        if len(result) >= 3:
                            # Standard format: [bbox, text, confidence]
                            bbox, text, confidence = result[0], result[1], result[2]
                        elif len(result) == 2:
                            # Format: [bbox, text] - no confidence
                            bbox, text = result[0], result[1]
                            confidence = 0.5  # Default confidence
                        elif len(result) == 1:
                            # Format: [text] - only text
                            text = result[0]
                            confidence = 0.5  # Default confidence
                        else:
                            logger.warning(f"Unexpected EasyOCR result format: {result}")
                            continue
                    else:
                        # Direct text result
                        text = str(result)
                        confidence = 0.5
                    
                    # Ensure text is a string and clean it
                    text = str(text).strip()
                    
                    # Ensure confidence is a float between 0 and 1
                    try:
                        confidence = float(confidence)
                        if confidence > 1.0:
                            confidence = confidence / 100.0  # Convert percentage to decimal
                    except (ValueError, TypeError):
                        confidence = 0.5
                    
                    # Apply confidence threshold
                    confidence_threshold = self.config.confidence_threshold
                    if isinstance(self.config, HandwritingOCRConfig):
                        confidence_threshold = min(confidence_threshold, 0.2)
                    
                    if confidence > confidence_threshold and text:
                        extracted_text += text + " "
                        confidences.append(confidence)
                        
                        # Convert bbox to proper format with better error handling
                        converted_bbox = []
                        try:
                            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                                for point in bbox:
                                    if isinstance(point, (list, tuple)) and len(point) >= 2:
                                        x = float(point[0]) if point[0] is not None else 0.0
                                        y = float(point[1]) if point[1] is not None else 0.0
                                        converted_bbox.append([x, y])
                                    else:
                                        converted_bbox.append([0.0, 0.0])
                                
                                # Ensure we have exactly 4 points
                                while len(converted_bbox) < 4:
                                    converted_bbox.append([0.0, 0.0])
                                converted_bbox = converted_bbox[:4]
                            else:
                                # Default bbox if format is invalid
                                converted_bbox = [[0.0, 0.0], [100.0, 0.0], [100.0, 20.0], [0.0, 20.0]]
                        except Exception as bbox_error:
                            logger.warning(f"Bbox conversion error: {bbox_error}")
                            converted_bbox = [[0.0, 0.0], [100.0, 0.0], [100.0, 20.0], [0.0, 20.0]]
                        
                        word_details.append({
                            "text": text,
                            "confidence": confidence,
                            "bbox": converted_bbox
                        })
                        
                except Exception as item_error:
                    logger.warning(f"EasyOCR result processing error: {item_error}")
                    continue
            
            avg_confidence = float(np.mean(confidences)) if confidences else 0.0
            
            return {
                "text": extracted_text.strip(),
                "confidence": avg_confidence * 100,
                "engine": "easyocr",
                "word_count": len(word_details),
                "word_details": word_details
            }
            
        except Exception as e:
            logger.error(f"EasyOCR error: {e}")
            return {"text": "", "confidence": 0, "error": str(e)}
    
    def _select_best_result(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Select the best OCR result based on confidence and text quality"""
        best_result = {"text": "", "confidence": 0, "engine": "none"}
        
        all_results = []
        
        # Collect all results
        for engine_results in [results.get('tesseract_results', {}), results.get('easyocr_results', {})]:
            for img_variant, result in engine_results.items():
                if not result.get('error') and result.get('confidence', 0) > 0:
                    all_results.append(result)
        
        if not all_results:
            return best_result
        
        # Score results based on confidence and text length
        scored_results = []
        for result in all_results:
            text = result.get('text', '')
            confidence = result.get('confidence', 0)
            word_count = result.get('word_count', 0)
            
            # Scoring: confidence (70%) + text quality (30%)
            text_quality_score = min(len(text) / 100, 1.0) * 30 + min(word_count / 10, 1.0) * 20
            total_score = confidence * 0.5 + text_quality_score
            
            scored_results.append((total_score, result))
        
        # Select highest scoring result
        if scored_results:
            best_result = max(scored_results, key=lambda x: x[0])[1]
        
        return best_result
    
    def _clean_ocr_text_basic(self, text: str) -> str:
        """Basic OCR text cleaning"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove very short meaningless fragments
        if len(text) < 2:
            return ""
        
        # Remove common OCR artifacts
        text = re.sub(r'[^\w\s\d.,;:()/-]', '', text)
        
        return text
    
    def _select_best_result_enhanced(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced result selection with multiple criteria"""
        best_result = {"text": "", "confidence": 0, "engine": "none"}
        
        all_results = []
        
        # Collect all results from both engines
        for engine_name, engine_results in results.items():
            if engine_name in ['tesseract_results', 'easyocr_results']:
                for variant, result in engine_results.items():
                    if not result.get('error') and result.get('confidence', 0) > 0:
                        result['source_engine'] = engine_name.replace('_results', '')
                        result['source_variant'] = variant
                        all_results.append(result)
        
        if not all_results:
            return best_result
        
        # Enhanced scoring algorithm
        scored_results = []
        for result in all_results:
            text = result.get('text', '')
            confidence = result.get('confidence', 0)
            word_count = result.get('word_count', len(text.split()))
            engine = result.get('source_engine', '')
            
            # Base score from confidence
            score = confidence * 0.4
            
            # Text quality scoring
            text_length = len(text.strip())
            if text_length > 10:  # Prefer results with reasonable text length
                score += min(text_length / 100, 20) * 0.2
            
            # Word count scoring
            if word_count > 2:  # Prefer results with multiple words
                score += min(word_count / 10, 15) * 0.2
            
            # Engine preference (slight preference for Tesseract on printed text)
            if engine == 'tesseract' and confidence > 60:
                score += 5
            elif engine == 'easyocr':
                score += 3  # EasyOCR is generally reliable
            
            # Variant quality scoring
            variant = result.get('source_variant', '')
            variant_bonuses = {
                'adaptive_gaussian': 8,
                'unsharp_mask': 6,
                'clean_text': 5,
                'triangle': 4,
                'enhanced': 3
            }
            score += variant_bonuses.get(variant, 0) * 0.1
            
            # Penalize very short results
            if text_length < 5:
                score *= 0.3
            
            scored_results.append((score, result))
        
        # Select highest scoring result
        if scored_results:
            best_score, best_result = max(scored_results, key=lambda x: x[0])
            best_result['selection_score'] = best_score
        
        return best_result
    
    def clean_and_correct_text(self, text: str) -> Dict[str, Any]:
        """Advanced text cleaning and spell correction"""
        if not text or text is None:
            return {
                'cleaned_text': "",
                'original_text': text or "",
                'corrections_applied': [],
                'improvement_score': 0.0
            }
            
        try:
            cleaned_text = str(text)
            corrections_applied = []
            
            # Step 1: Basic cleaning
            cleaned_text = self._basic_text_cleaning(cleaned_text)
            
            # Step 2: Medical-specific corrections
            cleaned_text, med_corrections = self._apply_medical_corrections(cleaned_text)
            corrections_applied.extend(med_corrections)
            
            # Step 3: Spell correction (if available)
            if self.config.spell_correction and self.textblob_available and cleaned_text:
                try:
                    from textblob import TextBlob
                    blob = TextBlob(cleaned_text)
                    corrected = str(blob.correct())
                    if corrected != cleaned_text:
                        corrections_applied.append(f"Spell correction applied")
                        cleaned_text = corrected
                except Exception as e:
                    logger.warning(f"Spell correction failed: {e}")
            
            return {
                'cleaned_text': cleaned_text,
                'original_text': str(text),
                'corrections_applied': corrections_applied,
                'improvement_score': self._calculate_improvement_score(str(text), cleaned_text)
            }
            
        except Exception as e:
            logger.error(f"Text cleaning failed: {e}")
            return {
                'cleaned_text': str(text) if text else "",
                'original_text': str(text) if text else "",
                'corrections_applied': [],
                'improvement_score': 0.0
            }
    
    def _basic_text_cleaning(self, text: str) -> str:
        """Apply basic text cleaning operations"""
        if not text or text is None:
            return ""
            
        try:
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Fix common OCR errors
            text = re.sub(r'[^\w\s\d.,;:()/-]', '', text)  # Remove strange characters
            text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)  # Join split numbers
            text = re.sub(r'([a-zA-Z])\s+([a-zA-Z])(?=\s)', r'\1\2', text)  # Join split short words
            
            return text.strip()
        except Exception as e:
            logger.warning(f"Basic text cleaning failed: {e}")
            return str(text) if text else ""
    
    def _apply_medical_corrections(self, text: str) -> Tuple[str, List[str]]:
        """Apply medical-specific text corrections"""
        if not text or text is None:
            return "", []
            
        corrections = []
        
        try:
            # Common medical OCR corrections
            medical_corrections = {
                # Units
                'mg': ['ing', 'nig', 'mq', 'rng', 'mg.', 'mG'],
                'ml': ['ini', 'nil', 'mi', 'rnl', 'ml.', 'mL'],
                'μg': ['ug', 'mcg', 'Ag', 'pg'],
                
                # Medications
                'tablet': ['tahlet', 'tabiets', 'tabiet', 'taibet', 'tablef', 'fablef'],
                'capsule': ['capsuie', 'capsuies', 'capsuule', 'capsufe', 'eapsufe'],
                
                # Frequency
                'twice': ['twlce', 'twtce', 'twace', 'fwice', 'rwice'],
                'daily': ['dally', 'dailly', 'dailv', 'daiiy', 'daihy'],
                'morning': ['moming', 'morninq', 'mornlng', 'mornmg'],
                'evening': ['eveninq', 'evenlng', 'evenmg', 'evering'],
                
                # Medical terms
                'prescription': ['prescnption', 'prescrption', 'prescripfion', 'prescriplion'],
                'patient': ['patlent', 'patjent', 'pafient', 'pahent'],
                'doctor': ['docfor', 'docior', 'doctcr', 'docier'],
                
                # Numbers that are commonly misread
                '1': ['l', 'I', '|'],
                '0': ['O', 'o'],
                '5': ['S', 's'],
                '6': ['G', 'g'],
                '8': ['B'],
            }
            
            for correct_word, variations in medical_corrections.items():
                for variation in variations:
                    # Use word boundaries for better matching
                    pattern = r'\b' + re.escape(variation) + r'\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        text = re.sub(pattern, correct_word, text, flags=re.IGNORECASE)
                        corrections.append(f"Corrected '{variation}' to '{correct_word}'")
            
            return text, corrections
            
        except Exception as e:
            logger.warning(f"Medical corrections failed: {e}")
            return text, []
        
        return text, corrections
    
    def _calculate_improvement_score(self, original: str, cleaned: str) -> float:
        """Calculate improvement score of text cleaning"""
        if not original:
            return 0.0
        
        # Simple metrics
        original_words = len(original.split())
        cleaned_words = len(cleaned.split())
        
        # More words generally indicates better OCR
        word_improvement = min(cleaned_words / max(original_words, 1), 2.0) - 1.0
        
        # Length improvement (up to a point)
        length_improvement = min(len(cleaned) / max(len(original), 1), 1.5) - 1.0
        
        return max(0.0, min(1.0, (word_improvement + length_improvement) / 2))
    
    def extract_medical_entities(self, text: str) -> Dict[str, List[Dict]]:
        """Extract medical entities from text"""
        if not text or text is None:
            return {}
            
        entities = {}
        
        try:
            text = str(text)  # Ensure text is a string
            
            for entity_type, patterns in self.medical_patterns.items():
                found_entities = []
                
                for pattern in patterns:
                    try:
                        matches = re.finditer(pattern, text, re.IGNORECASE)
                        for match in matches:
                            found_entities.append({
                                'text': match.group(),
                                'start': match.start(),
                                'end': match.end(),
                                'pattern': pattern
                            })
                    except Exception as pattern_error:
                        logger.warning(f"Pattern matching error for {pattern}: {pattern_error}")
                        continue
                
                if found_entities:
                    entities[entity_type] = found_entities
            
            return entities
            
        except Exception as e:
            logger.error(f"Medical entity extraction failed: {e}")
            return {}
    
    def process_medical_document_advanced(self, image: Union[np.ndarray, Image.Image, str],
                                        document_type: str = "auto") -> Dict[str, Any]:
        """
        Complete advanced medical document processing pipeline
        
        Returns comprehensive results with all processing steps
        """
        try:
            start_time = datetime.now()
            
            # Step 1: Input validation and conversion
            if isinstance(image, str):
                image_data = base64.b64decode(image)
                image = Image.open(io.BytesIO(image_data))
            
            # Step 2: Advanced image preprocessing
            processed_images = self.preprocess_image_advanced(image)
            if not processed_images or not isinstance(processed_images, dict):
                logger.error("Image preprocessing failed to return valid results")
                return self._sanitize_for_mongodb({
                    'extracted_text': '',
                    'confidence': 0,
                    'error': 'Image preprocessing failed',
                    'document_type': document_type,
                    'processing_time_seconds': 0
                })
            
            # Step 3: Multi-engine OCR extraction
            ocr_results = self.extract_text_multi_engine(processed_images)
            
            # Step 4: Text cleaning and correction
            best_text = ocr_results['combined_results'].get('text', '') or ""
            if best_text is None:
                best_text = ""
            text_processing = self.clean_and_correct_text(best_text)
            
            # Step 5: Medical entity extraction
            cleaned_text = text_processing.get('cleaned_text', '') or ""
            entities = self.extract_medical_entities(cleaned_text)
            
            # Step 6: Generate structured output
            processing_time = (datetime.now() - start_time).total_seconds()
            
            structured_output = {
                # Core results
                'extracted_text': text_processing['cleaned_text'],
                'original_ocr_text': text_processing['original_text'],
                'confidence': ocr_results['combined_results'].get('confidence', 0),
                
                # Document analysis
                'document_type': document_type,
                'medical_entities': entities,
                'word_count': len(text_processing['cleaned_text'].split()),
                'character_count': len(text_processing['cleaned_text']),
                
                # Processing details
                'text_processing': text_processing,
                'ocr_engines_used': self._get_engines_used(ocr_results),
                'preprocessing_steps': list(processed_images.keys()),
                'processing_time_seconds': processing_time,
                
                # Quality metrics
                'quality_score': self._calculate_quality_score(ocr_results, text_processing),
                'completeness_score': self._calculate_completeness_score(entities),
                
                # Debug information (if requested)
                'debug_info': {
                    'all_ocr_results': ocr_results if self.config.include_debug_images else None,
                    'image_variants_tested': list(processed_images.keys()),
                    'engines_status': self.get_engines_status()
                }
            }
            
            # Sanitize for MongoDB
            return self._sanitize_for_mongodb(structured_output)
            
        except Exception as e:
            logger.error(f"Advanced medical document processing error: {e}")
            return self._sanitize_for_mongodb({
                'extracted_text': '',
                'confidence': 0,
                'error': str(e),
                'document_type': document_type,
                'processing_time_seconds': 0
            })
    
    def _get_engines_used(self, ocr_results: Dict) -> List[str]:
        """Get list of OCR engines that produced results"""
        engines = []
        if ocr_results.get('tesseract_results'):
            engines.append('tesseract')
        if ocr_results.get('easyocr_results'):
            engines.append('easyocr')
        return engines
    
    def _calculate_quality_score(self, ocr_results: Dict, text_processing: Dict) -> float:
        """Calculate overall quality score (0-1)"""
        confidence = ocr_results['combined_results'].get('confidence', 0) / 100
        improvement = text_processing.get('improvement_score', 0)
        
        # Weight: 70% confidence, 30% text improvement
        return confidence * 0.7 + improvement * 0.3
    
    def _calculate_completeness_score(self, entities: Dict) -> float:
        """Calculate how complete the extraction is based on found entities"""
        total_entity_types = len(self.medical_patterns)
        found_entity_types = len(entities)
        
        return found_entity_types / total_entity_types if total_entity_types > 0 else 0.0
    
    def get_engines_status(self) -> Dict[str, bool]:
        """Get status of all processing engines"""
        return {
            'tesseract': self.tesseract_available,
            'easyocr': self.easyocr_available,
            'spacy': self.spacy_available,
            'textblob': self.textblob_available,
            'at_least_one_ocr_available': self.tesseract_available or self.easyocr_available
        }
    
    def get_engine_status_message(self) -> str:
        """Get user-friendly status message"""
        ocr_count = sum([self.tesseract_available, self.easyocr_available])
        nlp_count = sum([self.spacy_available, self.textblob_available])
        
        if ocr_count == 2:
            ocr_msg = "✅ Both OCR engines available (Optimal)"
        elif ocr_count == 1:
            if self.easyocr_available:
                ocr_msg = "✅ EasyOCR available (Excellent for medical documents)"
            else:
                ocr_msg = "✅ Tesseract available"
        else:
            ocr_msg = "❌ No OCR engines available"
        
        if nlp_count > 0:
            nlp_msg = f" | ✅ NLP tools ready ({nlp_count}/2)"
        else:
            nlp_msg = " | ⚠️ Limited NLP capabilities"
        
        return ocr_msg + nlp_msg
    
    def _sanitize_for_mongodb(self, data: Any) -> Any:
        """Recursively sanitize data for MongoDB compatibility"""
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

# Global instance for singleton pattern
_advanced_ocr_processor_instance = None

def get_advanced_ocr_processor(config: Optional[OCRConfig] = None, 
                             suppress_warnings: bool = True) -> AdvancedOCRProcessor:
    """Get singleton advanced OCR processor instance"""
    global _advanced_ocr_processor_instance
    
    if _advanced_ocr_processor_instance is None:
        _advanced_ocr_processor_instance = AdvancedOCRProcessor(config, suppress_warnings)
    
    return _advanced_ocr_processor_instance

def reset_advanced_ocr_processor():
    """Reset the singleton instance"""
    global _advanced_ocr_processor_instance
    _advanced_ocr_processor_instance = None