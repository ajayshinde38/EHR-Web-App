#!/usr/bin/env python3
"""
Check medical records in database
"""

from utils.records import get_patient_records
import json

def check_records():
    """Check records structure"""
    # Get records for the test patient
    records = get_patient_records('test_patient_123')
    
    print(f"Found {len(records)} records")
    print("=" * 50)
    
    for i, record in enumerate(records):
        print(f"\nRecord {i+1}:")
        print(f"  Title: {record.get('title')}")
        print(f"  Record Date: {record.get('record_date')}")
        print(f"  Record Type: {record.get('record_type')}")
        print(f"  Created At: {record.get('created_at')}")
        print(f"  Content Length: {len(record.get('content', ''))}")
        print(f"  Keys: {list(record.keys())}")
        print("-" * 30)

if __name__ == "__main__":
    check_records()