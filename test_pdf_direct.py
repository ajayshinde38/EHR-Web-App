#!/usr/bin/env python3
"""
Direct test of PDF extraction functions without Streamlit dependencies
"""

import sys
import os
import logging
from io import BytesIO

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_text_from_pdf(uploaded_file):
    """Enhanced PDF text extraction with multiple methods and comprehensive fallbacks"""
    try:
        from io import BytesIO
        import logging
        
        # Reset file pointer and validate file
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        
        if not file_content or len(file_content) < 100:
            logger.error("PDF file is empty or too small")
            return None
        
        pdf_bytes = BytesIO(file_content)
        extracted_text = ""
        
        # Method 1: Try PyPDF2 first (most common) with enhanced error handling
        try:
            import PyPDF2
            pdf_bytes.seek(0)
            pdf_reader = PyPDF2.PdfReader(pdf_bytes)
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                logger.warning("PDF is encrypted/password protected")
                # Try empty password first
                try:
                    pdf_reader.decrypt("")
                except:
                    logger.error("Cannot decrypt PDF - password required")
                    # Continue to other methods
            
            text = ""
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text and page_text.strip():
                        text += page_text + "\n"
                except Exception as page_error:
                    logger.warning(f"PyPDF2 failed on page {page_num + 1}: {page_error}")
                    continue
            
            if text.strip():
                extracted_text = text.strip()
                logger.info(f"PyPDF2 successfully extracted {len(extracted_text)} characters")
                return extracted_text
                
        except ImportError:
            logger.warning("PyPDF2 not available - install with: pip install PyPDF2")
        except Exception as pypdf_error:
            logger.warning(f"PyPDF2 extraction failed: {pypdf_error}")
        
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
                extracted_text = text.strip()
                logger.info(f"pdfplumber successfully extracted {len(extracted_text)} characters")
                return extracted_text
                
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
                extracted_text = text.strip()
                logger.info(f"PyMuPDF successfully extracted {len(extracted_text)} characters")
                return extracted_text
                
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
                extracted_text = text.strip()
                logger.info(f"pdfminer successfully extracted {len(extracted_text)} characters")
                return extracted_text
                
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
                    extracted_text = " ".join(text_parts)
                    logger.info(f"Raw extraction found {len(extracted_text)} characters")
                    return extracted_text
                    
        except Exception as raw_error:
            logger.warning(f"Raw text extraction failed: {raw_error}")
        
        # If all methods fail, return None
        logger.error("All PDF extraction methods failed - PDF may be image-based, corrupted, or heavily protected")
        return None
    
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return None

def create_test_pdf():
    """Create a simple test PDF"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from io import BytesIO
        
        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        
        # Add some test content
        p.drawString(100, 750, "Medical Record Test Document")
        p.drawString(100, 700, "Patient: John Doe")
        p.drawString(100, 650, "Medication: Aspirin 81mg")
        p.drawString(100, 600, "Frequency: Once daily")
        p.drawString(100, 550, "Instructions: Take with food")
        
        p.showPage()
        p.save()
        
        buffer.seek(0)
        return buffer
        
    except ImportError:
        logger.error("reportlab not available for PDF creation test")
        return None

def test_pdf_extraction():
    """Test the enhanced PDF extraction"""
    print("🧪 Testing Enhanced PDF Extraction\n")
    
    # Test 1: Create and extract from test PDF
    print("1. Testing with generated PDF...")
    test_pdf = create_test_pdf()
    
    if test_pdf:
        result = extract_text_from_pdf(test_pdf)
        if result:
            print(f"   ✅ Extraction successful: {len(result)} characters")
            print(f"   📄 Content preview: {result[:100]}...")
        else:
            print("   ❌ Extraction failed")
    else:
        print("   ⚠️ Could not create test PDF (reportlab missing)")
    
    # Test 2: Test with empty content
    print("\n2. Testing error handling...")
    empty_file = BytesIO(b"")
    result = extract_text_from_pdf(empty_file)
    print(f"   Empty file handled: {'✅' if result is None else '❌'}")
    
    # Test 3: Test with invalid content
    invalid_file = BytesIO(b"This is not a PDF file")
    result = extract_text_from_pdf(invalid_file)
    print(f"   Invalid file handled: {'✅' if result is None else '❌'}")
    
    print("\n🎯 PDF extraction testing complete!")

if __name__ == "__main__":
    test_pdf_extraction()