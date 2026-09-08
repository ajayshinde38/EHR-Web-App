"""
Patient Dashboard - Medical Records Management with Integrated OCR
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import io
import numpy as np
from PIL import Image
from utils.auth import check_user_role, get_current_user
from utils.records import (
    save_medical_record, 
    get_patient_records, 
    delete_record,
    get_records_stats,
    export_patient_records
)
from utils.ocr_processor import get_ocr_processor, reset_ocr_processor
from utils.advanced_ocr_processor import AdvancedOCRProcessor, OCRConfig, HandwritingOCRConfig, create_handwriting_config
from utils.mongodb_storage import init_mongodb_storage
from utils.health_card import HealthCardGenerator, OTPManager
from llm_integration import summarize_text, summarize_medical_record
import logging

# PDF generation imports
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Patient Dashboard - EHR Web App",
    page_icon="🏥",
    layout="wide"
)

def clear_summarization_state():
    """Clear all summarization-related session state variables"""
    summary_keys = [
        'ocr_summary', 'use_ocr_summary', 'ocr_original_text',
        'manual_summary', 'use_manual_summary', 'manual_original_text'
    ]
    for key in summary_keys:
        if key in st.session_state:
            del st.session_state[key]

def check_authentication():
    """Check if user is authenticated and has patient role"""
    if not st.session_state.get('authenticated', False):
        st.error("Please login to access this page")
        st.stop()
    
    if not check_user_role('patient') and st.session_state.user_role != 'admin':
        st.error("Access denied. This page is for patients only.")
        st.stop()

def clean_extracted_text(text):
    """Clean and validate extracted text from PDF to remove corrupted/binary data"""
    if not text:
        return None
    
    import re
    import unicodedata
    
    # Convert to string if bytes
    if isinstance(text, bytes):
        try:
            # Try UTF-8 first
            text = text.decode('utf-8', errors='ignore')
        except:
            try:
                # Try Latin-1 as fallback
                text = text.decode('latin-1', errors='ignore')
            except:
                # Last resort - ASCII
                text = text.decode('ascii', errors='ignore')
    
    text = str(text)
    
    # Early detection of heavily corrupted content
    total_length = len(text)
    if total_length > 100:
        # Count different types of characters
        alpha_count = sum(1 for c in text if c.isalpha())
        digit_count = sum(1 for c in text if c.isdigit())
        special_count = len(re.findall(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~]', text))
        
        # If more than 40% special characters, likely corrupted
        if special_count > total_length * 0.4:
            logger.warning(f"Text appears heavily corrupted (special chars: {special_count/total_length:.2f})")
            return None
        
        # If less than 20% alphabetic characters, likely corrupted
        if alpha_count < total_length * 0.2:
            logger.warning(f"Text appears corrupted (alpha chars: {alpha_count/total_length:.2f})")
            return None
    
    # Remove binary/corrupted characters that look like your example
    # Remove sequences of special characters and control codes
    text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)  # Keep only printable ASCII + whitespace
    
    # Remove sequences that look like binary corruption (more aggressive)
    text = re.sub(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~]{3,}', ' ', text)
    
    # Remove repeated pattern characters
    text = re.sub(r'(.)\1{6,}', r'\1', text)  # Replace 6+ repeated chars with single char
    
    # Remove lines that look like corruption patterns
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if line:
            # Skip lines that are obviously corrupted
            if re.match(r'^[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~0-9-]+$', line):
                continue  # Skip lines with only symbols/numbers/dashes
            
            # Skip very short lines with mostly symbols
            if len(line) < 15 and re.search(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~]{3,}', line):
                continue
            
            # Skip lines with too many special characters
            special_count = len(re.findall(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~]', line))
            if special_count > len(line) * 0.6:  # More than 60% special chars
                continue
            
            # Count alphabetic characters vs total
            alpha_count = sum(1 for c in line if c.isalpha())
            total_count = len(line)
            
            # Keep line if it has reasonable text content (>25% alphabetic)
            if total_count > 0 and alpha_count / total_count > 0.25:
                clean_lines.append(line)
            elif any(word.lower() in ['patient', 'medication', 'dose', 'mg', 'treatment', 'diagnosis', 'doctor', 'hospital', 'medical', 'name', 'age', 'date', 'report', 'test', 'lab'] for word in line.lower().split()):
                # Keep lines with medical keywords even if low alpha ratio
                clean_lines.append(line)
    
    cleaned_text = '\n'.join(clean_lines)
    
    # Final validation - ensure we have meaningful content
    if len(cleaned_text.strip()) < 15:
        logger.warning("Extracted text too short after cleaning - likely corrupted")
        return None
    
    # Check if result is mostly readable
    alpha_count = sum(1 for c in cleaned_text if c.isalpha())
    total_count = len(cleaned_text.replace(' ', '').replace('\n', '').replace('\t', ''))
    
    if total_count > 0 and alpha_count / total_count < 0.35:  # Increased threshold
        logger.warning(f"Extracted text appears to be corrupted or binary data (alpha ratio: {alpha_count/total_count:.2f})")
        return None
    
    # Check for excessive repetition (sign of corruption)
    if len(cleaned_text) > 100:
        # Look for patterns that repeat too much
        words = cleaned_text.split()
        if len(words) > 10:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                logger.warning("Text has excessive repetition - likely corrupted")
                return None
    
    # Check for specific corruption patterns like your example
    corruption_patterns = [
        r'[QQQQQQQQ]{8,}',  # Long sequences of Q
        r'[()]{10,}',       # Long sequences of parentheses
        r'[\d!@#$%^&*]+BR[\d!@#$%^&*]+',  # Pattern like your example
    ]
    
    for pattern in corruption_patterns:
        if re.search(pattern, cleaned_text):
            logger.warning(f"Detected corruption pattern: {pattern}")
            return None
    
    return cleaned_text.strip()

def extract_text_from_pdf(uploaded_file):
    """Enhanced PDF text extraction with multiple methods and comprehensive fallbacks"""
    try:
        from io import BytesIO
        import logging
        
        logger.info("Starting PDF text extraction process...")
        
        # Reset file pointer and validate file
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        
        if not file_content or len(file_content) < 100:
            logger.error(f"PDF file is empty or too small: {len(file_content) if file_content else 0} bytes")
            return None
        
        logger.info(f"PDF file loaded: {len(file_content)} bytes")
        
        # Check if it's actually a PDF
        if not file_content.startswith(b'%PDF'):
            logger.error("File doesn't have valid PDF header")
            return None
        
        pdf_bytes = BytesIO(file_content)
        extracted_text = ""
        
        # Method 1: Try PyPDF2 first (most common) with enhanced error handling
        try:
            import PyPDF2
            logger.info("Attempting PyPDF2 extraction...")
            pdf_bytes.seek(0)
            pdf_reader = PyPDF2.PdfReader(pdf_bytes)
            
            logger.info(f"PDF has {len(pdf_reader.pages)} pages")
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                logger.warning("PDF is encrypted/password protected")
                # Try empty password first
                try:
                    decrypt_result = pdf_reader.decrypt("")
                    logger.info(f"Decrypt attempt result: {decrypt_result}")
                except Exception as decrypt_error:
                    logger.error(f"Cannot decrypt PDF: {decrypt_error}")
                    # Continue to other methods
            
            text = ""
            pages_processed = 0
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text += page_text + "\n"
                        pages_processed += 1
                except Exception as page_error:
                    logger.warning(f"PyPDF2 failed on page {page_num + 1}: {page_error}")
                    continue
            
            logger.info(f"PyPDF2 processed {pages_processed}/{len(pdf_reader.pages)} pages")
            
            if text.strip():
                # Clean the extracted text before returning
                cleaned_text = clean_extracted_text(text.strip())
                if cleaned_text:
                    logger.info(f"PyPDF2 successfully extracted and cleaned {len(cleaned_text)} characters")
                    return cleaned_text
                else:
                    logger.warning("PyPDF2 extracted text was corrupted/unreadable after cleaning")
                
        except ImportError:
            logger.warning("PyPDF2 not available - install with: pip install PyPDF2")
        except Exception as pypdf_error:
            logger.error(f"PyPDF2 extraction failed: {pypdf_error}")
            import traceback
            logger.error(f"PyPDF2 traceback: {traceback.format_exc()}")
        
        # Method 2: Try pdfplumber (better for complex layouts)
        try:
            import pdfplumber
            pdf_bytes.seek(0)
            
            text = ""
            with pdfplumber.open(pdf_bytes) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    try:
                        # Try multiple extraction methods within pdfplumber
                        page_text = page.extract_text()
                        if not page_text or not page_text.strip():
                            # Try with different settings
                            page_text = page.extract_text(layout=True)
                        if not page_text or not page_text.strip():
                            # Try extracting words individually
                            words = page.extract_words()
                            if words:
                                page_text = " ".join([word['text'] for word in words])
                        
                        if page_text and page_text.strip():
                            text += page_text + "\n"
                    except Exception as page_error:
                        logger.warning(f"pdfplumber failed on page {page_num + 1}: {page_error}")
                        continue
            
            if text.strip():
                # Clean the extracted text before returning
                cleaned_text = clean_extracted_text(text.strip())
                if cleaned_text:
                    logger.info(f"pdfplumber successfully extracted and cleaned {len(cleaned_text)} characters")
                    return cleaned_text
                else:
                    logger.warning("pdfplumber extracted text was corrupted/unreadable after cleaning")
                
        except ImportError:
            logger.info("pdfplumber not available - install with: pip install pdfplumber")
        except Exception as plumber_error:
            logger.warning(f"pdfplumber extraction failed: {plumber_error}")
        
        # Method 3: Try pymupdf (fitz) for complex PDFs
        try:
            import fitz  # PyMuPDF
            pdf_bytes.seek(0)
            
            text = ""
            doc = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
            
            for page_num in range(doc.page_count):
                try:
                    page = doc[page_num]
                    # Try different extraction methods
                    page_text = page.get_text()
                    
                    if not page_text or not page_text.strip():
                        # Try with different extraction modes
                        page_text = page.get_text("text")
                    
                    if not page_text or not page_text.strip():
                        # Try extracting text blocks
                        blocks = page.get_text("dict")
                        text_parts = []
                        for block in blocks.get("blocks", []):
                            if "lines" in block:
                                for line in block["lines"]:
                                    for span in line.get("spans", []):
                                        text_parts.append(span.get("text", ""))
                        page_text = " ".join(text_parts)
                    
                    if page_text and page_text.strip():
                        text += page_text + "\n"
                except Exception as page_error:
                    logger.warning(f"PyMuPDF failed on page {page_num + 1}: {page_error}")
                    continue
            
            doc.close()
            
            if text.strip():
                # Clean the extracted text before returning
                cleaned_text = clean_extracted_text(text.strip())
                if cleaned_text:
                    logger.info(f"PyMuPDF successfully extracted and cleaned {len(cleaned_text)} characters")
                    return cleaned_text
                else:
                    logger.warning("PyMuPDF extracted text was corrupted/unreadable after cleaning")
                
        except ImportError:
            logger.info("PyMuPDF not available - install with: pip install pymupdf")
        except Exception as fitz_error:
            logger.warning(f"PyMuPDF extraction failed: {fitz_error}")
        
        # Method 4: Try pdfminer for difficult PDFs
        try:
            from pdfminer.high_level import extract_text as pdfminer_extract
            from pdfminer.layout import LAParams
            pdf_bytes.seek(0)
            
            # Try with different parameters
            laparams = LAParams(
                boxes_flow=0.5,
                word_margin=0.1,
                char_margin=2.0,
                line_margin=0.5
            )
            
            text = pdfminer_extract(pdf_bytes, laparams=laparams)
            if not text or not text.strip():
                # Try without layout parameters
                pdf_bytes.seek(0)
                text = pdfminer_extract(pdf_bytes)
            
            if text and text.strip():
                # Clean the extracted text before returning
                cleaned_text = clean_extracted_text(text.strip())
                if cleaned_text:
                    logger.info(f"pdfminer successfully extracted and cleaned {len(cleaned_text)} characters")
                    return cleaned_text
                else:
                    logger.warning("pdfminer extracted text was corrupted/unreadable after cleaning")
                
        except ImportError:
            logger.info("pdfminer not available - install with: pip install pdfminer.six")
        except Exception as miner_error:
            logger.warning(f"pdfminer extraction failed: {miner_error}")
        
        # Method 5: Last resort - try to extract as text stream
        try:
            pdf_bytes.seek(0)
            raw_content = pdf_bytes.read()
            
            # Look for text patterns in raw PDF content
            import re
            text_patterns = re.findall(rb'\(([^)]*)\)', raw_content)
            if text_patterns:
                text_parts = []
                for pattern in text_patterns:
                    try:
                        decoded = pattern.decode('utf-8', errors='ignore')
                        if decoded.strip() and len(decoded) > 2:
                            text_parts.append(decoded)
                    except:
                        continue
                
                if text_parts:
                    raw_text = " ".join(text_parts)
                    # Clean the extracted text before returning
                    cleaned_text = clean_extracted_text(raw_text)
                    if cleaned_text:
                        logger.info(f"Raw extraction found and cleaned {len(cleaned_text)} characters")
                        return cleaned_text
                    else:
                        logger.warning("Raw extraction found text but it was corrupted/unreadable after cleaning")
                    
        except Exception as raw_error:
            logger.warning(f"Raw text extraction failed: {raw_error}")
        
        # If all methods fail, return None to trigger OCR fallback
        logger.error("All PDF extraction methods failed or returned corrupted data - will try OCR fallback")
        return None
    
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return None

def extract_text_from_docx(uploaded_file):
    """Extract text from DOCX file"""
    try:
        from docx import Document
        from io import BytesIO
        
        # Read the DOCX file
        doc_bytes = BytesIO(uploaded_file.read())
        doc = Document(doc_bytes)
        
        # Extract text from all paragraphs
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        return text.strip()
    
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return None

def extract_text_from_pdf_with_ocr(uploaded_file):
    """Fallback PDF extraction using OCR for image-based or difficult PDFs"""
    try:
        import fitz  # PyMuPDF for PDF to image conversion
        from io import BytesIO
        from PIL import Image
        import numpy as np
        
        logger.info("Starting OCR-based PDF extraction...")
        
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        
        if not file_content:
            logger.error("No file content for OCR extraction")
            return None
        
        logger.info(f"OCR processing file: {len(file_content)} bytes")
        
        # Convert PDF pages to images and run OCR
        doc = fitz.open(stream=file_content, filetype="pdf")
        logger.info(f"PDF opened for OCR: {doc.page_count} pages")
        
        extracted_pages = []
        max_pages = min(doc.page_count, 10)  # Limit to first 10 pages
        
        for page_num in range(max_pages):
            try:
                logger.info(f"Processing page {page_num + 1}/{max_pages} with OCR...")
                page = doc[page_num]
                
                # Convert to image at higher resolution for better OCR
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("ppm")
                img = Image.open(BytesIO(img_data))
                logger.info(f"Page {page_num + 1} converted to image: {img.size}")
                
                # Convert to numpy array for OCR
                img_array = np.array(img)
                
                # Use the advanced OCR processor
                from utils.advanced_ocr_processor import AdvancedOCRProcessor, create_handwriting_config
                config = create_handwriting_config()
                ocr_processor = AdvancedOCRProcessor(config)
                
                ocr_result = ocr_processor.process_medical_document_advanced(img_array)
                page_text = ocr_result.get('extracted_text', '')
                
                logger.info(f"OCR result for page {page_num + 1}: {len(page_text)} characters, confidence: {ocr_result.get('confidence', 'N/A')}")
                
                # Clean the OCR text before adding
                if page_text and page_text.strip():
                    cleaned_page_text = clean_extracted_text(page_text.strip())
                    if cleaned_page_text:
                        extracted_pages.append(f"Page {page_num + 1}:\n{cleaned_page_text}")
                        logger.info(f"Page {page_num + 1} text added: {len(cleaned_page_text)} clean characters")
                    else:
                        logger.warning(f"OCR text from page {page_num + 1} was corrupted/unreadable after cleaning")
                else:
                    logger.warning(f"No text extracted from page {page_num + 1}")
                    
            except Exception as page_error:
                logger.error(f"OCR failed on PDF page {page_num + 1}: {page_error}")
                import traceback
                logger.error(f"Page {page_num + 1} traceback: {traceback.format_exc()}")
                continue
        
        doc.close()
        
        if extracted_pages:
            full_text = "\n\n".join(extracted_pages)
            logger.info(f"PDF OCR extraction successful: {len(full_text)} characters from {len(extracted_pages)} pages")
            return full_text
        else:
            logger.error("PDF OCR extraction failed - no text found from any page")
            return None
            
    except ImportError as import_error:
        logger.error(f"PDF OCR extraction requires additional libraries: {import_error}")
        return None
    except Exception as e:
        logger.error(f"PDF OCR extraction error: {e}")
        import traceback
        logger.error(f"OCR extraction traceback: {traceback.format_exc()}")
        return None

def clean_text_for_pdf(text):
    """Clean and escape text content for PDF generation to prevent parsing errors"""
    if not text:
        return ""
    
    import html
    import re
    
    # Convert to string if not already
    text = str(text)
    
    # Remove or replace problematic HTML tags and characters
    # Replace self-closing tags that cause issues
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<hr\s*/?>', '\n---\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<img[^>]*>', '[IMAGE]', text, flags=re.IGNORECASE)
    
    # Remove other HTML tags but keep the content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Escape HTML entities
    text = html.unescape(text)
    
    # Replace problematic Unicode characters that might cause PDF issues
    problematic_chars = {
        '\u019f': 'f',  # Replace ƒ with f
        '\u01a9': 't',  # Replace ƪ with t
        '\u2019': "'",  # Replace right single quotation mark
        '\u201c': '"',  # Replace left double quotation mark
        '\u201d': '"',  # Replace right double quotation mark
        '\u2013': '-',  # Replace en dash
        '\u2014': '--', # Replace em dash
        '\u2026': '...', # Replace ellipsis
    }
    
    for char, replacement in problematic_chars.items():
        text = text.replace(char, replacement)
    
    # Replace any remaining non-ASCII characters with their closest ASCII equivalent
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Clean up multiple whitespace characters
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # Limit line length to prevent very long lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if len(line) > 100:
            # Break very long lines at word boundaries
            words = line.split()
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 > 100 and current_line:
                    cleaned_lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word) + 1
            
            if current_line:
                cleaned_lines.append(' '.join(current_line))
        else:
            cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    
    return text.strip()

def upload_medical_record():
    """Enhanced upload medical record functionality with integrated OCR"""
    st.header("Upload Medical Documents")
    st.write("Upload your medical documents - images will be automatically processed with OCR and stored in the database.")
    
    # Get current user
    current_user = get_current_user()
    if not current_user:
        st.error("Failed to load user data")
        return
    
    # File upload options
    upload_method = st.radio(
        "Choose upload method:",
        ["Upload File/Image", "Enter Text Directly"],
        horizontal=True
    )
    
    # Initialize session state for extracted text and results
    if 'extracted_text' not in st.session_state:
        st.session_state.extracted_text = ""
    if 'current_ocr_results' not in st.session_state:
        st.session_state.current_ocr_results = None
    
    medical_text = st.session_state.extracted_text  # Get from session state
    file_name = None
    file_type = None
    file_size = None
    ocr_results = st.session_state.current_ocr_results  # Get from session state
    uploaded_file = None
    
    if upload_method == "Upload File/Image":
        st.subheader(" Document Upload with Auto-OCR")
        
        uploaded_file = st.file_uploader(
            "Choose a medical document or image",
            type=['txt', 'pdf', 'docx', 'jpg', 'jpeg', 'png', 'tiff', 'bmp'],
            help="Supported formats: TXT, PDF, DOCX, JPG, PNG, TIFF, BMP (Max size: 10MB)"
        )
        
        if uploaded_file is not None:
            file_name = uploaded_file.name
            file_type = uploaded_file.type
            file_size = uploaded_file.size
            
            # Create unique file identifier to prevent re-processing
            file_id = f"{file_name}_{file_size}_{file_type}"
            
            # Check if this file has already been processed
            if 'last_processed_file_id' not in st.session_state:
                st.session_state.last_processed_file_id = None
            
            # Only process if it's a different file or first time
            file_already_processed = (st.session_state.last_processed_file_id == file_id and 
                                    'extracted_text' in st.session_state and 
                                    st.session_state.extracted_text)
            
            # Display file information
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("File Name", file_name)
            with col2:
                st.metric("File Size", f"{file_size/1024:.1f} KB")
            with col3:
                st.metric("File Type", file_type.split('/')[-1].upper())
            
            # Show processing status
            if file_already_processed:
                st.success("File already processed - using cached results")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info("To reprocess this file, use the 'Clear Cache' button or refresh the page")
                with col2:
                    if st.button("Clear Cache", help="Clear cached results and reprocess file"):
                        st.session_state.last_processed_file_id = None
                        st.session_state.extracted_text = ""
                        st.session_state.current_ocr_results = None
                        st.rerun()
                medical_text = st.session_state.extracted_text
            else:
                # Process file based on type
                with st.spinner("🔄 Processing document..."):
                    if uploaded_file.type == "text/plain":
                        # Text file processing
                        uploaded_file.seek(0)
                        medical_text = str(uploaded_file.read(), "utf-8")
                        st.session_state.extracted_text = medical_text  # Store in session state
                        st.session_state.current_ocr_results = None  # No OCR results for text
                        st.session_state.last_processed_file_id = file_id  # Mark as processed
                        st.success("Text file processed successfully!")
                        
                        # Show text preview immediately
                        with st.expander("📄 Preview Text File Content", expanded=True):
                            # Allow editing of text file content
                            edited_text = st.text_area(
                                "Review and edit text content:",
                                value=medical_text,
                                height=200,
                                help="Review the text file content and make any necessary edits."
                            )
                            if edited_text != medical_text:
                                medical_text = edited_text
                                st.session_state.extracted_text = medical_text  # Update session state
                                st.info("Text has been edited")
                        
                        # Immediate AI Summarization Option for Text Files
                        if len(medical_text.strip()) > 50:
                            st.divider()
                            st.subheader("AI Medical Summarization")
                            st.info("Generate a professional medical summary of your text file")
                            
                            # Initialize session state for text file summary
                            if 'text_file_summary' not in st.session_state:
                                st.session_state.text_file_summary = None
                            if 'use_text_file_summary' not in st.session_state:
                                st.session_state.use_text_file_summary = False
                            if 'text_file_original_text' not in st.session_state:
                                st.session_state.text_file_original_text = medical_text
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown("**Generate AI Summary:** Creates a structured medical summary with key findings, diagnoses, and recommendations")
                            with col2:
                                if st.button("Generate Summary", type="primary", key="text_file_summary_btn"):
                                    with st.spinner("AI is analyzing your text file..."):
                                        try:
                                            current_text = st.session_state.extracted_text or medical_text
                                            if not current_text or len(current_text.strip()) < 10:
                                                st.error("No text available to summarize.")
                                            else:
                                                summary = summarize_medical_record(current_text, max_length=250, min_length=60)
                                                st.session_state.text_file_summary = summary
                                                st.session_state.text_file_original_text = current_text
                                                st.success("Medical summary generated!")
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Summary generation failed: {str(e)}")
                            
                            # Display text file summary if generated
                            if st.session_state.text_file_summary:
                                st.success("AI Medical Summary Generated")
                                
                                # Show formatted summary
                                st.markdown("### Professional Medical Summary")
                                st.markdown(f"""
                                <div style="
                                    background-color: #f8fffe;
                                    border-left: 4px solid #28a745;
                                    padding: 20px;
                                    border-radius: 8px;
                                    margin: 15px 0;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                ">
                                    <div style="color: #155724; line-height: 1.8; font-size: 15px; white-space: pre-line;">
                                        {st.session_state.text_file_summary}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Summary stats
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    compression = len(st.session_state.text_file_summary) / len(st.session_state.text_file_original_text) * 100
                                    st.metric("Compression", f"{compression:.1f}%")
                                with col2:
                                    st.metric("Summary Length", f"{len(st.session_state.text_file_summary)} chars")
                                with col3:
                                    st.metric("Words", f"{len(st.session_state.text_file_summary.split())}")
                                
                                # Option to use summary
                                use_summary = st.checkbox(
                                    "Use AI summary as primary record text", 
                                    value=st.session_state.use_text_file_summary,
                                    key="use_text_file_summary_checkbox"
                                )
                                st.session_state.use_text_file_summary = use_summary
                                
                                if use_summary:
                                    medical_text = st.session_state.text_file_summary
                                    st.success("AI summary will be saved as the record!")
                                    st.info("Only the professional medical summary will be saved.")
                                else:
                                    st.info("Original text file content will be used as primary content.")
                    
                    elif uploaded_file.type == "application/pdf":
                        # Enhanced PDF processing with comprehensive diagnostics
                        st.info("Analyzing PDF file...")
                        
                        # Reset file pointer and get basic info
                        uploaded_file.seek(0)
                        file_size = len(uploaded_file.read())
                        uploaded_file.seek(0)
                        
                        # Show file diagnostics
                        with st.expander("📊 PDF File Diagnostics", expanded=True):
                            st.write(f"**File name:** {uploaded_file.name}")
                            st.write(f"**File size:** {file_size:,} bytes ({file_size/1024:.1f} KB)")
                            st.write(f"**MIME type:** {uploaded_file.type}")
                            
                            # Check if file is actually a PDF
                            file_header = uploaded_file.read(10)
                            uploaded_file.seek(0)
                            is_pdf = file_header.startswith(b'%PDF')
                            st.write(f"**Valid PDF header:** {'Yes' if is_pdf else 'No - file may be corrupted'}")
                            
                            if not is_pdf:
                                st.error("This file doesn't appear to be a valid PDF. Please check the file format.")
                                return
                        
                        # Try extraction with detailed progress
                        with st.spinner("Attempting PDF text extraction..."):
                            extracted_text = extract_text_from_pdf(uploaded_file)
                        
                        # Show extraction results
                        if extracted_text:
                            st.success("Standard PDF extraction succeeded!")
                        else:
                            st.warning("Standard PDF extraction failed")
                            
                            # Detailed failure analysis
                            with st.expander("🔍 Extraction Failure Analysis", expanded=True):
                                st.write("**Possible reasons for failure:**")
                                st.write("• PDF contains only images/scans (needs OCR)")
                                st.write("• PDF is password-protected")
                                st.write("• PDF has complex formatting or non-standard structure")
                                st.write("• PDF is corrupted or uses unsupported features")
                                
                                # Check if OCR libraries are available
                                ocr_available = True
                                try:
                                    import fitz
                                    from PIL import Image
                                    st.write("• PyMuPDF (fitz): ✅ Available")
                                except ImportError:
                                    st.write("• PyMuPDF (fitz): ❌ Missing")
                                    ocr_available = False
                                
                                if ocr_available:
                                    # Try OCR-based extraction
                                    st.info("Attempting OCR-based extraction...")
                                    with st.spinner("Converting PDF to images and running OCR..."):
                                        extracted_text = extract_text_from_pdf_with_ocr(uploaded_file)
                                    
                                    if extracted_text:
                                        st.success("OCR extraction succeeded!")
                                    else:
                                        st.error("OCR extraction also failed")
                                        
                                        # Final troubleshooting
                                        st.subheader("Troubleshooting Options")
                                        st.write("**Since both standard and OCR extraction failed, try these alternatives:**")
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.write("**Option 1: Screenshot Method**")
                                            st.write("1. Take a screenshot of each PDF page")
                                            st.write("2. Upload screenshots as JPG/PNG images")
                                            st.write("3. Use the image OCR feature instead")
                                        
                                        with col2:
                                            st.write("**Option 2: Text Copy Method**")
                                            st.write("1. Open PDF in another viewer")
                                            st.write("2. Copy the text manually")
                                            st.write("3. Use 'Enter Text Directly' option above")
                                        
                                        st.write("**Option 3: PDF Conversion**")
                                        st.write("• Convert PDF to Word document first")
                                        st.write("• Upload the Word document instead")
                                        st.write("• Or save PDF pages as individual images")
                                        
                                        return  # Exit early if everything failed
                                else:
                                    st.error("OCR libraries not available - cannot attempt image-based extraction")
                                    return
                        
                        if extracted_text:
                            medical_text = extracted_text
                            st.session_state.extracted_text = medical_text  # Store in session state
                            st.session_state.current_ocr_results = None  # No OCR results for PDF
                            st.session_state.last_processed_file_id = file_id  # Mark as processed
                            st.success("PDF processed successfully!")
                            st.info(f"Extracted {len(medical_text)} characters from PDF")
                            
                            # Show extraction method used
                            with st.expander("PDF Extraction Details"):
                                st.write("**Text successfully extracted from PDF**")
                                st.write(f"**Total characters:** {len(medical_text)}")
                                st.write(f"**Total words:** {len(medical_text.split())}")
                                st.write(f"**Total lines:** {len(medical_text.split(chr(10)))}")
                                
                                # Check if OCR was used
                                if "Page 1:" in medical_text:
                                    st.write("**Extraction method:** OCR-based (PDF converted to images)")
                                    st.info("💡 This PDF was processed using OCR because it contains images or complex layouts")
                                else:
                                    st.write("**Extraction method:** Direct text extraction")
                        
                        # Show extracted text preview immediately
                        with st.expander("📄 Preview Extracted Text", expanded=True):
                            # Allow editing of PDF extracted text
                            edited_text = st.text_area(
                                "Review and edit extracted text:",
                                value=medical_text,
                                height=200,
                                help="PDF text may contain formatting errors. Please review and correct if needed."
                            )
                            if edited_text != medical_text:
                                medical_text = edited_text
                                st.session_state.extracted_text = medical_text  # Update session state
                                st.info("✅ Text has been edited")
                        
                        # Immediate AI Summarization Option for PDF
                        if len(medical_text.strip()) > 50:
                            st.divider()
                            st.subheader("🤖 AI Medical Summarization")
                            st.info("💡 Generate a professional medical summary of your extracted PDF text")
                            
                            # Initialize session state for PDF summary
                            if 'pdf_summary' not in st.session_state:
                                st.session_state.pdf_summary = None
                            if 'use_pdf_summary' not in st.session_state:
                                st.session_state.use_pdf_summary = False
                            if 'pdf_original_text' not in st.session_state:
                                st.session_state.pdf_original_text = medical_text
                            
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown("**Generate AI Summary:** Creates a structured medical summary with key findings, diagnoses, and recommendations")
                            with col2:
                                if st.button("🚀 Generate Summary", type="primary", key="pdf_summary_btn"):
                                    with st.spinner("🤖 AI is analyzing your PDF text..."):
                                        try:
                                            current_text = st.session_state.extracted_text or medical_text
                                            if not current_text or len(current_text.strip()) < 10:
                                                st.error("❌ No text available to summarize.")
                                            else:
                                                summary = summarize_medical_record(current_text, max_length=250, min_length=60)
                                                st.session_state.pdf_summary = summary
                                                st.session_state.pdf_original_text = current_text
                                                st.success("✅ Medical summary generated!")
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"❌ Summary generation failed: {str(e)}")
                            
                            # Display PDF summary if generated
                            if st.session_state.pdf_summary:
                                st.success("✅ AI Medical Summary Generated")
                                
                                # Show formatted summary
                                st.markdown("### 📋 Professional Medical Summary")
                                st.markdown(f"""
                                <div style="
                                    background-color: #f8fffe;
                                    border-left: 4px solid #28a745;
                                    padding: 20px;
                                    border-radius: 8px;
                                    margin: 15px 0;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                ">
                                    <div style="color: #155724; line-height: 1.8; font-size: 15px; white-space: pre-line;">
                                        {st.session_state.pdf_summary}
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Summary stats
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    compression = len(st.session_state.pdf_summary) / len(st.session_state.pdf_original_text) * 100
                                    st.metric("📊 Compression", f"{compression:.1f}%")
                                with col2:
                                    st.metric("📏 Summary Length", f"{len(st.session_state.pdf_summary)} chars")
                                with col3:
                                    st.metric("📖 Words", f"{len(st.session_state.pdf_summary.split())}")
                                
                                # Option to use summary
                                use_summary = st.checkbox(
                                    "✨ Use AI summary as primary record text", 
                                    value=st.session_state.use_pdf_summary,
                                    key="use_pdf_summary_checkbox"
                                )
                                st.session_state.use_pdf_summary = use_summary
                                
                                if use_summary:
                                    medical_text = st.session_state.pdf_summary
                                    st.success("✅ AI summary will be saved as the record!")
                                    st.info("💡 Only the professional medical summary will be saved.")
                                else:
                                    st.info("💡 Original PDF text will be used as primary content.")
                        else:
                            st.error("❌ PDF extraction failed with all available methods")
                            with st.expander("🔧 Troubleshooting PDF Issues"):
                                st.write("""
                                **PDF extraction failed. Here are some solutions:**
                                
                                **Common Issues:**
                                • Scanned PDF (image-based) - needs OCR
                                • Password-protected PDF
                                • Corrupted or non-standard PDF format
                                • PDF with complex layouts or forms
                                
                                **Recommended Solutions:**
                                1. **For Scanned PDFs:** Convert to image (JPG/PNG) and use OCR upload
                                2. **For Protected PDFs:** Remove password protection first
                                3. **For Complex PDFs:** Copy text manually and use text input method
                                4. **Alternative:** Take a screenshot and upload as image for OCR
                                
                                **Missing PDF Libraries:**
                                Some advanced PDF extraction requires additional packages:
                                • `pip install pdfplumber` - for complex layouts
                                • `pip install pymupdf` - for advanced PDF processing
                                • `pip install pdfminer.six` - for difficult PDFs
                                """)
                            st.info("💡 **Alternative**: Convert your PDF to an image (JPG/PNG) and use the OCR feature for better results.")
                
                    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                        # DOCX processing
                        uploaded_file.seek(0)
                        extracted_text = extract_text_from_docx(uploaded_file)
                        if extracted_text:
                            medical_text = extracted_text
                            st.session_state.extracted_text = medical_text  # Store in session state
                            st.session_state.current_ocr_results = None  # No OCR results for DOCX
                            st.session_state.last_processed_file_id = file_id  # Mark as processed
                            st.success("✅ DOCX processed successfully!")
                            st.info(f"📄 Extracted {len(medical_text)} characters from DOCX")
                        else:
                            st.warning("⚠️ DOCX extraction failed. Please use text input method.")
                
                    elif uploaded_file.type in ["image/jpeg", "image/jpg", "image/png", "image/tiff", "image/bmp"]:
                        # Image processing with OCR
                        from PIL import Image as PILImage
                        uploaded_file.seek(0)
                        image = PILImage.open(uploaded_file)
                        
                        # Display uploaded image
                        st.image(image, caption="📷  Uploaded Medical Image", width=400)
                        
                        # Show OCR system info
                        # OCR Processing
                        use_advanced = st.session_state.get('use_advanced_ocr', True)
                        
                        if use_advanced:
                            # Initialize advanced OCR processor
                            config = st.session_state.get('ocr_config', OCRConfig())
                            advanced_ocr = AdvancedOCRProcessor(config)
                            st.info(f"🚀 Advanced OCR: {advanced_ocr.get_engines_status()}")
                            spinner_text = "🔄 Running Advanced OCR Pipeline..."
                        else:
                            ocr_info = get_ocr_processor(suppress_warnings=True)
                            st.info(f"ℹ️ {ocr_info.get_engine_status_message()}")
                            spinner_text = "🔄 Running Standard OCR..."
                        
                        with st.spinner(spinner_text):
                            try:
                                # Convert PIL image to numpy array for OCR
                                image_array = np.array(image)
                                
                                if use_advanced:
                                    # Use advanced OCR processor
                                    config = st.session_state.get('ocr_config', OCRConfig())
                                    advanced_ocr = AdvancedOCRProcessor(config)
                                    ocr_results = advanced_ocr.process_medical_document_advanced(
                                        image_array, 
                                        document_type="auto"
                                    )
                                else:
                                    # Use standard OCR processor
                                    reset_ocr_processor()
                                    ocr_processor = get_ocr_processor(suppress_warnings=True)
                                    ocr_results = ocr_processor.process_medical_document(
                                        image_array, 
                                    document_type="auto"
                                )
                            
                                if ocr_results and 'extracted_text' in ocr_results:
                                    medical_text = ocr_results['extracted_text']
                                    confidence = ocr_results.get('confidence', 0)
                                    
                                    # Store in session state for access by summarize button
                                    st.session_state.extracted_text = medical_text
                                    st.session_state.current_ocr_results = ocr_results
                                    st.session_state.last_processed_file_id = file_id  # Mark as processed
                                    
                                    if use_advanced:
                                        st.success("✅ Advanced OCR processing completed!")
                                        
                                        # Show advanced metrics
                                        col1, col2, col3, col4 = st.columns(4)
                                        with col1:
                                            st.metric(" Characters", len(medical_text))
                                        with col2:
                                            st.metric(" Confidence", f"{confidence:.1f}%")
                                        with col3:
                                            quality_score = ocr_results.get('quality_score', 0)
                                            st.metric(" Quality", f"{quality_score:.1f}")
                                        with col4:
                                            word_count = ocr_results.get('word_count', 0)
                                            st.metric(" Words", word_count)
                                    
                                    # Show medical entities if found
                                    entities = ocr_results.get('medical_entities', {})
                                    if entities:
                                        st.subheader("🏥 Medical Entities Detected")
                                        for entity_type, entity_list in entities.items():
                                            if entity_list:
                                                st.write(f"**{entity_type.title()}**: {', '.join([e['text'] for e in entity_list])}")
                                    
                                    # Show processing details
                                    processing_time = ocr_results.get('processing_time_seconds', 0)
                                    st.caption(f" Processing time: {processing_time:.2f}s | "
                                             f"Engines: {', '.join(ocr_results.get('ocr_engines_used', []))}")
                                    
                                else:
                                    st.success("✅ Standard OCR processing completed!")
                                    
                                    # Show standard metrics
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        st.metric("📝 Text Extracted", f"{len(medical_text)} characters")
                                    with col2:
                                        st.metric(" Confidence", f"{confidence:.1f}%")
                                
                                # Display confidence level indicator
                                if confidence >= 80:
                                    st.success("🟢 High confidence OCR results")
                                elif confidence >= 60:
                                    st.warning("🟡 Medium confidence OCR results")
                                else:
                                    st.error("🔴 Low confidence OCR results - please review carefully")
                                
                                # Immediate AI Summarization Option for OCR
                                if len(medical_text.strip()) > 50:
                                    st.divider()
                                    st.subheader("🤖 AI Medical Summarization")
                                    st.info("💡 Generate a professional medical summary of your OCR extracted text")
                                    
                                    # Initialize session state for OCR summary
                                    if 'ocr_immediate_summary' not in st.session_state:
                                        st.session_state.ocr_immediate_summary = None
                                    if 'use_ocr_immediate_summary' not in st.session_state:
                                        st.session_state.use_ocr_immediate_summary = False
                                    if 'ocr_immediate_original_text' not in st.session_state:
                                        st.session_state.ocr_immediate_original_text = medical_text
                                    
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.markdown("**Generate AI Summary:** Creates a structured medical summary with key findings, diagnoses, and recommendations")
                                    with col2:
                                        if st.button("🚀 Generate Summary", type="primary", key="ocr_immediate_summary_btn"):
                                            with st.spinner("🤖 AI is analyzing your OCR text..."):
                                                try:
                                                    current_text = st.session_state.extracted_text or medical_text
                                                    if not current_text or len(current_text.strip()) < 10:
                                                        st.error("❌ No text available to summarize.")
                                                    else:
                                                        summary = summarize_medical_record(current_text, max_length=250, min_length=60)
                                                        st.session_state.ocr_immediate_summary = summary
                                                        st.session_state.ocr_immediate_original_text = current_text
                                                        st.success("✅ Medical summary generated!")
                                                        st.rerun()
                                                except Exception as e:
                                                    st.error(f"❌ Summary generation failed: {str(e)}")
                                    
                                    # Display OCR summary if generated
                                    if st.session_state.ocr_immediate_summary:
                                        st.success("✅ AI Medical Summary Generated")
                                        
                                        # Show formatted summary
                                        st.markdown("### 📋 Professional Medical Summary")
                                        st.markdown(f"""
                                        <div style="
                                            background-color: #f8fffe;
                                            border-left: 4px solid #28a745;
                                            padding: 20px;
                                            border-radius: 8px;
                                            margin: 15px 0;
                                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                        ">
                                            <div style="color: #155724; line-height: 1.8; font-size: 15px; white-space: pre-line;">
                                                {st.session_state.ocr_immediate_summary}
                                            </div>
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                        # Summary stats
                                        col1, col2, col3 = st.columns(3)
                                        with col1:
                                            compression = len(st.session_state.ocr_immediate_summary) / len(st.session_state.ocr_immediate_original_text) * 100
                                            st.metric("📊 Compression", f"{compression:.1f}%")
                                        with col2:
                                            st.metric("📏 Summary Length", f"{len(st.session_state.ocr_immediate_summary)} chars")
                                        with col3:
                                            st.metric("📖 Words", f"{len(st.session_state.ocr_immediate_summary.split())}")
                                        
                                        # Option to use summary
                                        use_summary = st.checkbox(
                                            "✨ Use AI summary as primary record text", 
                                            value=st.session_state.use_ocr_immediate_summary,
                                            key="use_ocr_immediate_summary_checkbox"
                                        )
                                        st.session_state.use_ocr_immediate_summary = use_summary
                                        
                                        if use_summary:
                                            medical_text = st.session_state.ocr_immediate_summary
                                            st.success("✅ AI summary will be saved as the record!")
                                            st.info("💡 Only the professional medical summary will be saved.")
                                        else:
                                            st.info("💡 Original OCR text will be used as primary content.")
                                    
                                else:
                                    st.error("❌ OCR processing failed. Please try again or use text input method.")
                            
                            except Exception as e:
                                st.error(f"❌ OCR error: {str(e)}")
                                st.info("💡 You can still save the image and add text description manually.")
                
                    else:
                        st.warning("⚠️ File type not supported. Please use supported formats.")
                        return
            
            # Show preview of extracted text
            if medical_text and len(medical_text.strip()) > 0:
                with st.expander(" Preview Extracted Text"):
                    # Allow editing of OCR results
                    edited_text = st.text_area(
                        "Review and edit extracted text:",
                        value=medical_text,
                        height=200,
                        help="OCR text may contain errors. Please review and correct if needed."
                    )
                    if edited_text != medical_text:
                        medical_text = edited_text
                        st.session_state.extracted_text = medical_text  # Update session state
                        st.info(" Text has been edited")
                    
                    st.caption(f"Total characters: {len(medical_text)}")
                    
                    # OCR quality information if available
                    if ocr_results:
                        with st.expander("🔍 OCR Analysis Details"):
                            if 'word_count' in ocr_results:
                                st.write(f"**Words detected:** {ocr_results['word_count']}")
                            if 'avg_confidence' in ocr_results:
                                st.write(f"**Average confidence:** {ocr_results['avg_confidence']:.1f}%")
                            if 'engines_used' in ocr_results:
                                st.write(f"**OCR engines:** {', '.join(ocr_results['engines_used'])}")
                
                # AI Summarization Option
                if medical_text and len(medical_text.strip()) > 50:  # Only offer summarization for longer texts
                    st.divider()
                    st.subheader(" AI Medical Summarization (Optional)")
                    
                    # Initialize session state for summary
                    if 'ocr_summary' not in st.session_state:
                        st.session_state.ocr_summary = None
                    if 'use_ocr_summary' not in st.session_state:
                        st.session_state.use_ocr_summary = False
                    if 'ocr_original_text' not in st.session_state:
                        st.session_state.ocr_original_text = medical_text
                    
                    # Update original text if changed
                    if st.session_state.ocr_original_text != medical_text and not st.session_state.use_ocr_summary:
                        st.session_state.ocr_original_text = medical_text
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(" Generate a professional medical summary of your extracted text with proper clinical formatting.")
                    with col2:
                        if st.button(" Generate Medical Summary", type="primary", key="ocr_summary_btn"):
                            with st.spinner(" AI is analyzing your medical text..."):
                                try:
                                    # Get current text from session state to ensure we have the latest version
                                    current_text = st.session_state.extracted_text or medical_text
                                    
                                    if not current_text or len(current_text.strip()) < 10:
                                        st.error(" No text available to summarize. Please extract text first.")
                                        st.rerun()
                                    
                                    # Generate medical summary using specialized function
                                    summary = summarize_medical_record(current_text, max_length=250, min_length=60)
                                    st.session_state.ocr_summary = summary
                                    st.session_state.use_ocr_summary = False  # Reset checkbox
                                    st.session_state.ocr_original_text = current_text  # Store original
                                    st.success(" Medical summary generated successfully!")
                                    st.rerun()  # Refresh to show the summary
                                    
                                except Exception as e:
                                    st.error(f" Medical summary generation failed: {str(e)}")
                                    st.info(" You can still save the original extracted text without summarization.")
                    
                    # Display summary if generated
                    if st.session_state.ocr_summary:
                        st.success("✅ Medical summary generated successfully!")
                        
                        # Display formatted medical summary
                        with st.container():
                            st.markdown("###  Professional Medical Summary")
                            
                            # Create a medical-styled box for the summary
                            st.markdown(f"""
                            <div style="
                                background-color: #f8fffe;
                                border-left: 4px solid #28a745;
                                padding: 20px;
                                border-radius: 8px;
                                margin: 15px 0;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                            ">
                                <div style="color: #155724; line-height: 1.8; font-size: 15px; white-space: pre-line;">
                                    {st.session_state.ocr_summary}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Summary statistics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                compression_ratio = len(st.session_state.ocr_summary) / len(st.session_state.ocr_original_text) * 100
                                st.metric(" Compression", f"{compression_ratio:.1f}%")
                            with col2:
                                st.metric(" Summary Length", f"{len(st.session_state.ocr_summary)} chars")
                            with col3:
                                st.metric(" Summary Words", f"{len(st.session_state.ocr_summary.split())} words")
                            
                            # Option to use summary as medical text with proper state management
                            st.divider()
                            use_summary = st.checkbox(
                                "✨ Use this medical summary as the primary record text",
                                value=st.session_state.use_ocr_summary,
                                key="use_ocr_summary_checkbox"
                            )
                            
                            if use_summary != st.session_state.use_ocr_summary:
                                st.session_state.use_ocr_summary = use_summary
                                if use_summary:
                                    st.success(" Medical summary will be saved as the record!")
                                    st.info("💡 Only the professional medical summary will be saved.")
                                else:
                                    st.info("💡 Original extracted text will be used as primary content.")
                    
                    # Set the final medical_text based on user choice
                    if st.session_state.use_ocr_summary and st.session_state.ocr_summary:
                        medical_text = st.session_state.ocr_summary
        
        # If no file uploaded but we have extracted text in session state, use it
        elif 'extracted_text' in st.session_state and st.session_state.extracted_text:
            medical_text = st.session_state.extracted_text
            st.info("📄 Using previously extracted text from last upload")
    
    else:  # Enter Text Directly
        st.subheader("✍️ Manual Text Entry")
        medical_text = st.text_area(
            "Enter your medical record text:",
            value=st.session_state.extracted_text if 'extracted_text' in st.session_state else "",  # Load from session state
            height=300,
            placeholder="Type or paste your medical record here...\n\nExample:\nPatient Name: John Doe\nDate: 2024-10-03\nChief Complaint: Chest pain\nHistory: 45-year-old male presents with..."
        )
        
        # Update session state when text changes
        if medical_text != st.session_state.extracted_text:
            st.session_state.extracted_text = medical_text
            st.session_state.current_ocr_results = None  # No OCR results for manual text
        
        # Show text statistics
        if medical_text:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(" Characters", len(medical_text))
            with col2:
                st.metric(" Words", len(medical_text.split()))
            with col3:
                st.metric(" Lines", len(medical_text.split('\n')))
            
            # AI Medical Summarization Option for Manual Text
            if len(medical_text.strip()) > 50:  # Only offer summarization for longer texts
                st.divider()
                st.subheader(" AI Medical Summarization (Optional)")
                
                # Initialize session state for manual summary
                if 'manual_summary' not in st.session_state:
                    st.session_state.manual_summary = None
                if 'use_manual_summary' not in st.session_state:
                    st.session_state.use_manual_summary = False
                if 'manual_original_text' not in st.session_state:
                    st.session_state.manual_original_text = medical_text
                
                # Update original text if changed
                if st.session_state.manual_original_text != medical_text and not st.session_state.use_manual_summary:
                    st.session_state.manual_original_text = medical_text
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info(" Generate a professional medical summary of your text with proper clinical formatting and structure.")
                with col2:
                    if st.button(" Generate Medical Summary", type="primary", key="manual_summary_btn"):
                        with st.spinner(" AI is analyzing your medical text..."):
                            try:
                                # Get current text from session state to ensure we have the latest version
                                current_text = st.session_state.extracted_text or medical_text
                                
                                if not current_text or len(current_text.strip()) < 10:
                                    st.error(" No text available to summarize. Please enter some text first.")
                                    st.rerun()
                                
                                # Generate medical summary using specialized function
                                summary = summarize_medical_record(current_text, max_length=250, min_length=60)
                                st.session_state.manual_summary = summary
                                st.session_state.use_manual_summary = False  # Reset checkbox
                                st.session_state.manual_original_text = current_text  # Store original
                                st.success("✅ Medical summary generated successfully!")
                                st.rerun()  # Refresh to show the summary
                                
                            except Exception as e:
                                st.error(f" Medical summary generation failed: {str(e)}")
                                st.info(" You can still save the original text without summarization.")
                
                # Display summary if generated
                if st.session_state.manual_summary:
                    st.success("✅ Medical summary generated successfully!")
                    
                    # Display formatted medical summary
                    with st.container():
                        st.markdown("###  Professional Medical Summary")
                        
                        # Create a medical-styled box for the summary
                        st.markdown(f"""
                        <div style="
                            background-color: #f8fffe;
                            border-left: 4px solid #28a745;
                            padding: 20px;
                            border-radius: 8px;
                            margin: 15px 0;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        ">
                            <div style="color: #155724; line-height: 1.8; font-size: 15px; white-space: pre-line;">
                                {st.session_state.manual_summary}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Summary statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            compression_ratio = len(st.session_state.manual_summary) / len(st.session_state.manual_original_text) * 100
                            st.metric("📊 Compression", f"{compression_ratio:.1f}%")
                        with col2:
                            st.metric("📏 Summary Length", f"{len(st.session_state.manual_summary)} chars")
                        with col3:
                            st.metric("📖 Summary Words", f"{len(st.session_state.manual_summary.split())} words")
                        
                        # Option to use summary as medical text with proper state management
                        st.divider()
                        use_summary = st.checkbox(
                            "✨ Use this medical summary as the primary record text",
                            value=st.session_state.use_manual_summary,
                            key="use_manual_summary_checkbox"
                        )
                        
                        if use_summary != st.session_state.use_manual_summary:
                            st.session_state.use_manual_summary = use_summary
                            if use_summary:
                                st.success(" Medical summary will be saved as the record!")
                                st.info("💡 Only the professional medical summary will be saved.")
                            else:
                                st.info(" Original text will be used as primary content.")
                
                # Set the final medical_text based on user choice
                if st.session_state.use_manual_summary and st.session_state.manual_summary:
                    medical_text = st.session_state.manual_summary
    
    # Additional record information
    if medical_text and len(medical_text.strip()) > 0:
        st.subheader(" Record Information")
        
        col1, col2 = st.columns(2)
        with col1:
            record_title = st.text_input(
                "Record Title",
                placeholder="e.g., Annual Physical Exam, Blood Test Results, X-Ray Report"
            )
            
            record_type = st.selectbox(
                "Record Type",
                ["General Consultation", "Lab Results", "Imaging Report", "Prescription", 
                 "Discharge Summary", "Handwritten Notes", "Medical Certificate", "Other"]
            )
        
        with col2:
            record_date = st.date_input(
                "Record Date",
                value=datetime.now().date(),
                help="Date when this medical record was created"
            )
            
            priority = st.selectbox(
                "Priority Level",
                ["Normal", "High", "Urgent"],
                help="Priority level for this medical record"
            )
        
        # Notes and tags
        additional_notes = st.text_area(
            "Additional Notes (Optional)",
            height=100,
            placeholder="Any additional notes or observations about this record..."
        )
        
        # Save record button
        save_button = st.button("💾 Save Medical Record", type="primary")
        
        if save_button:
            if not record_title.strip():
                st.error(" Please provide a record title")
                return
            
            try:
                # Prepare record data
                record_data = {
                    "title": record_title.strip(),
                    "content": medical_text.strip(),
                    "record_type": record_type,
                    "record_date": record_date.isoformat(),
                    "priority": priority,
                    "additional_notes": additional_notes.strip() if additional_notes else "",
                    "patient_id": current_user["id"],
                    "created_at": datetime.now().isoformat(),
                    "file_info": {
                        "original_filename": file_name,
                        "file_type": file_type,
                        "file_size": file_size
                    } if file_name else None,
                    "ocr_info": ocr_results if ocr_results else None
                }
                
                # Save to database
                with st.spinner("💾 Saving record to database..."):
                    result = save_medical_record(record_data)
                    
                    if result:
                        st.success("✅ Medical record saved successfully!")
                        
                        # Also save file to MongoDB storage if it's an uploaded file
                        if uploaded_file is not None:
                            try:
                                uploaded_file.seek(0)
                                file_data = uploaded_file.read()
                                
                                storage = init_mongodb_storage()
                                storage_result = storage.store_patient_file(
                                    file_data=file_data,
                                    filename=file_name,
                                    patient_id=current_user["id"],
                                    file_type="medical_document",
                                    metadata={
                                        "record_title": record_title,
                                        "record_type": record_type,
                                        "record_date": record_date.isoformat(),
                                        "has_ocr": bool(ocr_results),
                                        "ocr_confidence": ocr_results.get('avg_confidence', 0) if ocr_results else 0
                                    }
                                )
                                
                                if storage_result.get("success"):
                                    st.success(" File stored in database successfully!")
                                else:
                                    st.warning(" Record saved but file storage failed")
                                    
                            except Exception as e:
                                logger.error(f"File storage error: {e}")
                                st.warning(" Record saved but file storage failed")
                        
                        # Show summary
                        with st.expander("📋 Saved Record Summary"):
                            st.write(f"**Title:** {record_title}")
                            st.write(f"**Type:** {record_type}")
                            st.write(f"**Date:** {record_date}")
                            st.write(f"**Content:** {len(medical_text)} characters")
                            if file_name:
                                st.write(f"**File:** {file_name}")
                            if ocr_results:
                                st.write(f"**OCR Confidence:** {ocr_results.get('avg_confidence', 0):.1f}%")
                            
                            # Show if summary was used
                            if st.session_state.get('use_ocr_summary') or st.session_state.get('use_manual_summary'):
                                st.success("✅ Record saved with AI medical summary included")
                            else:
                                st.info(" Record saved with original text")
                        
                        # Clear summarization session state for next record
                        clear_summarization_state()
                        
                        # Clear form
                        st.rerun()
                        
                    else:
                        st.error(" Failed to save medical record")
                        
            except Exception as e:
                logger.error(f"Error saving record: {e}")
                st.error(f" Error saving record: {str(e)}")
    
    else:
        st.info("📝 Please upload a file or enter text to create a medical record.")

def display_medical_records():
    """Display patient's medical records"""
    st.header("📋 My Medical Records")
    
    # Get current user
    current_user = get_current_user()
    if not current_user:
        st.error("Failed to load user data")
        return
    
    # Load records
    with st.spinner("📖 Loading your medical records..."):
        records = get_patient_records(current_user["id"])
    
    if not records:
        st.info("📭 No medical records found. Upload your first record to get started!")
        return
    
    # Display statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Total Records", len(records))
    with col2:
        # Calculate recent records with proper date handling
        recent_records = []
        for r in records:
            try:
                created_at = r.get('created_at', '2024-01-01')
                
                # Handle different date formats safely
                record_date = None
                
                if isinstance(created_at, str) and created_at:
                    # Extract just the date part for comparison
                    date_part = created_at[:10]  # Get YYYY-MM-DD part
                    if len(date_part) == 10 and date_part.count('-') == 2:
                        record_date = datetime.strptime(date_part, '%Y-%m-%d')
                elif hasattr(created_at, 'year'):  # datetime object
                    # Remove timezone info if present
                    record_date = created_at.replace(tzinfo=None) if hasattr(created_at, 'tzinfo') and created_at.tzinfo else created_at
                
                # Default fallback
                if record_date is None:
                    record_date = datetime(2024, 1, 1)
                
                # Check if within last 30 days
                if (datetime.now() - record_date).days <= 30:
                    recent_records.append(r)
                    
            except (ValueError, TypeError, AttributeError):
                # Skip records with invalid dates
                continue
        
        st.metric(" This Month", len(recent_records))
    with col3:
        ocr_records = [r for r in records if r.get('ocr_info')]
        st.metric("🔍 OCR Processed", len(ocr_records))
    
    # Search and filter
    col1, col2 = st.columns(2)
    with col1:
        search_query = st.text_input("🔍 Search records", placeholder="Search by title, content, or type...")
    with col2:
        record_type_filter = st.selectbox("Filter by type", 
                                        ["All"] + ["General Consultation", "Lab Results", "Imaging Report", 
                                                  "Prescription", "Discharge Summary", "Handwritten Notes", 
                                                  "Medical Certificate", "Other"])
    
    # Filter records
    filtered_records = records
    if search_query:
        filtered_records = [r for r in filtered_records if 
                          search_query.lower() in r.get('title', '').lower() or
                          search_query.lower() in r.get('content', '').lower() or
                          search_query.lower() in r.get('record_type', '').lower()]
    
    if record_type_filter != "All":
        filtered_records = [r for r in filtered_records if r.get('record_type') == record_type_filter]
    
    # Display records
    if not filtered_records:
        st.warning("No records match your search criteria.")
        return
    
    for i, record in enumerate(filtered_records):
        # Generate better display title and date
        display_title = record.get('title') or f"Medical Record #{i+1}"
        
        # Handle record_date with better formatting
        record_date = record.get('record_date')
        if not record_date:
            # Use created_at as fallback
            created_at = record.get('created_at', '')
            if isinstance(created_at, str) and len(created_at) >= 10:
                record_date = created_at[:10]
            elif hasattr(created_at, 'strftime'):
                record_date = created_at.strftime('%Y-%m-%d')
            else:
                record_date = 'Unknown Date'
        
        # Format date nicely for display
        try:
            if record_date and record_date != 'Unknown Date':
                date_obj = datetime.strptime(record_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%B %d, %Y')  # e.g., "October 04, 2025"
            else:
                formatted_date = record_date
        except:
            formatted_date = record_date
        
        # Truncate title if too long for better display
        if len(display_title) > 50:
            display_title = display_title[:47] + "..."
        
        with st.expander(f"📄 {display_title} - {formatted_date}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.write(f"**Type:** {record.get('record_type', 'Unknown')}")
                
                # Display record date with fallback and nice formatting
                display_record_date = record.get('record_date')
                if not display_record_date:
                    created_at = record.get('created_at', '')
                    if isinstance(created_at, str) and len(created_at) >= 10:
                        display_record_date = created_at[:10]
                    elif hasattr(created_at, 'strftime'):
                        display_record_date = created_at.strftime('%Y-%m-%d')
                    else:
                        display_record_date = 'Unknown'
                
                # Format the date nicely
                try:
                    if display_record_date and display_record_date != 'Unknown':
                        date_obj = datetime.strptime(display_record_date, '%Y-%m-%d')
                        formatted_record_date = date_obj.strftime('%B %d, %Y')
                    else:
                        formatted_record_date = display_record_date
                except:
                    formatted_record_date = display_record_date
                
                st.write(f"**Date:** {formatted_record_date}")
                
                if record.get('priority') != 'Normal':
                    st.write(f"**Priority:** {record.get('priority', 'Normal')}")
                
                # Show content
                content = record.get('content', '')
                if len(content) > 300:
                    st.write(f"**Content:** {content[:300]}...")
                    with st.expander("Show full content"):
                        st.text(content)
                else:
                    st.write(f"**Content:** {content}")
                
                # OCR information
                if record.get('ocr_info'):
                    ocr_info = record['ocr_info']
                    st.info(f"🔍 OCR Processed - Confidence: {ocr_info.get('avg_confidence', 0):.1f}%")
                
                # Additional notes
                if record.get('additional_notes'):
                    st.write(f"**Notes:** {record['additional_notes']}")
            
            with col2:
                # Safe date formatting for created date
                created_at = record.get('created_at', 'Unknown')
                if isinstance(created_at, str) and len(created_at) >= 10:
                    try:
                        # Try to parse and format nicely
                        date_part = created_at[:10]
                        date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                        display_date = date_obj.strftime('%b %d, %Y')  # e.g., "Oct 04, 2025"
                    except:
                        display_date = created_at[:10]
                elif hasattr(created_at, 'strftime'):  # datetime object
                    display_date = created_at.strftime('%b %d, %Y')
                else:
                    display_date = 'Unknown'
                
                st.write(f"**Created:** {display_date}")
                
                # Actions
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f" Export PDF", key=f"export_{i}", type="primary"):
                        # Generate single record PDF
                        with st.spinner("📄 Generating PDF..."):
                            pdf_data = generate_single_record_pdf(record, current_user)
                            if pdf_data:
                                st.success("✅ PDF generated!")
                                # Create safe filename
                                safe_title = "".join(c for c in record.get('title', 'Record') if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                safe_title = safe_title[:30]  # Limit length
                                filename = f"medical_record_{safe_title}_{datetime.now().strftime('%Y%m%d')}.pdf"
                                st.download_button(
                                    label="📥 Download PDF",
                                    data=pdf_data,
                                    file_name=filename,
                                    mime="application/pdf",
                                    key=f"download_{i}"
                                )
                            else:
                                st.error(" Failed to generate PDF")
                
                with col_b:
                    if st.button(f"🗑️ Delete", key=f"delete_{i}"):
                        # Fixed: Added user_id parameter as required by delete_record function
                        if delete_record(record.get('_id'), current_user["id"]):
                            st.success("Record deleted!")
                            st.rerun()
                        else:
                            st.error("Failed to delete record")

def generate_single_record_pdf(record, user_info):
    """Generate a PDF report for a single medical record with full content visibility"""
    if not PDF_AVAILABLE:
        return None
    
    try:
        # Create a BytesIO buffer for the PDF
        buffer = io.BytesIO()
        
        # Create the PDF document with more space for content
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=50, leftMargin=50,
                               topMargin=50, bottomMargin=50)
        
        # Container for the 'Flowable' objects
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles for single record
        title_style = ParagraphStyle(
            'RecordTitle',
            parent=styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2c3e50')
        )
        
        header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=colors.HexColor('#3498db'),
            borderWidth=1,
            borderColor=colors.HexColor('#3498db'),
            borderPadding=5
        )
        
        body_style = ParagraphStyle(
            'RecordBody',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            leftIndent=10,
            rightIndent=10,
            leading=14
        )
        
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=4,
            leftIndent=15,
            textColor=colors.HexColor('#7f8c8d')
        )
        
        # Title
        record_title = record.get('title', 'Medical Record')
        story.append(Paragraph(f" {record_title}", title_style))
        story.append(Spacer(1, 20))
        
        # Patient Information Header
        story.append(Paragraph("👤 Patient Information", header_style))
        
        patient_data = [
            ['Patient Name:', user_info.get('full_name', user_info.get('username', 'Unknown'))],
            ['Username:', user_info.get('username', 'Unknown')],
            ['Report Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')]
        ]
        
        patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
        patient_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(patient_table)
        story.append(Spacer(1, 20))
        
        # Record Details
        story.append(Paragraph(" Record Details", header_style))
        
        # Format dates safely
        record_date = record.get('record_date', 'Unknown')
        if isinstance(record_date, str) and len(record_date) >= 10:
            display_date = record_date[:10]
        elif hasattr(record_date, 'strftime'):
            display_date = record_date.strftime('%Y-%m-%d')
        else:
            display_date = 'Unknown'
        
        created_at = record.get('created_at', 'Unknown')
        if isinstance(created_at, str) and len(created_at) >= 10:
            created_date = created_at[:10]
        elif hasattr(created_at, 'strftime'):
            created_date = created_at.strftime('%Y-%m-%d')
        else:
            created_date = 'Unknown'
        
        record_details = [
            ['Record Type:', record.get('record_type', 'Unknown')],
            ['Record Date:', display_date],
            ['Created Date:', created_date],
            ['Priority:', record.get('priority', 'Normal')],
            ['Status:', 'Active']
        ]
        
        details_table = Table(record_details, colWidths=[2*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ecf0f1')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(details_table)
        story.append(Spacer(1, 20))
        
        # OCR Information (if available)
        if record.get('ocr_info'):
            story.append(Paragraph(" OCR Processing Information", header_style))
            ocr_info = record['ocr_info']
            ocr_details = [
                ['OCR Confidence:', f"{ocr_info.get('avg_confidence', ocr_info.get('confidence', 0)):.1f}%"],
                ['Processing Engine:', ocr_info.get('engine', 'Unknown')],
                ['Processing Date:', created_date]
            ]
            
            ocr_table = Table(ocr_details, colWidths=[2*inch, 4*inch])
            ocr_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ecf0f1')),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4fd')),
                ('PADDING', (0, 0), (-1, -1), 8),
            ]))
            
            story.append(ocr_table)
            story.append(Spacer(1, 20))
        
        # Medical Content - FULL CONTENT WITHOUT TRUNCATION
        story.append(Paragraph(" Complete Medical Content", header_style))
        
        medical_text = record.get('content', record.get('medical_text', 'No content available'))
        
        # NO truncation - show complete content
        if medical_text and medical_text.strip():
            # Clean the text for PDF generation
            cleaned_text = clean_text_for_pdf(medical_text)
            
            # Split into manageable paragraphs for better formatting
            paragraphs = cleaned_text.split('\n\n')
            if not paragraphs or len(paragraphs) == 1:
                # If no double line breaks, split on single line breaks
                paragraphs = cleaned_text.split('\n')
            
            for para in paragraphs:
                if para.strip():
                    try:
                        # Handle very long single paragraphs by adding word wrapping
                        if len(para) > 1000:
                            # Split long paragraphs into smaller chunks for better formatting
                            words = para.split()
                            chunk_size = 150  # words per chunk
                            for i in range(0, len(words), chunk_size):
                                chunk = ' '.join(words[i:i + chunk_size])
                                try:
                                    story.append(Paragraph(chunk, body_style))
                                except Exception as chunk_e:
                                    logger.warning(f"Failed to create paragraph chunk, using fallback: {chunk_e}")
                                    # Fallback: add as plain text with minimal formatting
                                    story.append(Paragraph(f"[Content]: {chunk[:500]}...", body_style))
                        else:
                            story.append(Paragraph(para.strip(), body_style))
                    except Exception as para_e:
                        logger.warning(f"Failed to create paragraph, using fallback: {para_e}")
                        # Fallback: add as plain text
                        safe_text = para.strip()[:500] + "..." if len(para.strip()) > 500 else para.strip()
                        story.append(Paragraph(f"[Content]: {safe_text}", body_style))
        else:
            story.append(Paragraph("No medical content available for this record.", info_style))
        
        story.append(Spacer(1, 20))
        
        # Additional Notes (if available)
        if record.get('additional_notes'):
            story.append(Paragraph(" Additional Notes", header_style))
            try:
                notes = clean_text_for_pdf(record['additional_notes'])
                story.append(Paragraph(notes, body_style))
            except Exception as notes_e:
                logger.warning(f"Failed to create notes paragraph, using fallback: {notes_e}")
                safe_notes = str(record['additional_notes'])[:500] + "..." if len(str(record['additional_notes'])) > 500 else str(record['additional_notes'])
                story.append(Paragraph(f"[Notes]: {safe_notes}", body_style))
            story.append(Spacer(1, 20))
        
        # Footer
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7f8c8d')
        )
        
        story.append(Paragraph("─" * 50, footer_style))
        story.append(Paragraph("This medical record was exported from EHR Web Application", footer_style))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
        story.append(Paragraph("This document contains complete medical information without truncation", footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Get the value of the BytesIO buffer and return it
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logger.error(f"Single record PDF generation error: {e}")
        return None

def generate_pdf_report(records, user_info):
    """Generate a professional PDF report of medical records"""
    if not PDF_AVAILABLE:
        return None
    
    try:
        # Create a BytesIO buffer for the PDF
        buffer = io.BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        # Container for the 'Flowable' objects
        story = []
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1f77b4')
        )
        
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#2c3e50')
        )
        
        record_title_style = ParagraphStyle(
            'RecordTitle',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=6,
            spaceBefore=15,
            textColor=colors.HexColor('#e74c3c')
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leftIndent=20
        )
        
        # Title
        story.append(Paragraph(" Medical Records Report", title_style))
        story.append(Spacer(1, 20))
        
        # Patient Information
        story.append(Paragraph(" Patient Information", header_style))
        
        patient_data = [
            ['Patient Name:', user_info.get('full_name', user_info.get('username', 'Unknown'))],
            ['Username:', user_info.get('username', 'Unknown')],
            ['User ID:', str(user_info.get('id', 'Unknown'))],
            ['Report Generated:', datetime.now().strftime('%B %d, %Y at %I:%M %p')],
            ['Total Records:', str(len(records))]
        ]
        
        patient_table = Table(patient_data, colWidths=[2*inch, 4*inch])
        patient_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(patient_table)
        story.append(Spacer(1, 30))
        
        # Records Summary
        story.append(Paragraph(" Records Summary", header_style))
        
        # Group records by type
        record_types = {}
        for record in records:
            record_type = record.get('record_type', 'Unknown')
            if record_type not in record_types:
                record_types[record_type] = 0
            record_types[record_type] += 1
        
        summary_data = [['Record Type', 'Count']]
        for record_type, count in record_types.items():
            summary_data.append([record_type, str(count)])
        
        summary_table = Table(summary_data, colWidths=[3*inch, 1*inch])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 30))
        
        # Individual Records
        story.append(Paragraph(" Detailed Medical Records", header_style))
        
        for i, record in enumerate(records, 1):
            # Record header
            record_title = record.get('record_title', f'Medical Record {i}')
            story.append(Paragraph(f"{i}. {record_title}", record_title_style))
            
            # Record details table
            record_date = record.get('record_date', 'Unknown')
            if isinstance(record_date, str) and len(record_date) >= 10:
                display_date = record_date[:10]
            elif hasattr(record_date, 'strftime'):
                display_date = record_date.strftime('%Y-%m-%d')
            else:
                display_date = 'Unknown'
            
            created_at = record.get('created_at', 'Unknown')
            if isinstance(created_at, str) and len(created_at) >= 10:
                created_date = created_at[:10]
            elif hasattr(created_at, 'strftime'):
                created_date = created_at.strftime('%Y-%m-%d')
            else:
                created_date = 'Unknown'
            
            record_details = [
                ['Type:', record.get('record_type', 'Unknown')],
                ['Date:', display_date],
                ['Created:', created_date],
                ['Priority:', record.get('priority', 'Normal')]
            ]
            
            details_table = Table(record_details, colWidths=[1.5*inch, 4.5*inch])
            details_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#ecf0f1')),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8f9fa')),
                ('PADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(details_table)
            story.append(Spacer(1, 10))
            
            # Medical content - SHOW COMPLETE CONTENT WITHOUT TRUNCATION
            medical_text = record.get('medical_text', record.get('content', 'No content available'))
            
            story.append(Paragraph("<b>Complete Medical Content:</b>", body_style))
            
            # NO truncation - show complete content with better formatting
            if medical_text and medical_text.strip():
                # Clean the text for PDF generation
                cleaned_text = clean_text_for_pdf(medical_text)
                
                # Split into manageable paragraphs for better formatting
                paragraphs = cleaned_text.split('\n\n')
                if not paragraphs or len(paragraphs) == 1:
                    # If no double line breaks, split on single line breaks
                    paragraphs = cleaned_text.split('\n')
                
                for para in paragraphs:
                    if para.strip():
                        try:
                            # Handle very long single paragraphs by adding word wrapping
                            if len(para) > 1000:
                                # Split long paragraphs into smaller chunks for better formatting
                                words = para.split()
                                chunk_size = 150  # words per chunk
                                for j in range(0, len(words), chunk_size):
                                    chunk = ' '.join(words[j:j + chunk_size])
                                    try:
                                        story.append(Paragraph(chunk, body_style))
                                    except Exception as chunk_e:
                                        logger.warning(f"Failed to create paragraph chunk, using fallback: {chunk_e}")
                                        # Fallback: add as plain text with minimal formatting
                                        story.append(Paragraph(f"[Content]: {chunk[:500]}...", body_style))
                            else:
                                story.append(Paragraph(para.strip(), body_style))
                        except Exception as para_e:
                            logger.warning(f"Failed to create paragraph, using fallback: {para_e}")
                            # Fallback: add as plain text
                            safe_text = para.strip()[:500] + "..." if len(para.strip()) > 500 else para.strip()
                            story.append(Paragraph(f"[Content]: {safe_text}", body_style))
            else:
                story.append(Paragraph("No medical content available for this record.", body_style))
            
            story.append(Spacer(1, 20))
            
            # Add page break between records (except for last record)
            if i < len(records):
                story.append(Spacer(1, 20))
        
        # Footer
        story.append(Spacer(1, 30))
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7f8c8d')
        )
        story.append(Paragraph("This report was generated automatically by the EHR Web Application", footer_style))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Get the value of the BytesIO buffer and return it
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None

