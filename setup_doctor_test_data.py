#!/usr/bin/env python3
"""
Script to assign test patients to doctors for testing the Doctor Dashboard
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import get_users_collection, get_assignments_collection
from bson import ObjectId
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def assign_test_patients():
    """Assign patient1 to doctor1 for testing"""
    try:
        users_collection = get_users_collection()
        assignments_collection = get_assignments_collection()
        
        # Find doctor1 and patient1
        doctor = users_collection.find_one({"username": "doctor1", "role": "doctor"})
        patient = users_collection.find_one({"username": "patient1", "role": "patient"})
        
        if not doctor:
            logger.error("doctor1 not found. Please create doctor1 account first.")
            return False
            
        if not patient:
            logger.error("patient1 not found. Please create patient1 account first.")
            return False
        
        doctor_id = str(doctor['_id'])
        patient_id = str(patient['_id'])
        
        logger.info(f"Assigning patient1 (ID: {patient_id}) to doctor1 (ID: {doctor_id})")
        
        # Add to doctor's assigned patients
        users_collection.update_one(
            {"_id": ObjectId(doctor_id)},
            {"$addToSet": {"assigned_patients": patient_id}}
        )
        
        # Create/update assignment record
        assignments_collection.update_one(
            {"doctor_id": doctor_id},
            {
                "$addToSet": {"patient_ids": patient_id},
                "$set": {
                    "updated_at": datetime.utcnow(),
                    "doctor_name": doctor['username'],
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        logger.info("✅ Successfully assigned patient1 to doctor1!")
        
        # Verify assignment
        updated_doctor = users_collection.find_one({"_id": ObjectId(doctor_id)})
        assigned_patients = updated_doctor.get('assigned_patients', [])
        logger.info(f"Doctor1 now has {len(assigned_patients)} assigned patients: {assigned_patients}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to assign patients: {str(e)}")
        return False

def create_sample_medical_records():
    """Create some sample medical records for patient1"""
    try:
        from utils.records import save_medical_record
        
        users_collection = get_users_collection()
        patient = users_collection.find_one({"username": "patient1", "role": "patient"})
        
        if not patient:
            logger.error("patient1 not found")
            return False
        
        patient_id = str(patient['_id'])
        
        # Sample medical records
        sample_records = [
            {
                'patient_id': patient_id,
                'content': """Patient presents with acute chest pain and shortness of breath. 
                Pain started 2 hours ago, described as sharp and radiating to left arm. 
                No previous cardiac history. Blood pressure: 150/90 mmHg. 
                Heart rate: 95 bpm. Oxygen saturation: 98% on room air.
                
                Assessment: Possible acute coronary syndrome
                Plan: ECG, cardiac enzymes, chest X-ray
                """,
                'record_type': 'Emergency Visit',
                'file_type': 'Clinical Notes',
                'file_name': 'emergency_visit_20251003.txt'
            },
            {
                'patient_id': patient_id,
                'content': """Follow-up visit for hypertension management.
                Patient reports good compliance with medications.
                Blood pressure today: 135/85 mmHg (improved from last visit).
                No side effects from current medications.
                
                Current medications:
                - Lisinopril 10mg daily
                - Hydrochlorothiazide 25mg daily
                
                Plan: Continue current regimen, recheck in 3 months
                """,
                'record_type': 'Follow-up Visit',
                'file_type': 'Clinical Notes', 
                'file_name': 'hypertension_followup_20251003.txt'
            },
            {
                'patient_id': patient_id,
                'content': """Laboratory Results:
                
                Complete Blood Count:
                - WBC: 7.2 K/uL (Normal: 4.5-11.0)
                - RBC: 4.5 M/uL (Normal: 4.5-5.9)
                - Hemoglobin: 14.2 g/dL (Normal: 14.0-18.0)
                - Hematocrit: 42% (Normal: 42-52)
                - Platelets: 250 K/uL (Normal: 150-450)
                
                Basic Metabolic Panel:
                - Glucose: 95 mg/dL (Normal: 70-100)
                - Sodium: 140 mEq/L (Normal: 136-145)
                - Potassium: 4.2 mEq/L (Normal: 3.5-5.0)
                - Creatinine: 1.0 mg/dL (Normal: 0.7-1.3)
                """,
                'record_type': 'Lab Results',
                'file_type': 'Laboratory Report',
                'file_name': 'lab_results_20251003.txt'
            }
        ]
        
        logger.info("Creating sample medical records...")
        
        for i, record in enumerate(sample_records):
            record_id = save_medical_record(record)
            if record_id:
                logger.info(f"✅ Created sample record {i+1}: {record_id}")
            else:
                logger.error(f"❌ Failed to create sample record {i+1}")
        
        logger.info("✅ Sample medical records created successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create sample records: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 Setting up test data for Doctor Dashboard...")
    
    # Assign patients to doctors
    if assign_test_patients():
        print("✅ Patient assignment completed")
    else:
        print("❌ Patient assignment failed")
    
    # Create sample medical records
    if create_sample_medical_records():
        print("✅ Sample medical records created")
    else:
        print("❌ Sample medical records creation failed")
    
    print("\n🎯 Test setup complete!")
    print("You can now login as doctor1 and test the Doctor Dashboard features:")
    print("- View assigned patients")
    print("- Search patients by ID or name")
    print("- View patient medical history with AI summaries")
    print("- Add doctor's notes to medical records")
    print("- Create new doctor observations")