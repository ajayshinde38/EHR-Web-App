"""
Authentication utilities for EHR Web App
Handles user authentication, role checking, and session management
"""

import streamlit as st
import bcrypt
import logging
from datetime import datetime
from utils.database import get_users_collection
from bson import ObjectId

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed) -> bool:
    """
    Verify a password against its hash
    
    Args:
        password (str): Plain text password
        hashed: Hashed password (can be str or bytes)
        
    Returns:
        bool: True if password matches
    """
    try:
        # Handle both string and bytes formats for backward compatibility
        if isinstance(hashed, str):
            hashed_bytes = hashed.encode('utf-8')
        elif isinstance(hashed, bytes):
            hashed_bytes = hashed
        else:
            logger.error(f"Invalid hash type: {type(hashed)}")
            return False
            
        return bcrypt.checkpw(password.encode('utf-8'), hashed_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False

def authenticate_user(username: str, password: str) -> dict:
    """
    Authenticate a user with username and password
    
    Args:
        username (str): Username
        password (str): Password
        
    Returns:
        dict: User data if authenticated, None if failed
    """
    try:
        users_collection = get_users_collection()
        user = users_collection.find_one({"username": username})
        
        if user and verify_password(password, user.get('password', '')):
            logger.info(f"User {username} authenticated successfully")
            return {
                'id': str(user['_id']),
                'username': user['username'],
                'email': user.get('email', ''),
                'role': user.get('role', 'patient'),
                'full_name': user.get('full_name', ''),
                'created_at': user.get('created_at', '')
            }
        else:
            logger.warning(f"Authentication failed for user {username}")
            return None
            
    except Exception as e:
        logger.error(f"Authentication error for {username}: {str(e)}")
        return None

def create_user(username: str, email: str, password: str, role: str = 'patient', full_name: str = '') -> bool:
    """
    Create a new user
    
    Args:
        username (str): Username
        email (str): Email address
        password (str): Plain text password
        role (str): User role (patient, doctor, admin)
        full_name (str): Full name
        
    Returns:
        bool: True if user created successfully
    """
    try:
        users_collection = get_users_collection()
        
        # Check if user already exists
        if users_collection.find_one({"username": username}):
            logger.warning(f"User {username} already exists")
            return False
        
        if users_collection.find_one({"email": email}):
            logger.warning(f"Email {email} already registered")
            return False
        
        # Create user document
        user_doc = {
            'username': username,
            'email': email,
            'password': hash_password(password),
            'role': role,
            'full_name': full_name,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'is_active': True
        }
        
        result = users_collection.insert_one(user_doc)
        if result.inserted_id:
            logger.info(f"User {username} created successfully")
            return True
        else:
            logger.error(f"Failed to create user {username}")
            return False
            
    except Exception as e:
        logger.error(f"Error creating user {username}: {str(e)}")
        return False

def check_user_role(required_role: str) -> bool:
    """
    Check if the current user has the required role
    
    Args:
        required_role (str): Required role
        
    Returns:
        bool: True if user has required role
    """
    if 'user_role' not in st.session_state:
        return False
    
    user_role = st.session_state.user_role
    
    # Admin can access everything
    if user_role == 'admin':
        return True
    
    # Check specific role
    return user_role == required_role

def get_current_user() -> dict:
    """
    Get current user data from session state
    
    Returns:
        dict: Current user data or None
    """
    if 'user_data' in st.session_state:
        return st.session_state.user_data
    return None

def logout_user():
    """
    Logout the current user by clearing session state
    """
    # Clear all session state variables
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    logger.info("User logged out successfully")

def is_authenticated() -> bool:
    """
    Check if user is currently authenticated
    
    Returns:
        bool: True if authenticated
    """
    return 'user_data' in st.session_state and st.session_state.user_data is not None

def require_authentication():
    """
    Decorator/function to require authentication for a page
    Redirects to login if not authenticated
    """
    if not is_authenticated():
        st.error("Please log in to access this page")
        st.stop()

def get_user_by_id(user_id: str) -> dict:
    """
    Get user data by user ID
    
    Args:
        user_id (str): User ID
        
    Returns:
        dict: User data or None
    """
    try:
        users_collection = get_users_collection()
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        
        if user:
            return {
                'id': str(user['_id']),
                'username': user['username'],
                'email': user.get('email', ''),
                'role': user.get('role', 'patient'),
                'full_name': user.get('full_name', ''),
                'created_at': user.get('created_at', '')
            }
        return None
        
    except Exception as e:
        logger.error(f"Error getting user by ID {user_id}: {str(e)}")
        return None

def get_all_users() -> list:
    """
    Get all users (admin only)
    
    Returns:
        list: List of all users
    """
    try:
        users_collection = get_users_collection()
        users = list(users_collection.find({}))
        
        # Convert ObjectId to string
        for user in users:
            user['id'] = str(user['_id'])
            del user['_id']
            # Remove password from response
            if 'password' in user:
                del user['password']
        
        return users
        
    except Exception as e:
        logger.error(f"Error getting all users: {str(e)}")
        return []

def update_user_profile(user_id: str, updates: dict) -> bool:
    """
    Update user profile
    
    Args:
        user_id (str): User ID
        updates (dict): Fields to update
        
    Returns:
        bool: True if updated successfully
    """
    try:
        users_collection = get_users_collection()
        
        # Add updated timestamp
        updates['updated_at'] = datetime.now()
        
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updates}
        )
        
        if result.modified_count > 0:
            logger.info(f"User {user_id} profile updated successfully")
            return True
        else:
            logger.warning(f"No changes made to user {user_id} profile")
            return False
            
    except Exception as e:
        logger.error(f"Error updating user {user_id} profile: {str(e)}")
        return False

def change_password(user_id: str, old_password: str, new_password: str) -> bool:
    """
    Change user password
    
    Args:
        user_id (str): User ID
        old_password (str): Current password
        new_password (str): New password
        
    Returns:
        bool: True if password changed successfully
    """
    try:
        users_collection = get_users_collection()
        user = users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            logger.error(f"User {user_id} not found")
            return False
        
        # Verify old password
        if not verify_password(old_password, user.get('password', '')):
            logger.warning(f"Old password verification failed for user {user_id}")
            return False
        
        # Update with new password
        new_hashed = hash_password(new_password)
        result = users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": new_hashed, "updated_at": datetime.now()}}
        )
        
        if result.modified_count > 0:
            logger.info(f"Password changed successfully for user {user_id}")
            return True
        else:
            logger.error(f"Failed to change password for user {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error changing password for user {user_id}: {str(e)}")
        return False

def get_users_by_role(role: str) -> list:
    """
    Get all users with a specific role
    
    Args:
        role (str): User role
        
    Returns:
        list: List of users with the specified role
    """
    try:
        users_collection = get_users_collection()
        users = list(users_collection.find({"role": role}))
        
        # Convert ObjectId to string and remove password
        for user in users:
            user['id'] = str(user['_id'])
            del user['_id']
            if 'password' in user:
                del user['password']
        
        return users
        
    except Exception as e:
        logger.error(f"Error getting users by role {role}: {str(e)}")
        return []
