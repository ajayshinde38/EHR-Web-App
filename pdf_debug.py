#!/usr/bin/env python3
"""
Comprehensive PDF debugging tool to identify extraction issues
"""

import sys
import os
import logging
from io import BytesIO

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def analyze_pdf_file(file_path_or_bytes):
    """Comprehensive PDF analysis and debugging"""
    print("🔍 PDF DEBUGGING TOOL")
    print("=" * 50)
    
    # Load file
    if isinstance(file_path_or_bytes, str):
        print(f"📁 Loading file: {file_path_or_bytes}")
        try:
            with open(file_path_or_bytes, 'rb') as f:
                file_content = f.read()
        except Exception as e:
            print(f"❌ Cannot read file: {e}")
            return
    else:
        file_content = file_path_or_bytes
        print(f"📄 Analyzing provided bytes: {len(file_content)} bytes")
    
    # Basic file analysis
    print(f"\n📊 FILE ANALYSIS:")
    print(f"   Size: {len(file_content):,} bytes ({len(file_content)/1024:.1f} KB)")
    print(f"   Header: {file_content[:20]}")
    print(f"   Valid PDF header: {'✅' if file_content.startswith(b'%PDF') else '❌'}")
    
    if not file_content.startswith(b'%PDF'):
        print("❌ File is not a valid PDF - aborting analysis")
        return
    
    # Check PDF libraries
    print(f"\n📚 LIBRARY AVAILABILITY:")
    libraries = {}
    
    try:
        import PyPDF2
        libraries['PyPDF2'] = True
        print("   PyPDF2: ✅")
    except ImportError:
        libraries['PyPDF2'] = False
        print("   PyPDF2: ❌")
    
    try:
        import pdfplumber
        libraries['pdfplumber'] = True
        print("   pdfplumber: ✅")
    except ImportError:
        libraries['pdfplumber'] = False
        print("   pdfplumber: ❌")
    
    try:
        import fitz
        libraries['fitz'] = True
        print("   PyMuPDF (fitz): ✅")
    except ImportError:
        libraries['fitz'] = False
        print("   PyMuPDF (fitz): ❌")
    
    try:
        from pdfminer.high_level import extract_text
        libraries['pdfminer'] = True
        print("   pdfminer: ✅")
    except ImportError:
        libraries['pdfminer'] = False
        print("   pdfminer: ❌")
    
    pdf_bytes = BytesIO(file_content)
    
    # Test each library individually
    print(f"\n🧪 EXTRACTION TESTING:")
    
    # Test PyPDF2
    if libraries['PyPDF2']:
        print("\n1. Testing PyPDF2:")
        try:
            import PyPDF2
            pdf_bytes.seek(0)
            pdf_reader = PyPDF2.PdfReader(pdf_bytes)
            
            print(f"   📄 Pages: {len(pdf_reader.pages)}")
            print(f"   🔒 Encrypted: {pdf_reader.is_encrypted}")
            
            if pdf_reader.is_encrypted:
                print("   🔓 Trying to decrypt...")
                try:
                    decrypt_result = pdf_reader.decrypt("")
                    print(f"   🔓 Decrypt result: {decrypt_result}")
                except Exception as decrypt_error:
                    print(f"   ❌ Decrypt failed: {decrypt_error}")
            
            # Try to extract from first page
            if len(pdf_reader.pages) > 0:
                try:
                    first_page = pdf_reader.pages[0]
                    page_text = first_page.extract_text()
                    print(f"   📝 First page extraction: {len(page_text)} chars")
                    if page_text.strip():
                        print(f"   📝 Preview: {repr(page_text[:100])}")
                    else:
                        print("   ⚠️ No text found on first page")
                except Exception as page_error:
                    print(f"   ❌ Page extraction failed: {page_error}")
            
        except Exception as pypdf_error:
            print(f"   ❌ PyPDF2 failed: {pypdf_error}")
    
    # Test pdfplumber
    if libraries['pdfplumber']:
        print("\n2. Testing pdfplumber:")
        try:
            import pdfplumber
            pdf_bytes.seek(0)
            
            with pdfplumber.open(pdf_bytes) as pdf:
                print(f"   📄 Pages: {len(pdf.pages)}")
                
                if len(pdf.pages) > 0:
                    try:
                        first_page = pdf.pages[0]
                        page_text = first_page.extract_text()
                        print(f"   📝 First page extraction: {len(page_text) if page_text else 0} chars")
                        if page_text and page_text.strip():
                            print(f"   📝 Preview: {repr(page_text[:100])}")
                        else:
                            print("   ⚠️ No text found on first page")
                    except Exception as page_error:
                        print(f"   ❌ Page extraction failed: {page_error}")
            
        except Exception as plumber_error:
            print(f"   ❌ pdfplumber failed: {plumber_error}")
    
    # Test PyMuPDF
    if libraries['fitz']:
        print("\n3. Testing PyMuPDF (fitz):")
        try:
            import fitz
            pdf_bytes.seek(0)
            
            doc = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
            print(f"   📄 Pages: {doc.page_count}")
            
            if doc.page_count > 0:
                try:
                    first_page = doc[0]
                    page_text = first_page.get_text()
                    print(f"   📝 First page extraction: {len(page_text)} chars")
                    if page_text.strip():
                        print(f"   📝 Preview: {repr(page_text[:100])}")
                    else:
                        print("   ⚠️ No text found on first page - might be image-based")
                        
                        # Check if page has images
                        image_list = first_page.get_images()
                        print(f"   🖼️ Images on first page: {len(image_list)}")
                        
                except Exception as page_error:
                    print(f"   ❌ Page extraction failed: {page_error}")
            
            doc.close()
            
        except Exception as fitz_error:
            print(f"   ❌ PyMuPDF failed: {fitz_error}")
    
    # Test pdfminer
    if libraries['pdfminer']:
        print("\n4. Testing pdfminer:")
        try:
            from pdfminer.high_level import extract_text
            pdf_bytes.seek(0)
            
            text = extract_text(pdf_bytes)
            print(f"   📝 Full extraction: {len(text)} chars")
            if text.strip():
                print(f"   📝 Preview: {repr(text[:100])}")
            else:
                print("   ⚠️ No text found")
            
        except Exception as miner_error:
            print(f"   ❌ pdfminer failed: {miner_error}")
    
    # OCR capability test
    print(f"\n🔍 OCR CAPABILITY TEST:")
    try:
        import fitz
        from PIL import Image
        import numpy as np
        
        print("   PyMuPDF for image conversion: ✅")
        print("   PIL for image processing: ✅")
        print("   NumPy for array conversion: ✅")
        
        # Try to convert first page to image
        pdf_bytes.seek(0)
        doc = fitz.open(stream=pdf_bytes.read(), filetype="pdf")
        if doc.page_count > 0:
            try:
                page = doc[0]
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("ppm")
                img = Image.open(BytesIO(img_data))
                print(f"   ✅ Page converted to image: {img.size}")
                
                # Check if advanced OCR is available
                try:
                    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                    from utils.advanced_ocr_processor import AdvancedOCRProcessor, create_handwriting_config
                    print("   ✅ Advanced OCR processor available")
                    
                    # Try OCR on the image
                    img_array = np.array(img)
                    config = create_handwriting_config()
                    ocr_processor = AdvancedOCRProcessor(config)
                    result = ocr_processor.process_medical_document_advanced(img_array)
                    ocr_text = result.get('extracted_text', '')
                    print(f"   ✅ OCR result: {len(ocr_text)} chars, confidence: {result.get('confidence', 'N/A')}")
                    if ocr_text.strip():
                        print(f"   📝 OCR preview: {repr(ocr_text[:100])}")
                    
                except ImportError as ocr_import_error:
                    print(f"   ❌ Advanced OCR not available: {ocr_import_error}")
                except Exception as ocr_error:
                    print(f"   ❌ OCR processing failed: {ocr_error}")
                
            except Exception as convert_error:
                print(f"   ❌ Image conversion failed: {convert_error}")
        
        doc.close()
        
    except ImportError as ocr_lib_error:
        print(f"   ❌ OCR libraries missing: {ocr_lib_error}")
    except Exception as ocr_test_error:
        print(f"   ❌ OCR test failed: {ocr_test_error}")
    
    print(f"\n🎯 DIAGNOSIS SUMMARY:")
    print("=" * 50)
    
    # Provide recommendations based on findings
    if any(libraries.values()):
        print("✅ PDF processing libraries are available")
    else:
        print("❌ No PDF processing libraries available - install PyPDF2, pdfplumber, or pymupdf")
    
    print("\n💡 RECOMMENDATIONS:")
    print("• If all text extraction methods failed but OCR worked: PDF is image-based")
    print("• If encryption was detected: PDF needs password or permissions")
    print("• If no text found anywhere: PDF might be corrupted or use unsupported format")
    print("• If partial text found: PDF has mixed content (text + images)")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        analyze_pdf_file(sys.argv[1])
    else:
        print("Usage: python pdf_debug.py <path_to_pdf_file>")
        print("Or call analyze_pdf_file(pdf_bytes) directly from Python")