def export_records():
    """Export patient records with PDF support"""
    st.header("📥 Export My Data")
    
    current_user = get_current_user()
    if not current_user:
        st.error("Failed to load user data")
        return
    
    records = get_patient_records(current_user["id"])
    
    if not records:
        st.info(" No records to export.")
        return
    
    st.write(f" **Total Records:** {len(records)}")
    
    # Export format selection
    export_formats = ["PDF Report (Recommended)", "JSON", "CSV"]
    if not PDF_AVAILABLE:
        export_formats = ["JSON", "CSV"]
        st.warning(" PDF export not available. Please install reportlab library.")
    
    export_format = st.selectbox("Choose export format:", export_formats)
    
    # Show preview of what will be exported
    with st.expander(" Preview Export Content"):
        if export_format.startswith("PDF"):
            st.info(" **PDF Report will include:**")
            st.write("• Professional header with patient information")
            st.write("• Summary table of record types and counts") 
            st.write("• Detailed view of each medical record")
            st.write("• Formatted medical content with proper styling")
            st.write("• Generated date and footer information")
        else:
            st.info(f" **{export_format} export will include:**")
            st.write("• All medical record data in structured format")
            st.write("• Record metadata (dates, types, priorities)")
            st.write("• Complete medical text content")
    
    # Export button with different styling for PDF
    button_label = "📄 Generate PDF Report" if export_format.startswith("PDF") else f"📥 Export {export_format}"
    button_type = "primary" if export_format.startswith("PDF") else "secondary"
    
    if st.button(button_label, type=button_type):
        try:
            with st.spinner(f" Generating {export_format} export..."):
                
                if export_format.startswith("PDF"):
                    # Generate PDF report
                    pdf_data = generate_pdf_report(records, current_user)
                    
                    if pdf_data:
                        st.success("✅ PDF report generated successfully!")
                        
                        # Show PDF statistics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(" Pages", "Multi-page")
                        with col2:
                            st.metric(" Records", len(records))
                        with col3:
                            st.metric(" Size", f"{len(pdf_data) // 1024} KB")
                        
                        # Download button for PDF
                        st.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_data,
                            file_name=f"medical_records_{current_user['username']}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            type="primary"
                        )
                        
                        st.info(" **Tip:** The PDF includes all your medical records in a professional format suitable for sharing with healthcare providers.")
                        
                    else:
                        st.error(" Failed to generate PDF report")
                        st.info(" Try using JSON or CSV export instead.")
                
                elif export_format == "JSON":
                    data = export_patient_records(current_user["id"], "json")
                    st.success("✅ JSON export ready!")
                    st.download_button(
                        label="📥 Download JSON",
                        data=data,
                        file_name=f"medical_records_{current_user['username']}_{datetime.now().strftime('%Y%m%d')}.json",
                        mime="application/json"
                    )
                    
                else:  # CSV
                    data = export_patient_records(current_user["id"], "csv")
                    st.success("✅ CSV export ready!")
                    st.download_button(
                        label="📥 Download CSV",
                        data=data,
                        file_name=f"medical_records_{current_user['username']}_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                    
        except Exception as e:
            st.error(f" Export failed: {str(e)}")
            logger.error(f"Export error: {e}")
            st.info(" Please try again or contact support if the problem persists.")

def show_sample_templates():
    """Show sample templates for medical records"""
    st.header("📝 Medical Record Templates")
    st.write("Use these professional templates as a guide for creating your medical records.")
    
    # Template categories
    template_categories = {
        "🏥 Clinical Visit Templates": {
            "General Consultation": """
**Chief Complaint:** [Describe the main reason for visit]

**History of Present Illness:**
- Onset: [When did symptoms start?]
- Duration: [How long have symptoms persisted?]
- Quality: [Describe the nature of symptoms]
- Severity: [Rate severity 1-10]
- Associated symptoms: [Any related symptoms?]

**Past Medical History:**
- Previous illnesses: [List any chronic conditions]
- Medications: [Current medications and dosages]
- Allergies: [Drug or environmental allergies]

**Physical Examination:**
- Vital Signs: BP, HR, RR, Temp, O2 Sat
- General Appearance: [Overall patient condition]
- System-specific findings: [Relevant physical findings]

**Assessment and Plan:**
- Primary Diagnosis: [Working diagnosis]
- Treatment Plan: [Medications, procedures, follow-up]
- Patient Education: [Instructions given to patient]
- Follow-up: [When to return or follow-up required]
            """,
            "Follow-up Visit": """
**Follow-up for:** [Condition being followed]

**Interval History:**
- Since last visit: [Changes since last appointment]
- Medication compliance: [Is patient taking medications as prescribed?]
- Symptom progression: [Better, worse, or stable?]
- New concerns: [Any new symptoms or issues?]

**Current Medications:**
- [List current medications with dosages]
- [Note any changes or side effects]

**Physical Examination:**
- Vital Signs: [Current vital signs]
- Focused exam: [Examination relevant to condition]
- Comparison to previous: [How does exam compare to last visit?]

**Assessment:**
- Current status: [Stable, improved, or worsened]
- Treatment response: [How well is current treatment working?]

**Plan:**
- Continue current treatment: [Yes/No with modifications]
- New interventions: [Any new treatments or tests needed]
- Next follow-up: [When to return]
            """
        },
        "🧪 Laboratory & Diagnostic Templates": {
            "Lab Results Review": """
**Laboratory Results Review**

**Test Date:** [Date of laboratory work]
**Ordering Provider:** [Name of provider who ordered tests]

**Complete Blood Count (CBC):**
- WBC: [Value] (Normal: 4.5-11.0 K/uL)
- RBC: [Value] (Normal: 4.2-5.8 M/uL)
- Hemoglobin: [Value] (Normal: 12-16 g/dL)
- Hematocrit: [Value] (Normal: 36-48%)
- Platelets: [Value] (Normal: 150-450 K/uL)

**Basic Metabolic Panel (BMP):**
- Glucose: [Value] (Normal: 70-100 mg/dL)
- BUN: [Value] (Normal: 7-20 mg/dL)
- Creatinine: [Value] (Normal: 0.6-1.2 mg/dL)
- Sodium: [Value] (Normal: 136-145 mEq/L)
- Potassium: [Value] (Normal: 3.5-5.0 mEq/L)

**Clinical Interpretation:**
- [Interpretation of abnormal values]
- [Clinical significance]
- [Recommended follow-up or treatment modifications]
            """,
            "Imaging Report": """
**Imaging Study:** [Type of imaging - X-ray, CT, MRI, etc.]
**Study Date:** [Date of imaging]
**Clinical Indication:** [Reason for imaging]

**Technique:**
- [Technical parameters of the study]
- [Contrast used, if any]

**Findings:**
- [Detailed description of findings]
- [Normal and abnormal findings]
- [Comparison to previous studies if available]

**Impression:**
- [Primary finding or diagnosis]
- [Secondary findings]
- [Recommendations for follow-up or additional imaging]

**Clinical Correlation:**
- [How findings relate to patient's symptoms]
- [Recommendations for treatment or further evaluation]
            """
        },
        "💊 Prescription & Treatment Templates": {
            "Prescription Record": """
**Prescription Information**

**Patient:** [Patient name and DOB for verification]
**Date:** [Date of prescription]
**Prescribing Provider:** [Doctor name and credentials]

**Medication Details:**
- Drug Name: [Generic and brand name]
- Strength: [Dosage strength]
- Quantity: [Number of pills/amount]
- Directions: [How to take - frequency, timing, with/without food]
- Refills: [Number of refills authorized]

**Indication:** [Condition being treated]

**Patient Instructions:**
- [Special instructions for taking medication]
- [Common side effects to monitor]
- [When to contact provider]
- [Follow-up requirements]

**Drug Interactions Checked:** [Yes/No]
**Allergy Check Completed:** [Yes/No]
            """,
            "Treatment Plan": """
**Treatment Plan**

**Primary Diagnosis:** [Main condition being treated]
**Secondary Diagnoses:** [Other relevant conditions]

**Goals of Treatment:**
1. [Primary treatment goal]
2. [Secondary goals]
3. [Long-term objectives]

**Treatment Interventions:**

**Medications:**
- [Medication 1]: [Dosage and instructions]
- [Medication 2]: [Dosage and instructions]

**Non-Pharmacological Interventions:**
- [Physical therapy, lifestyle changes, etc.]
- [Dietary modifications]
- [Exercise recommendations]

**Monitoring Plan:**
- [What parameters to monitor]
- [Frequency of monitoring]
- [Target values or goals]

**Follow-up Schedule:**
- Next appointment: [Date and purpose]
- Long-term follow-up: [Frequency and requirements]

**Patient Education Provided:**
- [Topics discussed with patient]
- [Materials provided]
- [Patient's understanding confirmed]
            """
        }
    }
    
    # Display templates by category
    for category, templates in template_categories.items():
        with st.expander(category):
            for template_name, template_content in templates.items():
                st.subheader(f" {template_name}")
                
                # Display template with copy functionality
                st.code(template_content, language="text")
                
                # Copy to clipboard functionality
                if st.button(f" Copy {template_name} Template", key=f"copy_{template_name}"):
                    st.session_state.clipboard_content = template_content
                    st.success(f" {template_name} template copied! Go to Upload Record tab and paste it in the text area.")
    
    # Additional template features
    st.divider()
    
    # Quick template guide
    with st.expander(" How to Use Templates"):
        st.write("""
        **Using Medical Record Templates:**
        
        1. **Choose a Template**: Select the template that best matches your medical record type
        2. **Copy Template**: Click the "Copy Template" button
        3. **Navigate to Upload**: Go to the "Upload Record" tab
        4. **Paste and Fill**: Paste the template in the text area and fill in your specific information
        5. **Save Record**: Complete the form and save your medical record
        
        **Template Benefits:**
        - **Professional Format**: Industry-standard medical documentation format
        - **Complete Information**: Ensures all important details are included
        - **Consistency**: Standardized format across all your records
        - **Medical Accuracy**: Templates follow medical documentation best practices
        
        **Customization Tips:**
        - Replace placeholder text [in brackets] with your specific information
        - Add or remove sections as needed for your specific case
        - Include dates, times, and specific measurements when available
        - Use medical terminology appropriately
        """)
    
    # Template statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(" Available Templates", "8")
    with col2:
        st.metric(" Categories", "3")
    with col3:
        st.metric(" Success Rate", "95%")

def manage_health_card():
    """Integrated health card management for patients"""
    st.header("🏥 Your Digital Health Card")
    st.write("Manage your secure digital health card with QR code for quick medical access.")
    
    # Get current user
    current_user = get_current_user()
    if not current_user:
        st.error("Unable to load user information")
        return
    
    # Debug: check what fields are available in current_user
    # st.write("Debug - Current user keys:", list(current_user.keys()))
    
    # Initialize health card generator
    card_generator = HealthCardGenerator()
    
    # Check if user already has a health card
    # Use 'id' field, not '_id' (see authenticate_user function in utils/auth.py)
    user_id = current_user.get('id')
    if not user_id:
        st.error(" User ID not found in session. Please logout and login again.")
        return
    
    existing_card = card_generator.get_patient_health_card(str(user_id))
    
    if existing_card:
        # Display existing health card
        st.success("✅ You already have a digital health card!")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📋 Your Health Card Details")
            
            # existing_card is the health card document itself, not nested
            health_card = existing_card
            
            # Display card information in a nice format
            card_info = f"""
            **🆔 Health Card ID:** `{health_card['health_card_id']}`
            **👤 Name:** {health_card['patient_name']}
            **📅 Date of Birth:** {health_card['date_of_birth']}
            **📍 Address:** {health_card['address']}
            **📱 Mobile:** {health_card['mobile_number']}
            **📅 Card Generated:** {health_card['created_at'][:10] if isinstance(health_card['created_at'], str) else health_card['created_at'].strftime('%Y-%m-%d')}
            **⏰ Valid Until:** {health_card.get('validity_date', 'Lifetime')}
            """
            
            st.markdown(card_info)
            
            # QR Code section
            st.subheader("📱 QR Code")
            st.write("This QR code contains your encrypted health information for quick access by healthcare providers.")
            
            try:
                # Generate and display QR code
                # Prepare health card data for QR code generation
                qr_patient_data = {
                    "health_card_id": health_card['health_card_id'],
                    "full_name": health_card['patient_name'],
                    "patient_name": health_card['patient_name'],
                    "date_of_birth": health_card['date_of_birth'],
                    "mobile_number": health_card['mobile_number'],
                    "emergency_contact": health_card.get('emergency_contact', ''),
                    "blood_group": health_card.get('blood_group', '')
                }
                
                qr_img, qr_data = card_generator.generate_qr_code(qr_patient_data)
                if qr_img:
                    # Convert PIL Image to bytes for Streamlit compatibility
                    img_buffer = io.BytesIO()
                    qr_img.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    st.image(img_buffer, caption="Your Health Card QR Code", width=200)
                    
                    # Show QR code instructions
                    st.info(" **How to use this QR code:**\n- Healthcare providers can scan this code\n- Provides instant access to your health information\n- Requires OTP verification for security")
                else:
                    st.warning("Unable to generate QR code display")
            except Exception as e:
                st.error(f"Error displaying QR code: {str(e)}")
                st.info(" **Troubleshooting:** Please refresh the page or contact support if the issue persists.")
        
        with col2:
            st.subheader(" Card Actions")
            
            # Download health card
            if st.button("📥 Download Health Card", type="primary"):
                try:
                    # Prepare patient data dictionary for create_health_card method
                    patient_data = {
                        "patient_name": health_card['patient_name'],
                        "full_name": health_card['patient_name'],
                        "date_of_birth": health_card['date_of_birth'],
                        "address": health_card['address'],
                        "mobile_number": health_card['mobile_number'],
                        "health_card_id": health_card['health_card_id'],
                        "emergency_contact": health_card.get('emergency_contact', ''),
                        "blood_group": health_card.get('blood_group', ''),
                        "profile_photo_data": health_card.get('profile_photo_data', None)  # Include stored photo
                    }
                    
                    card_image, qr_data = card_generator.create_health_card(patient_data)
                    
                    if card_image:
                        # Convert PIL image to bytes
                        img_buffer = io.BytesIO()
                        card_image.save(img_buffer, format='PNG', quality=95)
                        img_buffer.seek(0)
                        
                        st.download_button(
                            label="💾 Download PNG",
                            data=img_buffer.getvalue(),
                            file_name=f"health_card_{health_card['health_card_id']}.png",
                            mime="image/png"
                        )
                        st.success("✅ Health card ready for download!")
                    else:
                        st.error("Unable to generate health card image")
                except Exception as e:
                    st.error(f"Error generating health card: {str(e)}")
            
        
            # Update information button
            if st.button("✏️ Update Information"):
                st.session_state.update_health_card = True
                st.rerun()
        
        # Card usage instructions
        st.divider()
        st.subheader(" How to Use Your Health Card")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("""
            **🏥 At Medical Facilities**
            - Show QR code to healthcare providers
            - Instant access to your medical records
            - No manual data entry required
            """)
        
        with col2:
            st.write("""
            **📱 QR Code Features**
            - Encrypted patient information
            - OTP verification for security
            - Quick medical history access
            """)
        
        with col3:
            st.write("""
            **🔒 Security Features**
            - Unique encrypted health ID
            - OTP verification required
            - Secure data transmission
            """)
        
    else:
        # Show health card generation form
        st.info(" You don't have a health card yet. Let's create one for you!")
        
        # Health card generation form
        with st.form("health_card_form"):
            st.subheader(" Health Card Information")
            
            col1, col2 = st.columns(2)
            
            with col1:
                patient_name = st.text_input(
                    "Full Name*", 
                    value=current_user.get('username', ''),
                    placeholder="Enter your full legal name"
                )
                
                date_of_birth = st.date_input(
                    "Date of Birth*",
                    min_value=datetime(1900, 1, 1).date(),
                    max_value=datetime.now().date(),
                    value=datetime(2000, 1, 1).date(),
                    help="Your date of birth as it appears on official documents"
                )
                
                mobile_number = st.text_input(
                    "Mobile Number*", 
                    placeholder="+1234567890",
                    help="Mobile number for OTP verification"
                )
            
            with col2:
                address = st.text_area(
                    "Address*", 
                    placeholder="Enter your complete address\nInclude city, state, and zip code",
                    height=100
                )
                
                emergency_contact = st.text_input(
                    "Emergency Contact",
                    placeholder="Name and phone number",
                    help="Optional: Emergency contact information"
                )
                
                blood_group = st.selectbox(
                    "Blood Group",
                    ["Select", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                    help="Optional: Blood group information"
                )
            
            # Profile photo upload
            st.subheader("📸 Profile Photo")
            profile_photo = st.file_uploader(
                "Upload Profile Photo", 
                type=['jpg', 'jpeg', 'png'],
                help="Upload a clear photo for your health card (optional)"
            )
            
            # Terms and conditions
            st.subheader("📋 Terms & Conditions")
            accept_terms = st.checkbox(
                "I agree to the terms and conditions for digital health card generation",
                help="By checking this box, you agree to the secure storage and use of your health information"
            )
            
            # Generate button
            generate_card = st.form_submit_button("🎫 Generate Health Card", type="primary")
            
            if generate_card:
                if not all([patient_name, date_of_birth, mobile_number, address, accept_terms]):
                    st.error(" Please fill in all required fields and accept the terms and conditions")
                else:
                    try:
                        # Validate mobile number format
                        if not mobile_number.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                            st.error(" Please enter a valid mobile number")
                            return
                        
                        # Generate health card
                        with st.spinner(" Generating your digital health card..."):
                            result = card_generator.generate_health_card(
                                patient_id=str(user_id),
                                patient_name=patient_name,
                                date_of_birth=str(date_of_birth),
                                address=address,
                                mobile_number=mobile_number,
                                profile_photo=profile_photo,
                                emergency_contact=emergency_contact,
                                blood_group=blood_group if blood_group != "Select" else None
                            )
                        
                        if result['success']:
                            st.success("🎉 Health card generated successfully!")
                            st.balloons()
                            
                            # Show generated card info
                            st.info(f"**Your Health Card ID:** `{result['health_card_id']}`")
                            st.write("Your digital health card has been created and is now available for use!")
                            
                            # Refresh page to show the new card
                            st.rerun()
                        else:
                            st.error(f" Failed to generate health card: {result.get('error', 'Unknown error')}")
                    
                    except Exception as e:
                        st.error(f" Error generating health card: {str(e)}")
    
    # Handle update health card
    if st.session_state.get('update_health_card', False):
        st.subheader("✏️ Update Health Card Information")
        st.warning(" Updating your health card will generate a new card ID. Your old card will be archived.")
        
        if st.button(" Cancel Update"):
            st.session_state.update_health_card = False
            st.rerun()
        
        if st.button("✅ Proceed with Update", type="primary"):
            # Archive old card and allow new generation
            try:
                # Archive the existing card
                card_generator.archive_health_card(str(user_id))
                st.session_state.update_health_card = False
                st.success("✅ Previous card archived. You can now generate a new health card.")
                st.rerun()
            except Exception as e:
                st.error(f" Error updating health card: {str(e)}")

def show_sample_templates():
    """Show sample templates for medical records"""
    st.header("📝 Medical Record Templates")
    
    templates = {
        "General Consultation": """
Patient Name: [Your Name]
Date: [Date]
Chief Complaint: [Main reason for visit]
History of Present Illness: [Detailed description]
Physical Examination: [Examination findings]
Assessment: [Doctor's assessment]
Plan: [Treatment plan]
        """,
        "Lab Results": """
Patient Name: [Your Name]
Test Date: [Date]
Laboratory: [Lab name]
Test Results:
- Test 1: [Result] [Normal Range]
- Test 2: [Result] [Normal Range]
Notes: [Any additional notes]
        """,
        "Prescription": """
Patient Name: [Your Name]
Date: [Date]
Prescriber: [Doctor name]
Medications:
1. [Medicine name] - [Dosage] - [Frequency] - [Duration]
2. [Medicine name] - [Dosage] - [Frequency] - [Duration]
Instructions: [Special instructions]
        """
    }
    
    for template_name, template_text in templates.items():
        with st.expander(f" {template_name} Template"):
            st.code(template_text.strip(), language="text")
            if st.button(f" Copy {template_name} Template", key=f"copy_{template_name}"):
                st.info("Template copied! You can paste it in the text entry area.")

def main():
    """Main patient dashboard function"""
    # Check authentication
    check_authentication()
    
    # Get current user
    current_user = get_current_user()
    if not current_user:
        st.error("Failed to load user data")
        st.stop()
    
    # Page header
    st.title("👨‍⚕️ Patient Dashboard")
    st.write(f"Welcome back, **{current_user.get('username', 'Patient')}**!")
    
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Upload Record", 
        "My Records", 
        "Health Card",
        "Export Data",
        "Templates"
    ])
    
    with tab1:
        upload_medical_record()
    
    with tab2:
        display_medical_records()
    
    with tab3:
        manage_health_card()
    
    with tab4:
        export_records()
    
    with tab5:
        show_sample_templates()

# Run the main function directly (Streamlit pages don't use __main__ pattern)
main()