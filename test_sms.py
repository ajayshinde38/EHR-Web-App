#!/usr/bin/env python3
"""
Simple SMS Test Script
Test your Twilio SMS configuration before using in the main app
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_sms_credentials():
    """Test if Twilio credentials are properly set"""
    print("🔍 Testing SMS Credentials...")
    print("=" * 50)
    
    # Check environment variables
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER')
    sms_enabled = os.getenv('SMS_ENABLED')
    enable_sms_otp = os.getenv('ENABLE_SMS_OTP')
    demo_mode = os.getenv('DEMO_MODE')
    
    print(f"TWILIO_ACCOUNT_SID: {'✅ SET' if account_sid else '❌ MISSING'}")
    if account_sid:
        print(f"  Value: AC...{account_sid[-6:]}")
    
    print(f"TWILIO_AUTH_TOKEN: {'✅ SET' if auth_token else '❌ MISSING'}")
    if auth_token:
        print(f"  Length: {len(auth_token)} characters")
    
    print(f"TWILIO_PHONE_NUMBER: {'✅ SET' if from_number else '❌ MISSING'}")
    if from_number:
        print(f"  Value: {from_number}")
    
    print(f"SMS_ENABLED: {sms_enabled}")
    print(f"ENABLE_SMS_OTP: {enable_sms_otp}")
    print(f"DEMO_MODE: {demo_mode}")
    
    return all([account_sid, auth_token, from_number])

def test_twilio_import():
    """Test if Twilio library is installed"""
    print("\n📦 Testing Twilio Library...")
    print("=" * 50)
    
    try:
        from twilio.rest import Client
        print("✅ Twilio library imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Twilio library not found: {e}")
        print("💡 Install with: pip install twilio")
        return False

def test_twilio_connection():
    """Test connection to Twilio API"""
    print("\n🌐 Testing Twilio Connection...")
    print("=" * 50)
    
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token:
            print("❌ Missing credentials for connection test")
            return False
        
        client = Client(account_sid, auth_token)
        
        # Try to fetch account details
        account = client.api.accounts(account_sid).fetch()
        print(f"✅ Connected to Twilio successfully")
        print(f"  Account SID: {account.sid}")
        print(f"  Account Status: {account.status}")
        print(f"  Account Type: {account.type}")
        
        return True
        
    except Exception as e:
        print(f"❌ Twilio connection failed: {e}")
        print("💡 Check your Account SID and Auth Token")
        return False

def send_test_sms():
    """Send a test SMS"""
    print("\n📱 Sending Test SMS...")
    print("=" * 50)
    
    # Get phone number from user
    to_number = input("Enter your phone number (with country code, e.g., +1234567890): ").strip()
    
    if not to_number.startswith('+'):
        print("❌ Phone number must include country code (e.g., +1234567890)")
        return False
    
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        from_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        client = Client(account_sid, auth_token)
        
        test_message = f"🧪 Test SMS from EHR System! Time: {os.popen('date /T').read().strip() if os.name == 'nt' else os.popen('date').read().strip()}"
        
        print(f"Sending SMS:")
        print(f"  From: {from_number}")
        print(f"  To: {to_number}")
        print(f"  Message: {test_message}")
        
        message = client.messages.create(
            body=test_message,
            from_=from_number,
            to=to_number
        )
        
        print(f"✅ SMS sent successfully!")
        print(f"  Message SID: {message.sid}")
        print(f"  Status: {message.status}")
        print("📱 Check your phone for the message!")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send SMS: {e}")
        return False

def main():
    """Run all SMS tests"""
    print("🚀 EHR System SMS Test")
    print("=" * 50)
    
    # Step 1: Check credentials
    if not test_sms_credentials():
        print("\n❌ SMS credentials are missing or incomplete")
        print("💡 Please check your .env file and ensure all Twilio variables are set")
        return
    
    # Step 2: Check Twilio library
    if not test_twilio_import():
        print("\n❌ Twilio library is not installed")
        return
    
    # Step 3: Test connection
    if not test_twilio_connection():
        print("\n❌ Cannot connect to Twilio API")
        return
    
    # Step 4: Send test SMS
    print("\n🎉 All checks passed! Ready to send test SMS.")
    
    while True:
        choice = input("\nDo you want to send a test SMS? (y/n): ").strip().lower()
        
        if choice == 'y':
            if send_test_sms():
                print("\n✅ Test completed successfully!")
            else:
                print("\n❌ Test SMS failed")
            break
        elif choice == 'n':
            print("\n👍 Test completed. SMS configuration is ready!")
            break
        else:
            print("Please enter 'y' or 'n'")

if __name__ == "__main__":
    main()