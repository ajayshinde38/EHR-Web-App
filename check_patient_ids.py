#!/usr/bin/env python3
"""
Check what patient IDs exist in database
"""

from utils.database import init_db

def check_patient_ids():
    """Check what patient IDs exist"""
    try:
        db = init_db()
        collection = db['medical_records']
        
        records = list(collection.find({}))
        print(f"Total records: {len(records)}")
        print("=" * 50)
        
        if records:
            for i, record in enumerate(records[:5]):
                print(f"Record {i+1}:")
                print(f"  Patient ID: {record.get('patient_id')}")
                print(f"  Title: {record.get('title')}")
                print(f"  Record Date: {record.get('record_date')}")
                print(f"  Record Type: {record.get('record_type')}")
                print(f"  Created At: {record.get('created_at')}")
                print("-" * 30)
        else:
            print("No records found in database")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_patient_ids()