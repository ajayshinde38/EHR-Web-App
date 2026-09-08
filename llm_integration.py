"""
LLM Integration Utility for Text Summarization
Prompt 6: Hugging Face transformers implementation with facebook/bart-large-cnn

This module provides text summarization functionality using Hugging Face transformers
with the facebook/bart-large-cnn model for high-quality text summarization.
"""

import logging
import re
import torch
from typing import Optional, List, Dict, Any
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import dependencies with proper error handling
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    TRANSFORMERS_AVAILABLE = True
    logger.info("Transformers library loaded successfully")
except ImportError as e:
    logger.error(f"Transformers not available: {str(e)}")
    TRANSFORMERS_AVAILABLE = False

class TextSummarizer:
    """
    Advanced text summarization using Hugging Face facebook/bart-large-cnn model
    """
    
    def __init__(self, model_name: str = "facebook/bart-large-cnn"):
        """
        Initialize the text summarizer
        
        Args:
            model_name (str): Hugging Face model identifier
        """
        self.model_name = model_name
        self.summarizer = None
        self.tokenizer = None
        self.model = None
        self._initialize_model()
    
    def _initialize_model(self) -> None:
        """Initialize the summarization model and tokenizer"""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available, using fallback summarization")
            return
        
        try:
            # Check for GPU availability
            device = 0 if torch.cuda.is_available() else -1
            device_name = "GPU" if torch.cuda.is_available() else "CPU"
            logger.info(f"Using device: {device_name}")
            
            # Initialize the summarization pipeline
            self.summarizer = pipeline(
                "summarization",
                model=self.model_name,
                device=device,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                trust_remote_code=True
            )
            
            # Load tokenizer separately for advanced text processing
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            logger.info(f"Successfully loaded model: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize model {self.model_name}: {str(e)}")
            self.summarizer = None
    
    def preprocess_text(self, text: str) -> str:
        """
        Preprocess input text for optimal summarization
        
        Args:
            text (str): Raw input text
            
        Returns:
            str: Preprocessed text
        """
        if not text or not isinstance(text, str):
            return ""
        
        # Remove excessive whitespace and normalize
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Remove special characters that might interfere with processing
        text = re.sub(r'[^\w\s.,;:()\-/\'\"!?]', '', text)
        
        # Ensure proper sentence endings
        if text and not text.endswith(('.', '!', '?')):
            text += '.'
        
        return text
    
    def chunk_text(self, text: str, max_chunk_length: int = 1024) -> List[str]:
        """
        Split long text into manageable chunks for processing
        
        Args:
            text (str): Input text to chunk
            max_chunk_length (int): Maximum characters per chunk
            
        Returns:
            List[str]: List of text chunks
        """
        if not text:
            return []
        
        # If text is short enough, return as single chunk
        if len(text) <= max_chunk_length:
            return [text]
        
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            # If adding this sentence would exceed limit, start new chunk
            if len(current_chunk) + len(sentence) + 1 > max_chunk_length:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # Sentence itself is too long, split by words
                    words = sentence.split()
                    word_chunk = ""
                    for word in words:
                        if len(word_chunk) + len(word) + 1 > max_chunk_length:
                            if word_chunk:
                                chunks.append(word_chunk.strip())
                            word_chunk = word
                        else:
                            word_chunk += " " + word if word_chunk else word
                    if word_chunk:
                        current_chunk = word_chunk
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def fallback_summarization(self, text: str, max_sentences: int = 3) -> str:
        """
        Simple rule-based summarization as fallback when model is unavailable
        
        Args:
            text (str): Input text
            max_sentences (int): Maximum sentences in summary
            
        Returns:
            str: Simple extractive summary
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        
        if len(sentences) <= max_sentences:
            return text
        
        # Score sentences based on position, length, and keywords
        scored_sentences = []
        total_sentences = len(sentences)
        
        for i, sentence in enumerate(sentences):
            score = 0
            
            # Position scoring (favor beginning and end)
            if i < total_sentences * 0.3:  # First 30%
                score += 3
            elif i > total_sentences * 0.7:  # Last 30%
                score += 2
            
            # Length scoring (prefer medium-length sentences)
            if 50 <= len(sentence) <= 200:
                score += 2
            elif 20 <= len(sentence) <= 300:
                score += 1
            
            # Keyword scoring (basic relevance)
            important_words = ['important', 'significant', 'key', 'main', 'primary', 
                             'conclusion', 'result', 'finding', 'therefore', 'however']
            for word in important_words:
                if word.lower() in sentence.lower():
                    score += 1
            
            scored_sentences.append((score, i, sentence))
        
        # Sort by score (descending) then by position (ascending) for ties
        scored_sentences.sort(key=lambda x: (-x[0], x[1]))
        
        # Select top sentences
        selected_sentences = sorted(
            [item for item in scored_sentences[:max_sentences]], 
            key=lambda x: x[1]  # Maintain original order
        )
        
        summary = '. '.join([item[2] for item in selected_sentences])
        return summary + '.' if summary and not summary.endswith('.') else summary
    
    def summarize_text(self, input_text: str, 
                      max_length: int = 150, 
                      min_length: int = 30) -> str:
        """
        Main summarization function - as requested in Prompt 6
        
        Args:
            input_text (str): Text to summarize
            max_length (int): Maximum length of summary in tokens
            min_length (int): Minimum length of summary in tokens
            
        Returns:
            str: Generated summary
        """
        try:
            # Input validation
            if not input_text or not isinstance(input_text, str):
                return "Error: No valid input text provided"
            
            # Preprocess the input text
            processed_text = self.preprocess_text(input_text)
            
            if len(processed_text.strip()) < 10:
                return "Error: Input text too short to summarize"
            
            # Use model if available
            if self.summarizer and TRANSFORMERS_AVAILABLE:
                return self._model_summarize(processed_text, max_length, min_length)
            else:
                logger.warning("Using fallback summarization method")
                return self.fallback_summarization(processed_text)
                
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return f"Error during summarization: {str(e)}"
    
    def _model_summarize(self, text: str, max_length: int, min_length: int) -> str:
        """
        Internal method for model-based summarization
        
        Args:
            text (str): Preprocessed text
            max_length (int): Maximum summary length
            min_length (int): Minimum summary length
            
        Returns:
            str: Model-generated summary
        """
        try:
            # Check text length and handle accordingly
            token_count = len(self.tokenizer.encode(text)) if self.tokenizer else len(text.split())
            
            if token_count > 1024:  # Model's max input length
                # Process in chunks for long texts
                chunks = self.chunk_text(text, 900)  # Leave buffer for tokenization
                chunk_summaries = []
                
                for i, chunk in enumerate(chunks):
                    if len(chunk.strip()) < 50:  # Skip very short chunks
                        continue
                    
                    try:
                        # Adjust parameters for chunks
                        chunk_max_length = max(min_length, max_length // len(chunks) + 20)
                        chunk_min_length = min(min_length, len(chunk.split()) // 4)
                        
                        result = self.summarizer(
                            chunk,
                            max_length=chunk_max_length,
                            min_length=chunk_min_length,
                            do_sample=False,
                            early_stopping=True
                        )
                        
                        if result and len(result) > 0:
                            chunk_summaries.append(result[0]['summary_text'])
                            
                    except Exception as e:
                        logger.warning(f"Failed to summarize chunk {i+1}: {str(e)}")
                        continue
                
                # Combine chunk summaries
                if chunk_summaries:
                    combined_summary = ' '.join(chunk_summaries)
                    
                    # If combined summary is still too long, summarize again
                    if len(combined_summary.split()) > max_length:
                        try:
                            final_result = self.summarizer(
                                combined_summary,
                                max_length=max_length,
                                min_length=min_length,
                                do_sample=False,
                                early_stopping=True
                            )
                            return final_result[0]['summary_text']
                        except:
                            # Truncate if final summarization fails
                            words = combined_summary.split()
                            return ' '.join(words[:max_length])
                    
                    return combined_summary
                else:
                    return self.fallback_summarization(text)
            
            else:
                # Process text directly
                result = self.summarizer(
                    text,
                    max_length=max_length,
                    min_length=min_length,
                    do_sample=False,
                    early_stopping=True
                )
                
                return result[0]['summary_text']
                
        except Exception as e:
            logger.error(f"Model summarization failed: {str(e)}")
            return self.fallback_summarization(text)
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded model
        
        Returns:
            Dict[str, Any]: Model information
        """
        return {
            "model_name": self.model_name,
            "model_loaded": self.summarizer is not None,
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "device": "GPU" if torch.cuda.is_available() else "CPU",
            "torch_version": torch.__version__ if 'torch' in globals() else "Not available"
        }

