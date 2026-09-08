#!/usr/bin/env python3
"""
Advanced OCR Pipeline Test and Demonstration
"""

import sys
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def create_medical_prescription_image():
    """Create a realistic medical prescription image for testing"""
    # Create image with medical prescription content
    img = Image.new('RGB', (600, 800), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a medical-like font
    try:
        font_title = ImageFont.truetype("arial.ttf", 16)
        font_content = ImageFont.truetype("arial.ttf", 12)
        font_small = ImageFont.truetype("arial.ttf", 10)
    except:
        font_title = ImageFont.load_default()
        font_content = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Prescription header
    draw.text((50, 30), "DR. JOHN SMITH", fill='black', font=font_title)
    draw.text((50, 50), "General Medicine Specialist", fill='black', font=font_small)
    draw.text((50, 70), "License: MD-12345", fill='black', font=font_small)
    
    # Patient information
    draw.text((50, 110), "PATIENT: Jane Doe (F)", fill='black', font=font_content)
    draw.text((50, 130), "Age: 45 years", fill='black', font=font_content)
    draw.text((50, 150), "Date: 15-10-2025", fill='black', font=font_content)
    draw.text((50, 170), "BP: 140/90 mmHg", fill='black', font=font_content)
    
    # Prescription details
    draw.text((50, 210), "Rx:", fill='black', font=font_title)
    
    # Medication 1
    draw.text((70, 240), "1. Amlodipine 5mg tablet", fill='black', font=font_content)
    draw.text((70, 260), "   Take once daily in morning", fill='black', font=font_content)
    draw.text((70, 280), "   For 30 days", fill='black', font=font_content)
    
    # Medication 2
    draw.text((70, 320), "2. Metformin 500mg tablet", fill='black', font=font_content)
    draw.text((70, 340), "   Take twice daily after meals", fill='black', font=font_content)
    draw.text((70, 360), "   For 30 days", fill='black', font=font_content)
    
    # Medication 3
    draw.text((70, 400), "3. Vitamin D3 1000 IU capsule", fill='black', font=font_content)
    draw.text((70, 420), "   Take once daily", fill='black', font=font_content)
    draw.text((70, 440), "   For 30 days", fill='black', font=font_content)
    
    # Instructions
    draw.text((50, 480), "Instructions:", fill='black', font=font_content)
    draw.text((70, 500), "- Take medications as prescribed", fill='black', font=font_small)
    draw.text((70, 520), "- Monitor blood pressure daily", fill='black', font=font_small)
    draw.text((70, 540), "- Follow up after 2 weeks", fill='black', font=font_small)
    draw.text((70, 560), "- Avoid fatty foods", fill='black', font=font_small)
    
    # Footer
    draw.text((50, 620), "Next visit: 30-10-2025", fill='black', font=font_content)
    draw.text((50, 650), "Doctor's Signature", fill='black', font=font_content)
    
    return img

def test_standard_vs_advanced_ocr():
    """Compare standard OCR vs advanced OCR pipeline"""
    print("🧪 Testing Standard vs Advanced OCR Pipeline")
    print("=" * 60)
    
    try:
        from utils.ocr_processor import get_ocr_processor
        from utils.advanced_ocr_processor import get_advanced_ocr_processor, OCRConfig
        
        # Create test image
        print("📷 Creating test medical prescription image...")
        test_image = create_medical_prescription_image()
        image_array = np.array(test_image)
        
        # Test Standard OCR
        print("\n🔍 Testing Standard OCR...")
        standard_processor = get_ocr_processor(suppress_warnings=True)
        standard_results = standard_processor.process_medical_document(image_array, "prescription")
        
        # Test Advanced OCR
        print("🚀 Testing Advanced OCR Pipeline...")
        config = OCRConfig(
            noise_reduction=True,
            contrast_enhancement=True,
            spell_correction=True,
            medical_entity_extraction=True,
            confidence_threshold=0.3
        )
        advanced_processor = get_advanced_ocr_processor(config, suppress_warnings=True)
        advanced_results = advanced_processor.process_medical_document_advanced(image_array, "prescription")
        
        # Compare results
        print("\n📊 COMPARISON RESULTS")
        print("=" * 60)
        
        # Standard OCR Results
        print("\n🔍 STANDARD OCR:")
        print(f"Text Length: {len(standard_results.get('extracted_text', ''))}")
        print(f"Confidence: {standard_results.get('confidence', 0):.1f}%")
        print(f"Text Preview: {standard_results.get('extracted_text', '')[:100]}...")
        
        # Advanced OCR Results
        print("\n🚀 ADVANCED OCR:")
        print(f"Text Length: {len(advanced_results.get('extracted_text', ''))}")
        print(f"Confidence: {advanced_results.get('confidence', 0):.1f}%")
        print(f"Quality Score: {advanced_results.get('quality_score', 0):.2f}")
        print(f"Word Count: {advanced_results.get('word_count', 0)}")
        print(f"Processing Time: {advanced_results.get('processing_time_seconds', 0):.2f}s")
        print(f"Text Preview: {advanced_results.get('extracted_text', '')[:100]}...")
        
        # Medical Entities
        entities = advanced_results.get('medical_entities', {})
        if entities:
            print("\n🏥 MEDICAL ENTITIES DETECTED:")
            for entity_type, entity_list in entities.items():
                if entity_list:
                    print(f"  {entity_type.title()}: {[e['text'] for e in entity_list]}")
        
        # Text Processing Details
        text_processing = advanced_results.get('text_processing', {})
        if text_processing:
            print(f"\n📝 TEXT PROCESSING:")
            corrections = text_processing.get('corrections_applied', [])
            if corrections:
                print(f"  Corrections Applied: {len(corrections)}")
                for correction in corrections[:3]:  # Show first 3
                    print(f"    - {correction}")
            print(f"  Improvement Score: {text_processing.get('improvement_score', 0):.2f}")
        
        # Accuracy Analysis
        print("\n📈 ACCURACY ANALYSIS:")
        standard_words = len(standard_results.get('extracted_text', '').split())
        advanced_words = len(advanced_results.get('extracted_text', '').split())
        
        print(f"Standard OCR Word Count: {standard_words}")
        print(f"Advanced OCR Word Count: {advanced_words}")
        
        if advanced_words > standard_words:
            improvement = ((advanced_words - standard_words) / max(standard_words, 1)) * 100
            print(f"✅ Advanced OCR extracted {improvement:.1f}% more words")
        
        confidence_improvement = advanced_results.get('confidence', 0) - standard_results.get('confidence', 0)
        if confidence_improvement > 0:
            print(f"✅ Advanced OCR confidence improved by {confidence_improvement:.1f}%")
        
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def demonstrate_preprocessing_steps():
    """Demonstrate the image preprocessing pipeline"""
    print("\n🖼️  DEMONSTRATING PREPROCESSING STEPS")
    print("=" * 60)
    
    try:
        from utils.advanced_ocr_processor import get_advanced_ocr_processor, OCRConfig
        
        # Create test image
        test_image = create_medical_prescription_image()
        
        # Add some noise and rotation to simulate real-world conditions
        image_array = np.array(test_image)
        
        # Simulate noise
        noise = np.random.normal(0, 10, image_array.shape).astype(np.uint8)
        noisy_image = np.clip(image_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        print("📷 Created test image with simulated noise")
        
        # Process with advanced OCR
        config = OCRConfig(include_debug_images=True)
        processor = get_advanced_ocr_processor(config, suppress_warnings=True)
        
        # Get preprocessing results
        processed_images = processor.preprocess_image_advanced(noisy_image)
        
        print(f"\n🔧 PREPROCESSING STEPS APPLIED:")
        for step_name in processed_images.keys():
            print(f"  ✅ {step_name.replace('_', ' ').title()}")
        
        print(f"\nTotal preprocessing variants: {len(processed_images)}")
        
    except Exception as e:
        print(f"❌ Preprocessing demonstration failed: {e}")

if __name__ == "__main__":
    print("🚀 ADVANCED OCR PIPELINE DEMONSTRATION")
    print("=" * 60)
    
    # Test the pipeline
    success = test_standard_vs_advanced_ocr()
    
    if success:
        # Demonstrate preprocessing
        demonstrate_preprocessing_steps()
        
        print("\n🎉 DEMONSTRATION COMPLETED!")
        print("📋 The Advanced OCR Pipeline provides:")
        print("   ✅ Enhanced image preprocessing")
        print("   ✅ Multi-engine OCR extraction")
        print("   ✅ Medical entity recognition")
        print("   ✅ Spell correction")
        print("   ✅ Quality assessment")
        print("   ✅ Structured output")
    else:
        print("\n❌ Demonstration failed - check dependencies")