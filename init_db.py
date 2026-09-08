"""
Database initialization script
Creates sample users and data for testing the EHR Web App
"""
import sys
import os
from datetime import datetime

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import init_db, get_users_collection, get_records_collection
from utils.auth import create_user
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize database with sample data"""
    try:
        # Initialize database connection
        db = init_db()
        if db is None:
            logger.error("Failed to connect to database")
            return False
        
        users_collection = get_users_collection()
        
        # Check if admin user exists
        admin_exists = users_collection.find_one({"username": "admin", "role": "admin"})
        
        if not admin_exists:
            logger.info("Creating default admin user...")
            
            # Create default admin
            if create_user("admin", "admin@ehr-app.com", "admin123", "admin"):
                logger.info("✅ Admin user created successfully!")
                logger.info("   Username: admin")
                logger.info("   Password: admin123")
            else:
                logger.error("❌ Failed to create admin user")
                return False
        else:
            logger.info("Admin user already exists")
        
        # Create sample doctor if not exists
        doctor_exists = users_collection.find_one({"username": "doctor1", "role": "doctor"})
        if not doctor_exists:
            logger.info("Creating sample doctor...")
            if create_user("doctor1", "doctor1@ehr-app.com", "doctor123", "doctor"):
                logger.info("✅ Sample doctor created!")
                logger.info("   Username: doctor1")
                logger.info("   Password: doctor123")
        
        # Create sample patient if not exists
        patient_exists = users_collection.find_one({"username": "patient1", "role": "patient"})
        if not patient_exists:
            logger.info("Creating sample patient...")
            if create_user("patient1", "patient1@ehr-app.com", "patient123", "patient"):
                logger.info("✅ Sample patient created!")
                logger.info("   Username: patient1")
                logger.info("   Password: patient123")
        
        logger.info("🎉 Database initialization completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        return False

def display_sample_accounts():
    """Display information about sample accounts"""
    print("\n" + "="*60)
    print("🏥 EHR WEB APP - SAMPLE ACCOUNTS")
    print("="*60)
    print("\n👨‍💼 ADMIN ACCOUNT:")
    print("   Username: admin")
    print("   Password: admin123")
    print("   Access: Full system administration")
    
    print("\n👨‍⚕️ DOCTOR ACCOUNT:")
    print("   Username: doctor1")
    print("   Password: doctor123")
    print("   Access: Patient management and records")
    
    print("\n👤 PATIENT ACCOUNT:")
    print("   Username: patient1")
    print("   Password: patient123")
    print("   Access: Personal medical records")
    
    print("\n🌐 APPLICATION URL:")
    print("   http://localhost:8501")
    
    print("\n📝 NEXT STEPS:")
    print("   1. Open the application in your browser")
    print("   2. Login with any of the accounts above")
    print("   3. Test the role-based features")
    print("   4. Upload medical records as a patient")
    print("   5. Assign patients to doctors as an admin")
    print("="*60)

if __name__ == "__main__":
    print("🚀 Initializing EHR Web App Database...")
    
    if initialize_database():
        display_sample_accounts()
    else:
        print("❌ Database initialization failed. Please check your MongoDB connection.")
        print("💡 Make sure MongoDB is running and the connection string in .env is correct.")