# Global instance for easy access
_summarizer_instance = None

def get_summarizer() -> TextSummarizer:
    """
    Get or create a global summarizer instance
    
    Returns:
        TextSummarizer: Initialized summarizer instance
    """
    global _summarizer_instance
    if _summarizer_instance is None:
        _summarizer_instance = TextSummarizer()
    return _summarizer_instance

def summarize_text(input_text: str, max_length: int = 150, min_length: int = 30) -> str:
    """
    Main function for text summarization as requested in Prompt 6
    
    This function provides a simple interface to the facebook/bart-large-cnn model
    for text summarization using Hugging Face transformers.
    
    Args:
        input_text (str): The text to be summarized
        max_length (int): Maximum length of the summary (default: 150 tokens)
        min_length (int): Minimum length of the summary (default: 30 tokens)
    
    Returns:
        str: The generated summary of the input text
    
    Example:
        >>> text = "This is a long document about artificial intelligence..."
        >>> summary = summarize_text(text)
        >>> print(summary)
    """
    summarizer = get_summarizer()
    return summarizer.summarize_text(input_text, max_length, min_length)

# Utility functions for enhanced functionality
def batch_summarize(texts: List[str], max_length: int = 150, min_length: int = 30) -> List[str]:
    """
    Summarize multiple texts in batch
    
    Args:
        texts (List[str]): List of texts to summarize
        max_length (int): Maximum summary length
        min_length (int): Minimum summary length
    
    Returns:
        List[str]: List of summaries
    """
    summarizer = get_summarizer()
    return [summarizer.summarize_text(text, max_length, min_length) for text in texts]

