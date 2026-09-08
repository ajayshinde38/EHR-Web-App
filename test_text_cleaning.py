#!/usr/bin/env python3
"""
Test the enhanced text cleaning functionality for corrupted PDF extraction
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_text_cleaning():
    """Test the text cleaning function with corrupted input"""
    
    # Import the cleaning function
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "patient_dashboard", 
        "pages/01_Patient_Dashboard.py"
    )
    patient_module = importlib.util.module_from_spec(spec)
    
    # Mock streamlit to avoid errors
    import types
    mock_st = types.ModuleType('streamlit')
    mock_st.set_page_config = lambda **kwargs: None
    sys.modules['streamlit'] = mock_st
    
    try:
        spec.loader.exec_module(patient_module)
        clean_extracted_text = patient_module.clean_extracted_text
        print("✅ Successfully imported clean_extracted_text function")
    except Exception as e:
        print(f"❌ Import error: {e}")
        return
    
    print("\n🧪 Testing Text Cleaning Function\n")
    
    # Test 1: Your corrupted input
    corrupted_input = """!0*21/*.-4;K@48G9-.BYBGNPTUT3?]c\\RbKSTQC''Q6.6QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ
	"	
}!1AQa"q2#BR$3br	
%&'( 
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
(
("""
    
    print("1. Testing corrupted input from user:")
    print(f"   Input length: {len(corrupted_input)} characters")
    result = clean_extracted_text(corrupted_input)
    print(f"   Result: {repr(result)}")
    print(f"   Status: {'✅ Correctly filtered out' if result is None else '❌ Should have been filtered'}")
    
    # Test 2: Mixed good and bad content
    mixed_input = """!@#$%^&*()_+Patient Information Report
QQQQQQQQQQQQQQQQ
Name: John Doe
Age: 45 years
Medication: Aspirin 81mg daily
!!!!!!!!!!!!!!!!!!
Diagnosis: Hypertension
((((((((((((((((
Follow up in 2 weeks"""
    
    print("\n2. Testing mixed content:")
    print(f"   Input preview: {mixed_input[:50]}...")
    result = clean_extracted_text(mixed_input)
    print(f"   Result: {repr(result)}")
    print(f"   Status: {'✅ Cleaned successfully' if result and 'Patient' in result else '❌ Lost medical content'}")
    
    # Test 3: Binary/bytes input
    binary_input = b'\x00\x01\x02\x03Patient Record\x04\x05\x06\x07'
    
    print("\n3. Testing binary input:")
    print(f"   Input type: {type(binary_input)}")
    result = clean_extracted_text(binary_input)
    print(f"   Result: {repr(result)}")
    print(f"   Status: {'✅ Converted and cleaned' if result and 'Patient' in result else '❌ Failed to handle binary'}")
    
    # Test 4: Normal medical text
    normal_input = """Patient: Jane Smith
Date of Birth: 1980-05-15
Medication: Metformin 500mg twice daily
Diagnosis: Type 2 Diabetes
Instructions: Take with meals, monitor blood sugar"""
    
    print("\n4. Testing normal medical text:")
    print(f"   Input preview: {normal_input[:50]}...")
    result = clean_extracted_text(normal_input)
    print(f"   Result length: {len(result) if result else 0}")
    print(f"   Status: {'✅ Preserved correctly' if result and len(result) > 100 else '❌ Lost content'}")
    
    # Test 5: Empty/None input
    print("\n5. Testing edge cases:")
    for test_input, name in [(None, "None"), ("", "Empty string"), ("   ", "Whitespace only")]:
        result = clean_extracted_text(test_input)
        print(f"   {name}: {'✅ Handled correctly' if result is None else '❌ Should return None'}")
    
    print("\n🎯 Text cleaning test complete!")

if __name__ == "__main__":
    test_text_cleaning()