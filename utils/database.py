"""
Database utilities for MongoDB connection and operations
"""
import pymongo
from pymongo import MongoClient
import streamlit as st
from config.settings import MONGODB_CONFIG
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@st.cache_resource
def init_db():
    """
    Initialize MongoDB connection
    Returns MongoDB database object
    """
    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_CONFIG["connection_string"])
        
        # Test connection
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        
        # Get database
        db = client[MONGODB_CONFIG["database_name"]]
        
        # Create indexes for better performance
        create_indexes(db)
        
        return db
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        st.error(f"Database connection failed: {str(e)}")
        return None

def create_indexes(db):
    """Create database indexes for better performance"""
    try:
        # Users collection indexes
        users_collection = db[MONGODB_CONFIG["collections"]["users"]]
        users_collection.create_index("username", unique=True)
        users_collection.create_index("email", unique=True)
        
        # Records collection indexes
        records_collection = db[MONGODB_CONFIG["collections"]["records"]]
        records_collection.create_index("patient_id")
        records_collection.create_index("uploaded_at")
        
        # Assignments collection indexes
        assignments_collection = db[MONGODB_CONFIG["collections"]["assignments"]]
        assignments_collection.create_index("doctor_id")
        assignments_collection.create_index("patient_ids")
        
        logger.info("Database indexes created successfully")
        
    except Exception as e:
        logger.warning(f"Failed to create indexes: {str(e)}")

def get_collection(collection_name):
    """Get a specific collection from the database"""
    try:
        db = init_db()
        if db is not None:
            return db[MONGODB_CONFIG["collections"][collection_name]]
        return None
    except Exception as e:
        logger.error(f"Error getting collection {collection_name}: {str(e)}")
        return None

def test_connection():
    """Test MongoDB connection"""
    try:
        client = MongoClient(MONGODB_CONFIG["connection_string"])
        client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False

# Collection helper functions
def get_users_collection():
    """Get users collection"""
    return get_collection("users")

def get_records_collection():
    """Get records collection"""
    return get_collection("records")

def get_assignments_collection():
    """Get assignments collection"""
    return get_collection("assignments")