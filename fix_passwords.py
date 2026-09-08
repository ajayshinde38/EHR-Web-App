#!/usr/bin/env python3
"""
Fix user passwords for test accounts
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.database import get_users_collection
from utils.auth import hash_password
from bson import ObjectId

def fix_user_passwords():
    """Reset passwords for test users"""
    print("Fixing user passwords...")
    
    users_collection = get_users_collection()
    
    # Users to fix
    test_users = [
        {"username": "patient1", "password": "password123"},
        {"username": "doctor1", "password": "password123"},
        {"username": "admin1", "password": "password123"}
    ]
    
    for user_info in test_users:
        user = users_collection.find_one({"username": user_info["username"]})
        
        if user:
            # Hash the new password
            new_password_hash = hash_password(user_info["password"])
            
            # Update the user's password
            result = users_collection.update_one(
                {"_id": user["_id"]},
                {"$set": {"password": new_password_hash}}
            )
            
            if result.modified_count > 0:
                print(f"✓ Updated password for {user_info['username']}")
            else:
                print(f"⚠️  Password for {user_info['username']} was already correct")
        else:
            print(f"✗ User {user_info['username']} not found")
    
    print("Password fix completed!")

if __name__ == "__main__":
    fix_user_passwords()