#!/usr/bin/env python3
"""
Fix the Patient Dashboard OCR integration
"""

def fix_ocr_integration():
    file_path = r'c:\Users\prath\Downloads\CEP (4)\pages\01_Patient_Dashboard.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the problematic line
    old_line = 'ocr_info = get_advanced_ocr_processor(suppress_warnings=True)'
    new_lines = '''# Initialize advanced OCR processor
                        config = st.session_state.get('ocr_config', AdvancedOCRConfig())
                        advanced_ocr = AdvancedOCRProcessor(config)
                        st.info(f"🚀 Advanced OCR: {advanced_ocr.get_engines_status()}")'''
    
    content = content.replace(old_line, new_lines.replace('\n                        ', '\n                        '))
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Successfully updated Patient Dashboard OCR integration")

if __name__ == "__main__":
    fix_ocr_integration()