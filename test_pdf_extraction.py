#!/usr/bin/env python3
"""
Test the enhanced PDF extraction functionality
"""

import sys
import os
from io import BytesIO

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from pages.01_Patient_Dashboard import extract_text_from_pdf, extract_text_from_pdf_with_ocr
    print("✅ Successfully imported PDF extraction functions")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def test_pdf_functions():
    """Test PDF extraction functions"""
    print("\n🧪 Testing PDF extraction functions...")
    
    # Test 1: Basic function availability
    print("\n1. Function availability:")
    print(f"   extract_text_from_pdf: {'✅' if callable(extract_text_from_pdf) else '❌'}")
    print(f"   extract_text_from_pdf_with_ocr: {'✅' if callable(extract_text_from_pdf_with_ocr) else '❌'}")
    
    # Test 2: Function signatures
    print("\n2. Function signatures:")
    try:
        import inspect
        sig1 = inspect.signature(extract_text_from_pdf)
        sig2 = inspect.signature(extract_text_from_pdf_with_ocr)
        print(f"   extract_text_from_pdf{sig1}")
        print(f"   extract_text_from_pdf_with_ocr{sig2}")
    except Exception as e:
        print(f"   ❌ Error getting signatures: {e}")
    
    # Test 3: Check required libraries
    print("\n3. Required libraries:")
    libraries = ['PyPDF2', 'pdfplumber', 'fitz', 'pdfminer', 'PIL']
    for lib in libraries:
        try:
            if lib == 'fitz':
                import fitz
            elif lib == 'pdfminer':
                from pdfminer.high_level import extract_text
            elif lib == 'PIL':
                from PIL import Image
            else:
                __import__(lib)
            print(f"   {lib}: ✅")
        except ImportError:
            print(f"   {lib}: ❌ Missing")
    
    # Test 4: Create minimal PDF content
    print("\n4. Testing with minimal content:")
    try:
        # Simple test with empty BytesIO (will fail but test error handling)
        empty_content = BytesIO(b"")
        result = extract_text_from_pdf(empty_content)
        print(f"   Empty content result: {repr(result)}")
    except Exception as e:
        print(f"   Empty content error (expected): {e}")
    
    print("\n🎯 PDF extraction functions are ready for testing!")

if __name__ == "__main__":
    test_pdf_functions()