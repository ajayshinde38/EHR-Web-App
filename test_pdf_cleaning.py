#!/usr/bin/env python3
"""
Test script for PDF text cleaning function
"""

def clean_text_for_pdf(text):
    """Clean and escape text content for PDF generation to prevent parsing errors"""
    if not text:
        return ""
    
    import html
    import re
    
    # Convert to string if not already
    text = str(text)
    
    # Remove or replace problematic HTML tags and characters
    # Replace self-closing tags that cause issues
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<hr\s*/?>', '\n---\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<img[^>]*>', '[IMAGE]', text, flags=re.IGNORECASE)
    
    # Remove other HTML tags but keep the content
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    
    # Escape HTML entities
    text = html.unescape(text)
    
    # Replace problematic Unicode characters that might cause PDF issues
    problematic_chars = {
        '\u019f': 'f',  # Replace ƒ with f
        '\u01a9': 't',  # Replace ƪ with t
        '\u2019': "'",  # Replace right single quotation mark
        '\u201c': '"',  # Replace left double quotation mark
        '\u201d': '"',  # Replace right double quotation mark
        '\u2013': '-',  # Replace en dash
        '\u2014': '--', # Replace em dash
        '\u2026': '...', # Replace ellipsis
    }
    
    for char, replacement in problematic_chars.items():
        text = text.replace(char, replacement)
    
    # Replace any remaining non-ASCII characters with their closest ASCII equivalent
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Clean up multiple whitespace characters
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # Limit line length to prevent very long lines
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        if len(line) > 100:
            # Break very long lines at word boundaries
            words = line.split()
            current_line = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 > 100 and current_line:
                    cleaned_lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word) + 1
            
            if current_line:
                cleaned_lines.append(' '.join(current_line))
        else:
            cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    
    return text.strip()

def test_text_cleaning():
    """Test the text cleaning function with problematic content"""
    
    # Sample problematic text (similar to what caused the error)
    problematic_text = """res.send('Login successful'); else res.send('Invalid creden ŧals'); }); }); // Serve HTML app.get('/', (req, res) => { res.sendFile(__dirname + '/index.html'); }); app.listen(3000, () => console.log('Server running on hŧtp://localhost:3000') ); HTML Form <!DOCTYPE html> <html> <head> <ŧitle>Simple Login</ŧitle> </head> <body> <h2>Login Form</h2> <form id="loginForm"> <input id="username" placeholder="Username" required /><br><br> <input id="password" type="password" placeholder="Password" required /><br><br> <buŧton type="submit">Login</buŧton> </form> <p id="result"></p> <script> const form = document.getElementById('loginForm'); form.addEventListener('submit', async e => { e.preventDefault(); const username = document.getElementById('username').value; const password = document.getElementById('password').value; const res = await fetch('/login', { method: 'POST', headers: { 'Content- Type': 'applicaŧon/json' }, body: JSON.stringify({ username, password }) }); const text = await res.text(); document.getElementById('result').innerText = text; }); </script> </body> </html> To Run this : Node server.js"""
    
    print("🧪 Testing PDF Text Cleaning Function")
    print("=" * 60)
    
    print("Original text (first 200 chars):")
    print(repr(problematic_text[:200]))
    print()
    
    # Clean the text
    cleaned_text = clean_text_for_pdf(problematic_text)
    
    print("Cleaned text (first 200 chars):")
    print(repr(cleaned_text[:200]))
    print()
    
    print("Full cleaned text:")
    print("-" * 40)
    print(cleaned_text)
    print("-" * 40)
    
    # Test if it's safe for ReportLab
    try:
        # Try to create a simple paragraph with the cleaned text
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import getSampleStyleSheet
        
        styles = getSampleStyleSheet()
        para = Paragraph(cleaned_text[:500], styles['Normal'])  # Test first 500 chars
        
        print("✅ SUCCESS: Cleaned text is safe for ReportLab Paragraph creation!")
        print(f"Paragraph object created successfully: {type(para)}")
        
    except ImportError:
        print("⚠️  ReportLab not available for testing, but text cleaning completed successfully")
    except Exception as e:
        print(f"❌ ERROR: Cleaned text still causes issues: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_text_cleaning()