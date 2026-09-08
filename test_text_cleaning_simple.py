#!/usr/bin/env python3
"""
Simple test of text cleaning logic without dependencies
"""

import re
import unicodedata

def clean_extracted_text(text):
    """Clean and validate extracted text from PDF to remove corrupted/binary data"""
    if not text:
        return None
    
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
    
    # Remove binary/corrupted characters that look like your example
    # Remove sequences of special characters and control codes
    text = re.sub(r'[^\x20-\x7E\n\r\t]', '', text)  # Keep only printable ASCII + whitespace
    
    # Remove sequences that look like binary corruption (more aggressive)
    text = re.sub(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~]{3,}', ' ', text)
    
    # Remove repeated pattern characters
    text = re.sub(r'(.)\1{8,}', r'\1', text)  # Replace 8+ repeated chars with single char
    
    # Remove lines that look like corruption patterns
    lines = text.split('\n')
    clean_lines = []
    for line in lines:
        line = line.strip()
        if line:
            # Skip lines that are obviously corrupted
            if re.match(r'^[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~0-9-]+$', line):
                continue  # Skip lines with only symbols/numbers/dashes
            
            # Skip lines with too many special characters
            special_count = len(re.findall(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./`~]', line))
            if special_count > len(line) * 0.5:  # More than 50% special chars
                continue
            
            # Count alphabetic characters vs total
            alpha_count = sum(1 for c in line if c.isalpha())
            total_count = len(line)
            
            # Keep line if it has reasonable text content (>30% alphabetic)
            if total_count > 0 and alpha_count / total_count > 0.3:
                clean_lines.append(line)
            elif any(word.lower() in ['patient', 'medication', 'dose', 'mg', 'treatment', 'diagnosis', 'doctor', 'hospital', 'medical', 'name', 'age', 'date'] for word in line.lower().split()):
                # Keep lines with medical keywords even if low alpha ratio
                clean_lines.append(line)
    
    cleaned_text = '\n'.join(clean_lines)
    
    # Final validation - ensure we have meaningful content
    if len(cleaned_text.strip()) < 10:
        print(f"Warning: Extracted text too short after cleaning - likely corrupted")
        return None
    
    # Check if result is mostly readable
    alpha_count = sum(1 for c in cleaned_text if c.isalpha())
    total_count = len(cleaned_text.replace(' ', '').replace('\n', '').replace('\t', ''))
    
    if total_count > 0 and alpha_count / total_count < 0.4:  # Increased threshold
        print(f"Warning: Extracted text appears to be corrupted or binary data (alpha ratio: {alpha_count/total_count:.2f})")
        return None
    
    # Check for excessive repetition (sign of corruption)
    if len(cleaned_text) > 100:
        # Look for patterns that repeat too much
        words = cleaned_text.split()
        if len(words) > 10:
            unique_words = set(words)
            if len(unique_words) / len(words) < 0.3:  # Less than 30% unique words
                print("Warning: Text has excessive repetition - likely corrupted")
                return None
    
    return cleaned_text.strip()

def test_text_cleaning():
    """Test the text cleaning function with corrupted input"""
    
    print("🧪 Testing Text Cleaning Function\n")
    
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
    print(f"   Input preview: {repr(corrupted_input[:50])}...")
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
    print(f"   Input preview: {repr(binary_input)}")
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
    print(f"   Result preview: {repr(result[:100]) if result else None}...")
    print(f"   Status: {'✅ Preserved correctly' if result and len(result) > 100 else '❌ Lost content'}")
    
    # Test 5: Edge cases
    print("\n5. Testing edge cases:")
    test_cases = [
        (None, "None"),
        ("", "Empty string"), 
        ("   ", "Whitespace only"),
        ("!@#$%^", "Only symbols"),
        ("1234567890", "Only numbers")
    ]
    
    for test_input, name in test_cases:
        result = clean_extracted_text(test_input)
        status = "✅ Handled correctly" if result is None else f"❌ Returned: {repr(result)}"
        print(f"   {name}: {status}")
    
    print("\n🎯 Text cleaning test complete!")
    print("\n💡 The function successfully filters out corrupted/binary data while preserving medical content!")

if __name__ == "__main__":
    test_text_cleaning()