def summarize_with_metadata(input_text: str, max_length: int = 150, min_length: int = 30) -> Dict[str, Any]:
    """
    Generate summary with additional metadata
    
    Args:
        input_text (str): Text to summarize
        max_length (int): Maximum summary length
        min_length (int): Minimum summary length
    
    Returns:
        Dict[str, Any]: Dictionary containing summary and metadata
    """
    summarizer = get_summarizer()
    summary = summarizer.summarize_text(input_text, max_length, min_length)
    
    return {
        "summary": summary,
        "original_length": len(input_text),
        "summary_length": len(summary),
        "compression_ratio": len(summary) / len(input_text) if input_text else 0,
        "timestamp": datetime.now().isoformat(),
        "word_count": len(summary.split()) if summary else 0
    }

def summarize_medical_record(input_text: str, max_length: int = 200, min_length: int = 50) -> str:
    """
    Specialized medical record summarization with proper medical formatting
    
    Args:
        input_text (str): Medical record text to summarize
        max_length (int): Maximum summary length in tokens
        min_length (int): Minimum summary length in tokens
    
    Returns:
        str: Formatted medical summary
    """
    try:
        summarizer = get_summarizer()
        
        # Pre-process medical text for better summarization
        processed_text = preprocess_medical_text(input_text)
        
        # Generate basic summary
        basic_summary = summarizer.summarize_text(processed_text, max_length, min_length)
        
        # Post-process to medical format
        formatted_summary = format_medical_summary(basic_summary, input_text)
        
        return formatted_summary
        
    except Exception as e:
        logger.error(f"Medical summarization failed: {e}")
        return f"Error generating medical summary: {str(e)}"

