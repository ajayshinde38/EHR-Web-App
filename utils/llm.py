"""
LLM utilities for medical text summarization using Hugging Face
"""
import streamlit as st
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import transformers, but don't fail if not available
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    from config.settings import HUGGINGFACE_CONFIG
    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Transformers not available: {str(e)}. Using simple text processing.")
    TRANSFORMERS_AVAILABLE = False

logger = logging.getLogger(__name__)

@st.cache_resource
def load_summarization_model():
    """
    Load and cache the summarization model
    Returns:
        pipeline: Hugging Face summarization pipeline or None
    """
    if not TRANSFORMERS_AVAILABLE:
        logger.warning("Transformers not available, using simple summarization")
        return None
    
    try:
        from config.settings import HUGGINGFACE_CONFIG
        model_name = HUGGINGFACE_CONFIG["model_name"]
        
        # Check if GPU is available
        device = 0 if torch.cuda.is_available() else -1
        
        # Load model and tokenizer
        summarizer = pipeline(
            "summarization",
            model=model_name,
            device=device,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
        )
        
        logger.info(f"Summarization model {model_name} loaded successfully")
        return summarizer
        
    except Exception as e:
        logger.error(f"Failed to load summarization model: {str(e)}")
        return None

def preprocess_medical_text(text):
    """
    Preprocess medical text for better summarization
    Args:
        text: Raw medical text
    Returns:
        str: Preprocessed text
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters that might interfere
    text = re.sub(r'[^\w\s.,;:()\-/]', '', text)
    
    # Ensure text ends with proper punctuation
    if text and not text.strip().endswith(('.', '!', '?')):
        text = text.strip() + '.'
    
    return text.strip()

def simple_summarization(text, max_sentences=3):
    """
    Simple rule-based text summarization as fallback
    Args:
        text: Input text to summarize
        max_sentences: Maximum sentences in summary
    Returns:
        str: Simple summary
    """
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= max_sentences:
        return text
    
    # Simple scoring based on position and length
    scored_sentences = []
    for i, sentence in enumerate(sentences):
        score = 0
        # Prefer sentences with medical keywords
        medical_keywords = ['patient', 'diagnosis', 'treatment', 'symptoms', 'medication', 'condition']
        for keyword in medical_keywords:
            if keyword.lower() in sentence.lower():
                score += 2
        
        # Prefer sentences that are not too short or too long
        if 10 < len(sentence) < 200:
            score += 1
        
        # Prefer sentences near the beginning
        if i < len(sentences) / 3:
            score += 1
        
        scored_sentences.append((score, sentence))
    
    # Sort by score and take top sentences
    scored_sentences.sort(reverse=True, key=lambda x: x[0])
    top_sentences = [s[1] for s in scored_sentences[:max_sentences]]
    
    return '. '.join(top_sentences) + '.'
    """
    Split long text into chunks for processing
    Args:
        text: Input text
        max_length: Maximum length per chunk
    Returns:
        list: List of text chunks
    """
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_length:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                # Word is too long, split it
                chunks.append(word[:max_length])
                current_chunk = [word[max_length:]] if len(word) > max_length else []
                current_length = len(current_chunk[0]) if current_chunk else 0
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def chunk_text(text, max_length=1024):
    """
    Split long text into chunks for processing
    Args:
        text: Input text
        max_length: Maximum length per chunk
    Returns:
        list: List of text chunks
    """
    words = text.split()
    chunks = []
    current_chunk = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_length:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                # Word is too long, split it
                chunks.append(word[:max_length])
                current_chunk = [word[max_length:]] if len(word) > max_length else []
                current_length = len(current_chunk[0]) if current_chunk else 0
        else:
            current_chunk.append(word)
            current_length += len(word) + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks

def summarize_text(text, max_length=None, min_length=None):
    """
    Summarize medical text using Hugging Face model or simple fallback
    Args:
        text: Medical text to summarize
        max_length: Maximum length of summary
        min_length: Minimum length of summary
    Returns:
        str: Summarized text or None if failed
    """
    try:
        # Preprocess text
        processed_text = preprocess_medical_text(text)
        
        if not processed_text:
            return "No valid text to summarize."
        
        # Load model if available
        summarizer = load_summarization_model()
        
        if not summarizer or not TRANSFORMERS_AVAILABLE:
            # Use simple summarization as fallback
            logger.info("Using simple text summarization fallback")
            return simple_summarization(processed_text)
        
        # Use transformers model
        if max_length is None:
            from config.settings import HUGGINGFACE_CONFIG
            max_length = HUGGINGFACE_CONFIG["max_length"]
        if min_length is None:
            from config.settings import HUGGINGFACE_CONFIG
            min_length = HUGGINGFACE_CONFIG["min_length"]
        
        # Check if text is too long for model
        if len(processed_text) > 1024:
            # Process in chunks
            chunks = chunk_text(processed_text, 1000)
            summaries = []
            
            for chunk in chunks:
                if len(chunk.strip()) < 50:  # Skip very short chunks
                    continue
                    
                try:
                    result = summarizer(
                        chunk,
                        max_length=max_length // len(chunks) + 20,
                        min_length=min(min_length, len(chunk) // 4),
                        do_sample=False
                    )
                    summaries.append(result[0]['summary_text'])
                except Exception as e:
                    logger.warning(f"Failed to summarize chunk: {str(e)}")
                    continue
            
            # Combine summaries
            if summaries:
                combined_summary = ' '.join(summaries)
                
                # If combined summary is still too long, summarize again
                if len(combined_summary) > max_length * 2:
                    try:
                        final_result = summarizer(
                            combined_summary,
                            max_length=max_length,
                            min_length=min_length,
                            do_sample=False
                        )
                        return final_result[0]['summary_text']
                    except:
                        return combined_summary[:max_length * 2]
                
                return combined_summary
            else:
                return simple_summarization(processed_text)
        
        else:
            # Process normally
            result = summarizer(
                processed_text,
                max_length=max_length,
                min_length=min_length,
                do_sample=False
            )
            
            return result[0]['summary_text']
    
    except Exception as e:
        logger.error(f"Summarization failed: {str(e)}")
        # Fallback to simple summarization
        try:
            return simple_summarization(text)
        except:
            return f"Unable to generate summary: {str(e)}"

def extract_key_medical_info(text):
    """
    Extract key medical information from text
    Args:
        text: Medical text
    Returns:
        dict: Extracted medical information
    """
    info = {
        "symptoms": [],
        "medications": [],
        "conditions": [],
        "procedures": []
    }
    
    # Simple keyword extraction (can be enhanced with NER models)
    text_lower = text.lower()
    
    # Common medical keywords
    symptom_keywords = ['pain', 'fever', 'headache', 'nausea', 'fatigue', 'cough', 'shortness of breath']
    medication_keywords = ['tablet', 'mg', 'ml', 'prescription', 'dose', 'medication']
    condition_keywords = ['diabetes', 'hypertension', 'infection', 'syndrome', 'disease', 'disorder']
    procedure_keywords = ['surgery', 'procedure', 'examination', 'test', 'scan', 'biopsy']
    
    # Extract keywords
    for keyword in symptom_keywords:
        if keyword in text_lower:
            info["symptoms"].append(keyword)
    
    for keyword in medication_keywords:
        if keyword in text_lower:
            info["medications"].append(keyword)
    
    for keyword in condition_keywords:
        if keyword in text_lower:
            info["conditions"].append(keyword)
    
    for keyword in procedure_keywords:
        if keyword in text_lower:
            info["procedures"].append(keyword)
    
    return info

def generate_medical_insights(text):
    """
    Generate medical insights from text
    Args:
        text: Medical text
    Returns:
        dict: Medical insights
    """
    try:
        # Get summary
        summary = summarize_text(text)
        
        # Extract key information
        key_info = extract_key_medical_info(text)
        
        # Calculate text statistics
        word_count = len(text.split())
        char_count = len(text)
        
        insights = {
            "summary": summary,
            "key_information": key_info,
            "statistics": {
                "word_count": word_count,
                "character_count": char_count,
                "estimated_reading_time": max(1, word_count // 200)  # minutes
            },
            "generated_at": str(datetime.now())
        }
        
        return insights
        
    except Exception as e:
        logger.error(f"Failed to generate insights: {str(e)}")
        return {
            "summary": "Failed to generate summary",
            "key_information": {"symptoms": [], "medications": [], "conditions": [], "procedures": []},
            "statistics": {"word_count": 0, "character_count": 0, "estimated_reading_time": 0},
            "error": str(e)
        }