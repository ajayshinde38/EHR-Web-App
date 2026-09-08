#!/usr/bin/env python3
"""
Fix existing medical records with missing titles and dates
"""

from utils.database import init_db
from datetime import datetime

def fix_existing_records():
    """Fix records with None titles and dates"""
    try:
        db = init_db()
        collection = db['medical_records']
        
        # Find records with None title or record_date
        records_to_fix = list(collection.find({
            "$or": [
                {"title": None},
                {"record_date": None}
            ]
        }))
        
        print(f"Found {len(records_to_fix)} records to fix")
        
        if not records_to_fix:
            print("No records need fixing!")
            return
        
        fixed_count = 0
        
        for i, record in enumerate(records_to_fix):
            record_id = record['_id']
            updates = {}
            
            # Fix title if None
            if record.get('title') is None:
                record_type = record.get('record_type', 'Medical Record')
                # Generate title based on content or type
                content = record.get('content', '')
                if len(content) > 0:
                    # Try to extract first meaningful line as title
                    lines = content.split('\n')
                    meaningful_line = None
                    for line in lines:
                        line = line.strip()
                        if len(line) > 5 and not line.startswith('OCR') and not line.startswith('─'):
                            meaningful_line = line[:50]  # Limit to 50 chars
                            break
                    
                    if meaningful_line:
                        updates['title'] = meaningful_line
                    else:
                        updates['title'] = f"{record_type} #{i+1}"
                else:
                    updates['title'] = f"{record_type} #{i+1}"
            
            # Fix record_date if None
            if record.get('record_date') is None:
                # Use created_at as fallback
                created_at = record.get('created_at')
                if created_at:
                    if isinstance(created_at, str) and len(created_at) >= 10:
                        updates['record_date'] = created_at[:10]
                    elif hasattr(created_at, 'strftime'):
                        updates['record_date'] = created_at.strftime('%Y-%m-%d')
                    else:
                        updates['record_date'] = datetime.now().strftime('%Y-%m-%d')
                else:
                    updates['record_date'] = datetime.now().strftime('%Y-%m-%d')
            
            # Update the record
            if updates:
                result = collection.update_one(
                    {"_id": record_id},
                    {"$set": updates}
                )
                
                if result.modified_count > 0:
                    fixed_count += 1
                    print(f"Fixed record {i+1}: Title='{updates.get('title', 'unchanged')}', Date='{updates.get('record_date', 'unchanged')}'")
                else:
                    print(f"Failed to fix record {i+1}")
        
        print(f"\nSuccessfully fixed {fixed_count} out of {len(records_to_fix)} records")
        
        # Verify the fixes
        print("\nVerifying fixes...")
        remaining_issues = list(collection.find({
            "$or": [
                {"title": None},
                {"record_date": None}
            ]
        }))
        
        if len(remaining_issues) == 0:
            print("✅ All records now have proper titles and dates!")
        else:
            print(f"⚠️ {len(remaining_issues)} records still have issues")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_existing_records()