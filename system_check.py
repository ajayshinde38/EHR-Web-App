#!/usr/bin/env python3
"""
Quick system status check for PDF extraction
"""

import os
import sys

def check_system_status():
    """Quick check of PDF extraction system"""
    print("🔍 PDF EXTRACTION SYSTEM STATUS")
    print("=" * 40)
    
    # Check working directory
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check if main files exist
    files_to_check = [
        "pages/01_Patient_Dashboard.py",
        "utils/advanced_ocr_processor.py",
        "app.py"
    ]
    
    print(f"\n📄 FILE AVAILABILITY:")
    for file_path in files_to_check:
        exists = os.path.exists(file_path)
        print(f"   {file_path}: {'✅' if exists else '❌'}")
    
    # Check libraries
    print(f"\n📚 LIBRARY STATUS:")
    libraries = [
        ("PyPDF2", "PyPDF2"),
        ("pdfplumber", "pdfplumber"), 
        ("PyMuPDF", "fitz"),
        ("pdfminer", "pdfminer.high_level"),
        ("PIL", "PIL"),
        ("NumPy", "numpy"),
        ("Streamlit", "streamlit")
    ]
    
    available_count = 0
    for name, import_name in libraries:
        try:
            if import_name == "pdfminer.high_level":
                from pdfminer.high_level import extract_text
            else:
                __import__(import_name)
            print(f"   {name}: ✅")
            available_count += 1
        except ImportError:
            print(f"   {name}: ❌")
    
    print(f"\n📊 SYSTEM READINESS:")
    print(f"   Libraries available: {available_count}/{len(libraries)}")
    
    if available_count >= 5:
        print("   Status: ✅ READY for PDF extraction")
    elif available_count >= 3:
        print("   Status: ⚠️ PARTIAL - some features may not work")
    else:
        print("   Status: ❌ NOT READY - install missing libraries")
    
    # Check if Streamlit app is running
    print(f"\n🚀 APPLICATION STATUS:")
    try:
        import requests
        response = requests.get("http://localhost:8502", timeout=2)
        print("   Streamlit app: ✅ Running on localhost:8502")
    except:
        print("   Streamlit app: ❌ Not running")
    
    print(f"\n💡 QUICK FIXES:")
    if available_count < len(libraries):
        print("   Install missing libraries:")
        print("   pip install PyPDF2 pdfplumber pymupdf pdfminer.six pillow numpy streamlit")
    
    print("   To start the app:")
    print("   streamlit run app.py")
    
    print("\n🔧 TROUBLESHOOTING:")
    print("   For PDF issues, use: python pdf_debug.py <your_pdf_file>")
    print("   For detailed logs, check the Streamlit console output")

if __name__ == "__main__":
    check_system_status()