def preprocess_medical_text(text: str) -> str:
    """
    Preprocess medical text for optimal summarization
    
    Args:
        text (str): Raw medical text
    
    Returns:
        str: Preprocessed medical text
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Clean and structure the text
    cleaned_text = text.strip()
    
    # Remove excessive whitespace
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    # Fix common OCR errors in medical text
    cleaned_text = re.sub(r'\b([A-Z])[il1]\b', r'\1I', cleaned_text)  # Fix I to l conversions
    cleaned_text = re.sub(r'\b0([A-Za-z])', r'O\1', cleaned_text)  # Fix 0 to O conversions
    
    # Remove excessive punctuation
    cleaned_text = re.sub(r'([.!?])\1+', r'\1', cleaned_text)
    
    # Ensure sentences end properly
    if cleaned_text and not cleaned_text[-1] in '.!?':
        cleaned_text += '.'
    
    return cleaned_text

def format_medical_summary(summary: str, original_text: str) -> str:
    """
    Format summary into proper medical record structure with intelligent extraction
    
    Args:
        summary (str): Basic summary text
        original_text (str): Original medical record text
    
    Returns:
        str: Professionally formatted medical summary with proper sections
    """
    if not summary:
        return "Unable to generate medical summary."
    
    # Clean the summary text
    summary = summary.strip()
    
    # Extract key information from the original text
    key_info = extract_key_medical_info(original_text)
    
    # Build a proper structured medical summary
    formatted_summary = ""
    
    # Clinical Summary Section - Use the AI-generated summary
    formatted_summary += "**CLINICAL SUMMARY:**\n"
    formatted_summary += create_clinical_summary(summary, key_info) + "\n\n"
    
    # Assessment Section
    formatted_summary += "**ASSESSMENT:**\n"
    formatted_summary += create_assessment_section(key_info, original_text) + "\n\n"
    
    # Plan Section
    formatted_summary += "**PLAN:**\n"
    formatted_summary += create_plan_section(key_info, original_text) + "\n"
    
    return formatted_summary

def extract_medical_sections(text: str) -> Dict[str, str]:
    """
    Extract common medical record sections
    
    Args:
        text (str): Medical record text
    
    Returns:
        Dict[str, str]: Dictionary of identified medical sections
    """
    sections = {}
    
    if not text:
        return sections
    
    text_lower = text.lower()
    
    # Common medical section patterns
    patterns = {
        'chief_complaint': r'(?:chief complaint|presenting complaint|reason for visit)[:\s]*([^\n.]*)',
        'assessment': r'(?:assessment|diagnosis|impression)[:\s]*([^\n.]*)',
        'plan': r'(?:plan|treatment|recommendation)[:\s]*([^\n.]*)',
        'history': r'(?:history|hpi|history of present illness)[:\s]*([^\n.]*)',
        'examination': r'(?:physical exam|examination|pe)[:\s]*([^\n.]*)'
    }
    
    for section_name, pattern in patterns.items():
        match = re.search(pattern, text_lower)
        if match:
            sections[section_name] = match.group(1).strip()
    
    return sections

def extract_key_medical_info(text: str) -> Dict[str, Any]:
    """
    Extract key medical information from text including test values, diagnoses, etc.
    
    Args:
        text (str): Medical record text
    
    Returns:
        Dict[str, Any]: Dictionary of extracted medical information
    """
    info = {
        'test_values': [],
        'diagnoses': [],
        'medications': [],
        'patient_info': {},
        'dates': [],
        'measurements': []
    }
    
    if not text:
        return info
    
    # Extract test values (e.g., "URIC ACID 5.7 mg/dl")
    test_pattern = r'([A-Z][A-Z\s]+(?:ACID|LEVEL|COUNT|RATE|TEST))[\s:]*([0-9.]+)\s*([a-z/]+)?'
    for match in re.finditer(test_pattern, text):
        test_name = match.group(1).strip()
        value = match.group(2)
        unit = match.group(3) if match.group(3) else ""
        info['test_values'].append(f"{test_name}: {value} {unit}".strip())
    
    # Extract patient ID/UMID
    umid_pattern = r'(?:UMID|Patient\s*ID|MRN)[\s:]*([A-Z0-9.]+)'
    umid_match = re.search(umid_pattern, text, re.IGNORECASE)
    if umid_match:
        info['patient_info']['id'] = umid_match.group(1).strip()
    
    # Extract dates
    date_pattern = r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b'
    dates = re.findall(date_pattern, text)
    if dates:
        info['dates'] = dates[:3]  # Keep first 3 dates
    
    # Extract doctor names
    doctor_pattern = r'(?:Dr\.?|Doctor)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    doctor_match = re.search(doctor_pattern, text)
    if doctor_match:
        info['patient_info']['doctor'] = doctor_match.group(1).strip()
    
    # Extract facility/hospital name
    facility_pattern = r'(?:Hospital|Facility|Clinic|Center)[\s:]*([A-Z][A-Za-z\s,]+?)(?:\n|$|,)'
    facility_match = re.search(facility_pattern, text)
    if facility_match:
        info['patient_info']['facility'] = facility_match.group(1).strip()
    
    return info

def create_clinical_summary(ai_summary: str, key_info: Dict[str, Any]) -> str:
    """
    Create a proper clinical summary combining AI summary with key extracted info
    
    Args:
        ai_summary (str): AI-generated summary text
        key_info (Dict): Extracted key medical information
    
    Returns:
        str: Formatted clinical summary
    """
    summary_parts = []
    
    # Add patient context if available
    if key_info.get('patient_info'):
        patient_info = key_info['patient_info']
        context = []
        if patient_info.get('id'):
            context.append(f"Patient ID: {patient_info['id']}")
        if patient_info.get('doctor'):
            context.append(f"Attending Physician: Dr. {patient_info['doctor']}")
        if patient_info.get('facility'):
            context.append(f"Facility: {patient_info['facility']}")
        if context:
            summary_parts.append(" | ".join(context))
    
    # Add AI summary (truncated if too long)
    clean_summary = ai_summary.strip()
    if len(clean_summary) > 500:
        # Extract first few sentences
        sentences = re.split(r'[.!?]+', clean_summary)
        clean_summary = '. '.join(sentences[:3]) + '.'
    summary_parts.append(clean_summary)
    
    # Add key test values if available
    if key_info.get('test_values'):
        test_summary = "Key Test Results: " + "; ".join(key_info['test_values'][:5])
        summary_parts.append(test_summary)
    
    return "\n".join(summary_parts)

def create_assessment_section(key_info: Dict[str, Any], original_text: str) -> str:
    """
    Create assessment section from extracted information
    
    Args:
        key_info (Dict): Extracted medical information
        original_text (str): Original medical text
    
    Returns:
        str: Assessment section text
    """
    assessment_parts = []
    
    # Look for diagnostic keywords in the original text
    diagnostic_terms = ['diagnosis', 'condition', 'disease', 'syndrome', 'disorder', 'infection']
    text_lower = original_text.lower()
    
    # Find sentences containing diagnostic terms
    sentences = re.split(r'[.!?]+', original_text)
    relevant_sentences = []
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(term in sentence_lower for term in diagnostic_terms):
            # Clean the sentence
            clean_sentence = sentence.strip()
            if len(clean_sentence) > 20 and len(clean_sentence) < 300:
                relevant_sentences.append(clean_sentence)
                if len(relevant_sentences) >= 2:
                    break
    
    if relevant_sentences:
        assessment_parts.extend(relevant_sentences)
    else:
        # Fallback: Extract based on test results
        if key_info.get('test_values'):
            assessment_parts.append("Laboratory investigation completed with documented findings.")
            if any('URIC ACID' in test for test in key_info['test_values']):
                assessment_parts.append("Uric acid levels assessed for metabolic evaluation.")
        else:
            assessment_parts.append("Clinical assessment based on documented findings and patient presentation.")
    
    return " ".join(assessment_parts) if assessment_parts else "Assessment pending review of complete clinical data."

def create_plan_section(key_info: Dict[str, Any], original_text: str) -> str:
    """
    Create plan/recommendations section
    
    Args:
        key_info (Dict): Extracted medical information
        original_text (str): Original medical text
    
    Returns:
        str: Plan section text
    """
    plan_parts = []
    
    # Look for plan-related keywords
    plan_keywords = ['treatment', 'plan', 'recommendation', 'follow-up', 'monitor', 'therapy', 'medication']
    text_lower = original_text.lower()
    
    # Find sentences containing plan keywords
    sentences = re.split(r'[.!?]+', original_text)
    relevant_sentences = []
    
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(keyword in sentence_lower for keyword in plan_keywords):
            clean_sentence = sentence.strip()
            if len(clean_sentence) > 20 and len(clean_sentence) < 300:
                relevant_sentences.append(clean_sentence)
                if len(relevant_sentences) >= 2:
                    break
    
    if relevant_sentences:
        plan_parts.extend(relevant_sentences)
    else:
        # Generate generic but appropriate plan
        if key_info.get('test_values'):
            plan_parts.append("Continue monitoring of laboratory values and clinical status.")
            plan_parts.append("Follow-up as clinically indicated based on test results.")
        else:
            plan_parts.append("Continue current management plan.")
            plan_parts.append("Follow-up appointment as recommended by treating physician.")
    
    return " ".join(plan_parts) if plan_parts else "Treatment plan to be determined by attending physician based on clinical assessment."

def summarize_with_metadata(input_text: str, max_length: int = 150, min_length: int = 30) -> Dict[str, Any]:
    """
    Summarize text and return additional metadata
    
    Args:
        input_text (str): Text to summarize
        max_length (int): Maximum summary length
        min_length (int): Minimum summary length
    
    Returns:
        Dict[str, Any]: Summary with metadata
    """
    summarizer = get_summarizer()
    summary = summarizer.summarize_text(input_text, max_length, min_length)
    
    return {
        "summary": summary,
        "original_length": len(input_text),
        "summary_length": len(summary),
        "compression_ratio": len(summary) / len(input_text) if input_text else 0,
        "model_info": summarizer.get_model_info(),
        "timestamp": datetime.now().isoformat()
    }

# Example usage and testing
if __name__ == "__main__":
    # Test the summarization function
    test_text = """
    Artificial intelligence (AI) is intelligence demonstrated by machines, 
    in contrast to the natural intelligence displayed by humans and animals. 
    Leading AI textbooks define the field as the study of "intelligent agents": 
    any device that perceives its environment and takes actions that maximize 
    its chance of successfully achieving its goals. Colloquially, the term 
    "artificial intelligence" is often used to describe machines that mimic 
    "cognitive" functions that humans associate with the human mind, such as 
    "learning" and "problem solving". As machines become increasingly capable, 
    tasks considered to require "intelligence" are often removed from the 
    definition of AI, a phenomenon known as the AI effect. A quip in Tesler's 
    Theorem says "AI is whatever hasn't been done yet." For instance, optical 
    character recognition is frequently excluded from things considered to be 
    AI, having become a routine technology.
    """
    
    print("Testing LLM Integration for Text Summarization")
    print("=" * 50)
    
    # Test basic summarization
    print("Original text length:", len(test_text))
    summary = summarize_text(test_text)
    print("Summary:", summary)
    print("Summary length:", len(summary))
    
    # Test with metadata
    print("\n" + "=" * 50)
    result_with_metadata = summarize_with_metadata(test_text)
    print("Summary with metadata:")
    for key, value in result_with_metadata.items():
        print(f"{key}: {value}")