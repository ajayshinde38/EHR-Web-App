#!/usr/bin/env python3
"""
Simple test for PDF extraction functions
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test importing PDF functions"""
    
    try:
        # Try importing as module
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "patient_dashboard", 
            "pages/01_Patient_Dashboard.py"
        )
        patient_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patient_module)
        
        # Check if functions exist
        has_extract = hasattr(patient_module, 'extract_text_from_pdf')
        has_ocr_extract = hasattr(patient_module, 'extract_text_from_pdf_with_ocr')
        
        print(f"✅ Module loaded successfully")
        print(f"   extract_text_from_pdf: {'✅' if has_extract else '❌'}")
        print(f"   extract_text_from_pdf_with_ocr: {'✅' if has_ocr_extract else '❌'}")
        
        if has_extract:
            # Get function signature
            import inspect
            sig = inspect.signature(patient_module.extract_text_from_pdf)
            print(f"   Function signature: extract_text_from_pdf{sig}")
        
        return patient_module
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return None

def test_libraries():
    """Test required PDF libraries"""
    print("\n📚 Testing PDF extraction libraries:")
    
    libraries = {
        'PyPDF2': 'PyPDF2',
        'pdfplumber': 'pdfplumber', 
        'PyMuPDF': 'fitz',
        'pdfminer': 'pdfminer.high_level',
        'PIL': 'PIL'
    }
    
    available = []
    for name, import_name in libraries.items():
        try:
            if import_name == 'pdfminer.high_level':
                from pdfminer.high_level import extract_text
            else:
                __import__(import_name)
            print(f"   {name}: ✅")
            available.append(name)
        except ImportError:
            print(f"   {name}: ❌")
    
    print(f"\n📊 Available libraries: {len(available)}/5")
    return available

if __name__ == "__main__":
    print("🔍 Testing PDF Extraction Setup\n")
    
    # Test imports
    module = test_imports()
    
    # Test libraries
    available_libs = test_libraries()
    
    print(f"\n🎯 Status Summary:")
    print(f"   Functions imported: {'✅' if module else '❌'}")
    print(f"   PDF libraries available: {len(available_libs)}/5")
    
    if module and available_libs:
        print(f"   Ready for PDF extraction: ✅")
    else:
        print(f"   Setup incomplete: ❌")
        
    print("\n💡 Next: Test with actual PDF files to verify extraction works!")