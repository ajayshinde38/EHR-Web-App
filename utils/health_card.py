"""
Health Card Generation and Management System
Generates unique health cards with QR codes for patients
"""
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import uuid
import pyotp
import json
import base64
import os
from datetime import datetime, timedelta
import streamlit as st
from utils.database import init_db
import logging
from bson import ObjectId

# Load environment variables
from dotenv import load_dotenv
load_dotenv()
import base64

logger = logging.getLogger(__name__)

class HealthCardGenerator:
    def __init__(self):
        self.card_width = 856  # Increased width for better layout
        self.card_height = 540
        self.db = init_db()
        
    def generate_unique_patient_id(self):
        """Generate a unique patient health ID"""
        # Format: HC-YYYY-NNNNNN (Health Card - Year - 6 digit number)
        year = datetime.now().year
        unique_part = str(uuid.uuid4().int)[:6]
        return f"HC-{year}-{unique_part}"
    
    def get_patient_health_card(self, patient_id):
        """Get existing health card for a patient"""
        try:
            collection = self.db.health_cards
            card = collection.find_one({"patient_id": patient_id, "archived": {"$ne": True}})
            return card
        except Exception as e:
            logger.error(f"Error getting patient health card: {str(e)}")
            return None
    
    def archive_health_card(self, patient_id):
        """Archive existing health card when updating"""
        try:
            collection = self.db.health_cards
            result = collection.update_one(
                {"patient_id": patient_id, "archived": {"$ne": True}},
                {"$set": {"archived": True, "archived_at": datetime.now().isoformat()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error archiving health card: {str(e)}")
            return False
    
    def generate_health_card(self, patient_id, patient_name, date_of_birth, address, mobile_number, 
                           profile_photo=None, emergency_contact=None, blood_group=None):
        """Generate a new health card for a patient (one per patient only)"""
        try:
            # Check if patient already has an active health card
            existing_card = self.get_patient_health_card(patient_id)
            if existing_card:
                return {
                    "success": False,
                    "error": "Patient already has an active health card. Please update the existing card instead."
                }
            
            # Generate unique health card ID
            health_card_id = self.generate_unique_patient_id()
            
            # Process profile photo if provided
            processed_photo = None
            if profile_photo is not None:
                try:
                    # Handle different types of photo input
                    if hasattr(profile_photo, 'read'):  # File upload from Streamlit
                        photo_data = profile_photo.read()
                        processed_photo = Image.open(io.BytesIO(photo_data))
                    elif isinstance(profile_photo, Image.Image):  # Already a PIL Image
                        processed_photo = profile_photo
                    else:
                        logger.warning(f"Unsupported profile photo type: {type(profile_photo)}")
                except Exception as e:
                    logger.error(f"Error processing profile photo: {e}")
                    processed_photo = None
            
            # Prepare patient data
            patient_data = {
                "patient_id": patient_id,
                "health_card_id": health_card_id,
                "full_name": patient_name,
                "patient_name": patient_name,  # For compatibility
                "date_of_birth": date_of_birth,
                "address": address,
                "mobile_number": mobile_number,
                "emergency_contact": emergency_contact or "",
                "blood_group": blood_group or ""
            }
            
            # Generate QR code
            qr_img, qr_data = self.generate_qr_code(patient_data)
            if not qr_img or not qr_data:
                return {
                    "success": False,
                    "error": "Failed to generate QR code"
                }
            
            # Save to database
            collection = self.db.health_cards
            
            # Handle profile photo storage
            profile_photo_data = None
            if processed_photo:
                try:
                    # Convert PIL Image to base64 string for storage
                    photo_buffer = io.BytesIO()
                    processed_photo.save(photo_buffer, format='PNG')
                    photo_buffer.seek(0)
                    profile_photo_data = base64.b64encode(photo_buffer.getvalue()).decode('utf-8')
                except Exception as e:
                    logger.error(f"Error processing profile photo for storage: {e}")
            
            card_data = {
                "health_card_id": health_card_id,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "date_of_birth": date_of_birth,
                "address": address,
                "mobile_number": mobile_number,
                "emergency_contact": emergency_contact or "",
                "blood_group": blood_group or "",
                "profile_photo_data": profile_photo_data,  # Store photo data
                "qr_data": qr_data,
                "issued_date": datetime.now(),
                "validity_date": datetime.now() + timedelta(days=365*5),  # 5 years validity
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "archived": False
            }
            
            result = collection.insert_one(card_data)
            
            if result.inserted_id:
                return {
                    "success": True,
                    "health_card_id": health_card_id,
                    "card_data": card_data
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save health card to database"
                }
                
        except Exception as e:
            logger.error(f"Error generating health card: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def generate_qr_code(self, patient_data):
        """Generate QR code containing patient information"""
        try:
            # Create QR data with essential patient info
            qr_data = {
                "patient_id": patient_data.get("health_card_id"),
                "name": patient_data.get("full_name"),
                "dob": patient_data.get("date_of_birth"),
                "mobile": patient_data.get("mobile_number"),
                "emergency_contact": patient_data.get("emergency_contact"),
                "blood_group": patient_data.get("blood_group"),
                "generated": datetime.now().isoformat()
            }
            
            # Convert to JSON string
            qr_string = json.dumps(qr_data)
            
            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)
            
            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")
            return qr_img, qr_data
            
        except Exception as e:
            logger.error(f"QR code generation error: {e}")
            return None, None
    
    def create_health_card(self, patient_data, profile_photo=None):
        """Create a complete health card with all information"""
        try:
            # Try to get profile photo from patient_data if not provided
            if not profile_photo and patient_data.get('profile_photo_data'):
                try:
                    # Decode base64 profile photo
                    photo_data = base64.b64decode(patient_data['profile_photo_data'])
                    profile_photo = Image.open(io.BytesIO(photo_data))
                except Exception as e:
                    logger.error(f"Error loading stored profile photo: {e}")
                    profile_photo = None

            # Create card background with better dimensions
            card = Image.new('RGB', (self.card_width, self.card_height), color='white')
            draw = ImageDraw.Draw(card)

            # Larger font sizes for better visibility
            try:
                title_font = ImageFont.truetype("arial.ttf", 36)
                header_font = ImageFont.truetype("arial.ttf", 26)
                text_font = ImageFont.truetype("arial.ttf", 18)  # Main font slightly smaller
                small_font = ImageFont.truetype("arial.ttf", 16)
                label_font = ImageFont.truetype("arial.ttf", 18)
            except:
                # Fallback to default font
                title_font = ImageFont.load_default()
                header_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
                label_font = ImageFont.load_default()

            # Draw card border
            border_color = "#2E8B57"  # Sea Green
            draw.rectangle([10, 10, self.card_width-10, self.card_height-10], 
                          outline=border_color, width=3)

            # Draw header background (make it taller for title and subtitle)
            draw.rectangle([15, 15, self.card_width-15, 110], 
                          fill="#E8F5E8", outline=border_color, width=2)

            # Card title
            draw.text((30, 32), "DIGITAL HEALTH CARD", fill=border_color, font=title_font)
            # Place subtitle below title, but above the header line
            draw.text((30, 80), "Ministry of Health & Family Welfare", fill="#666666", font=small_font)

            # Patient photo area - larger size
            photo_x, photo_y = 30, 120
            photo_size = 180

            if profile_photo:
                try:
                    # Resize and paste profile photo
                    photo = profile_photo.resize((photo_size, photo_size))
                    card.paste(photo, (photo_x, photo_y))
                except:
                    # Draw placeholder if photo fails
                    draw.rectangle([photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], 
                                 outline="#CCCCCC", fill="#F0F0F0", width=2)
                    draw.text((photo_x + photo_size//2 - 40, photo_y + photo_size//2 - 20), "PHOTO", fill="#999999", font=text_font)
            else:
                # Draw photo placeholder
                draw.rectangle([photo_x, photo_y, photo_x + photo_size, photo_y + photo_size], 
                             outline="#CCCCCC", fill="#F0F0F0", width=2)
                draw.text((photo_x + photo_size//2 - 40, photo_y + photo_size//2 - 20), "PHOTO", fill="#999999", font=text_font)

            # Patient information - improved layout for larger fonts
            info_x = photo_x + photo_size + 40
            info_y = 120
            line_height = 40
            label_width = 180

            patient_info = [
                ("Name:", patient_data.get("full_name", patient_data.get("patient_name", "N/A"))),
                ("Health ID:", patient_data.get("health_card_id", "N/A")),
                ("Date of Birth:", patient_data.get("date_of_birth", "N/A")),
                ("Mobile Number:", patient_data.get("mobile_number", "N/A")),
                ("Blood Group:", patient_data.get("blood_group", "N/A")),
                ("Address:", self._format_address(patient_data.get("address", "N/A"))),
                ("Emergency Contact:", patient_data.get("emergency_contact", "N/A"))
            ]

            for i, (label, value) in enumerate(patient_info):
                y_pos = info_y + (i * line_height)
                draw.text((info_x, y_pos), label, fill="#333333", font=label_font)
                draw.text((info_x + label_width, y_pos), str(value), fill="#000000", font=text_font)

            # Generate and add QR code - much larger
            qr_img, qr_data = self.generate_qr_code(patient_data)
            if qr_img:
                qr_size = 220
                qr_x = self.card_width - qr_size - 40
                qr_y = 120
                qr_resized = qr_img.resize((qr_size, qr_size))
                card.paste(qr_resized, (qr_x, qr_y))
                draw.text((qr_x + 30, qr_y + qr_size + 18), "Scan QR Code", fill="#666666", font=header_font)
                draw.text((qr_x + 18, qr_y + qr_size + 48), "for Quick Access", fill="#666666", font=header_font)

            # Card footer - better spacing
            footer_y = self.card_height - 50
            draw.line([30, footer_y, self.card_width - 30, footer_y], fill="#CCCCCC", width=1)
            issue_date = datetime.now().strftime("%d/%m/%Y")
            validity_date = (datetime.now() + timedelta(days=365*5)).strftime("%d/%m/%Y")
            # Reduce font size for footer text to fit
            footer_font = small_font if small_font.size < 18 else ImageFont.truetype("arial.ttf", 14)
            draw.text((30, footer_y + 8), f"Issue Date: {issue_date}", fill="#666666", font=footer_font)
            draw.text((320, footer_y + 8), f"Valid Until: {validity_date}", fill="#666666", font=footer_font)
            draw.text((550, footer_y + 8), "This is a digitally generated health card", fill="#666666", font=footer_font)

            return card, qr_data
            
        except Exception as e:
            logger.error(f"Health card creation error: {e}")
            return None, None
    
    def _format_address(self, address):
        """Format address to fit on health card"""
        if not address or address == "N/A":
            return "N/A"
        
        # Limit address length to prevent overlapping
        if len(address) > 35:
            return address[:32] + "..."
        return address
    
    def save_health_card_data(self, patient_data, qr_data):
        """Save health card data to database"""
        try:
            health_cards_collection = self.db['health_cards']
            
            card_data = {
                "health_card_id": patient_data.get("health_card_id"),
                "patient_id": patient_data.get("patient_id"),
                "patient_name": patient_data.get("full_name"),
                "mobile_number": patient_data.get("mobile_number"),
                "qr_data": qr_data,
                "issued_date": datetime.now(),
                "validity_date": datetime.now() + timedelta(days=365*5),
                "status": "active",
                "created_at": datetime.now()
            }
            
            result = health_cards_collection.insert_one(card_data)
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Health card data save error: {e}")
            return None
    
    def get_patient_by_health_id(self, health_id):
        """Get patient data by health card ID"""
        try:
            health_cards_collection = self.db['health_cards']
            users_collection = self.db['users']
            records_collection = self.db['medical_records']
            
            # Find health card
            health_card = health_cards_collection.find_one({"health_card_id": health_id})
            if not health_card:
                return None
            
            # Find patient user data
            patient = users_collection.find_one({"_id": ObjectId(health_card["patient_id"])})
            if not patient:
                return None
            
            # Get patient's medical records
            records = list(records_collection.find({"patient_id": health_card["patient_id"]}))
            
            return {
                "health_card": health_card,
                "patient": patient,
                "medical_records": records
            }
            
        except Exception as e:
            logger.error(f"Patient lookup error: {e}")
            return None
    
    def get_patient_by_mobile(self, mobile_number):
        """Get patient data by mobile number"""
        try:
            health_cards_collection = self.db['health_cards']
            return health_cards_collection.find_one({"mobile_number": mobile_number})
            
        except Exception as e:
            logger.error(f"Mobile lookup error: {e}")
            return None

class OTPManager:
    def __init__(self):
        self.db = init_db()
        self.otp_length = 6
        self.otp_validity_minutes = 5
        self.max_attempts = 3
        
    def generate_otp(self, mobile_number, purpose="verification"):
        """Generate OTP for mobile verification with improved security"""
        try:
            import random
            import string
            
            # Generate secure 6-digit OTP
            otp = ''.join(random.choices(string.digits, k=self.otp_length))
            
            # Store OTP in database
            otp_collection = self.db['otp_verification']
            
            # Remove existing OTPs for this mobile
            otp_collection.delete_many({"mobile_number": mobile_number, "purpose": purpose})
            
            # Calculate expiry time
            expires_at = datetime.now() + timedelta(minutes=self.otp_validity_minutes)
            
            # Insert new OTP with enhanced data
            otp_data = {
                "mobile_number": mobile_number,
                "otp": otp,
                "purpose": purpose,
                "created_at": datetime.now(),
                "expires_at": expires_at,
                "verified": False,
                "attempts": 0,
                "max_attempts": self.max_attempts,
                "blocked": False
            }
            
            result = otp_collection.insert_one(otp_data)
            
            if result.inserted_id:
                # Send SMS OTP
                sms_sent = self.send_sms_otp(mobile_number, otp, purpose)
                
                return {
                    "success": True,
                    "otp": otp,  # Remove this in production
                    "expires_at": expires_at,
                    "sms_sent": sms_sent,
                    "message": f"OTP sent to {mobile_number}. Valid for {self.otp_validity_minutes} minutes."
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to generate OTP"
                }
            
        except Exception as e:
            logger.error(f"OTP generation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def verify_otp(self, mobile_number, otp, purpose="verification"):
        """Verify OTP for mobile number with attempt tracking"""
        try:
            otp_collection = self.db['otp_verification']
            
            # Find OTP record
            otp_record = otp_collection.find_one({
                "mobile_number": mobile_number,
                "purpose": purpose,
                "verified": False,
                "blocked": False,
                "expires_at": {"$gt": datetime.now()}
            })
            
            if not otp_record:
                return {
                    "success": False,
                    "error": "No valid OTP found or OTP expired"
                }
            
            # Check if max attempts exceeded
            if otp_record["attempts"] >= self.max_attempts:
                # Block this OTP
                otp_collection.update_one(
                    {"_id": otp_record["_id"]},
                    {"$set": {"blocked": True}}
                )
                return {
                    "success": False,
                    "error": "Maximum verification attempts exceeded. Please request a new OTP."
                }
            
            # Increment attempt count
            otp_collection.update_one(
                {"_id": otp_record["_id"]},
                {"$inc": {"attempts": 1}}
            )
            
            # Verify OTP
            if otp_record["otp"] == otp:
                # Mark as verified
                otp_collection.update_one(
                    {"_id": otp_record["_id"]},
                    {"$set": {"verified": True, "verified_at": datetime.now()}}
                )
                return {
                    "success": True,
                    "message": "OTP verified successfully"
                }
            else:
                remaining_attempts = self.max_attempts - otp_record["attempts"]
                return {
                    "success": False,
                    "error": f"Invalid OTP. {remaining_attempts} attempts remaining."
                }
            
        except Exception as e:
            logger.error(f"OTP verification error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def send_sms_otp(self, mobile_number, otp, purpose="verification"):
        """Send OTP via SMS with real SMS service integration"""
        try:
            # Format mobile number
            formatted_mobile = self._format_mobile_number(mobile_number)
            
            # Create message based on purpose
            if purpose == "verification":
                message = f"Your Health Card verification OTP is: {otp}. Valid for {self.otp_validity_minutes} minutes. Do not share this code. - EHR System"
            elif purpose == "access":
                message = f"Your Health Card access OTP is: {otp}. Valid for {self.otp_validity_minutes} minutes. Do not share this code. - EHR System"
            else:
                message = f"Your OTP is: {otp}. Valid for {self.otp_validity_minutes} minutes. Do not share this code. - EHR System"
            
            # Check if SMS is enabled
            sms_enabled = os.getenv('SMS_ENABLED', 'false').lower() == 'true'
            enable_sms_otp = os.getenv('ENABLE_SMS_OTP', 'false').lower() == 'true'
            demo_mode = os.getenv('DEMO_MODE', 'true').lower() == 'true'
            show_otp_in_ui = os.getenv('SHOW_OTP_IN_UI', 'true').lower() == 'true'
            
            # Try to send real SMS if either SMS_ENABLED or ENABLE_SMS_OTP is true
            if (sms_enabled or enable_sms_otp):
                logger.info(f"Attempting to send SMS OTP to {formatted_mobile}")
                # Production SMS sending
                sms_sent = self._send_real_sms(formatted_mobile, message)
                if sms_sent:
                    logger.info(f"SMS OTP sent successfully to {formatted_mobile}")
                    return True
                else:
                    logger.error(f"Failed to send SMS OTP to {formatted_mobile}")
                    # If SMS fails and we're in demo mode or show UI is enabled, log the OTP
                    if demo_mode or show_otp_in_ui:
                        logger.info(f"FALLBACK - SMS OTP {otp} for {formatted_mobile} ({purpose})")
                        logger.info(f"Message: {message}")
                    
                    # Store OTP failure reason for UI display
                    if hasattr(st, 'session_state'):
                        st.session_state['sms_error'] = "SMS delivery failed. Check phone number or try again."
                        st.session_state['fallback_otp'] = otp if (demo_mode or show_otp_in_ui) else None
                    
                    return False
            else:
                # Demo mode - log the OTP
                logger.info(f"DEMO MODE - SMS OTP {otp} for {formatted_mobile} ({purpose})")
                logger.info(f"Message: {message}")
                return True
            
        except Exception as e:
            logger.error(f"SMS sending error: {e}")
            return False
    
    def _send_real_sms(self, mobile_number, message):
        """Send real SMS using Twilio or other SMS service"""
        try:
            sms_provider = os.getenv('SMS_PROVIDER', 'twilio').lower()
            
            if sms_provider == 'twilio':
                return self._send_twilio_sms(mobile_number, message)
            elif sms_provider == 'aws':
                return self._send_aws_sns_sms(mobile_number, message)
            else:
                logger.error(f"Unsupported SMS provider: {sms_provider}")
                return False
                
        except Exception as e:
            logger.error(f"Real SMS sending error: {e}")
            return False
    
    def _send_twilio_sms(self, mobile_number, message):
        """Send SMS using Twilio service"""
        try:
            # Import Twilio
            from twilio.rest import Client
            
            # Get Twilio credentials from environment variables
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            from_number = os.getenv('TWILIO_PHONE_NUMBER')
            
            # Debug logging
            logger.info(f"Twilio SMS Debug - Attempting to send to: {mobile_number}")
            logger.info(f"Twilio credentials check - SID: {'SET' if account_sid else 'MISSING'}")
            logger.info(f"Twilio credentials check - Token: {'SET' if auth_token else 'MISSING'}")
            logger.info(f"Twilio credentials check - Phone: {from_number if from_number else 'MISSING'}")
            
            # Validate credentials
            if not account_sid or not auth_token or not from_number:
                logger.error("Twilio credentials not found in environment variables")
                logger.error("Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER")
                return False
            
            # Create Twilio client
            logger.info("Creating Twilio client...")
            client = Client(account_sid, auth_token)
            
            # Send SMS
            logger.info(f"Sending SMS from {from_number} to {mobile_number}")
            logger.info(f"Message content: {message[:50]}..." if len(message) > 50 else f"Message content: {message}")
            
            message_obj = client.messages.create(
                body=message,
                from_=from_number,
                to=mobile_number
            )
            
            # Log success
            logger.info(f"✅ Twilio SMS sent successfully!")
            logger.info(f"Message SID: {message_obj.sid}")
            logger.info(f"Message Status: {message_obj.status}")
            return True
            
        except ImportError as e:
            logger.error(f"❌ Twilio library not installed: {e}")
            logger.error("Run: pip install twilio")
            return False
        except Exception as e:
            error_message = str(e)
            logger.error(f"❌ Twilio SMS error: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Error details: {str(e)}")
            
            # Check for specific Twilio trial account errors
            if "21608" in error_message or "unverified" in error_message.lower():
                logger.warning("🔒 TWILIO TRIAL ACCOUNT LIMITATION DETECTED")
                logger.warning("📱 This phone number needs to be verified for trial accounts")
                logger.warning("💡 Solutions:")
                logger.warning("   1. Verify this phone number at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
                logger.warning("   2. Or upgrade to a paid Twilio account")
                logger.warning("   3. Or test with an already verified number")
            elif "21614" in error_message:
                logger.warning("🚫 INVALID PHONE NUMBER FORMAT")
                logger.warning("💡 Ensure phone number includes country code (e.g., +1234567890)")
            elif "20003" in error_message or "authentication" in error_message.lower():
                logger.warning("🔑 TWILIO AUTHENTICATION ERROR")
                logger.warning("💡 Check your Account SID and Auth Token in .env file")
            elif "21606" in error_message:
                logger.warning("📞 INVALID FROM NUMBER")
                logger.warning("💡 Check your Twilio phone number in .env file")
            
            return False
    
    def _send_aws_sns_sms(self, mobile_number, message):
        """Send SMS using AWS SNS service"""
        try:
            # Import AWS SDK
            import boto3
            
            # Create SNS client
            sns = boto3.client(
                'sns',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
            
            # Send SMS
            response = sns.publish(
                PhoneNumber=mobile_number,
                Message=message,
                MessageAttributes={
                    'AWS.SNS.SMS.SMSType': {
                        'DataType': 'String',
                        'StringValue': 'Transactional'
                    }
                }
            )
            
            logger.info(f"AWS SNS SMS sent successfully. MessageId: {response['MessageId']}")
            return True
            
        except ImportError:
            logger.error("AWS SDK not installed. Run: pip install boto3")
            return False
        except Exception as e:
            logger.error(f"AWS SNS SMS error: {e}")
            return False
    
    def _format_mobile_number(self, mobile_number):
        """Format mobile number to international format"""
        # Remove spaces and special characters
        clean_number = ''.join(filter(str.isdigit, str(mobile_number)))
        
        # Add country code if missing (assuming India +91)
        if len(clean_number) == 10:
            return f"+91{clean_number}"
        elif len(clean_number) == 12 and clean_number.startswith("91"):
            return f"+{clean_number}"
        elif mobile_number.startswith("+"):
            return mobile_number
        else:
            return f"+{clean_number}"
    
    def cleanup_expired_otps(self):
        """Clean up expired OTPs from database"""
        try:
            otp_collection = self.db['otp_verification']
            result = otp_collection.delete_many({
                "expires_at": {"$lt": datetime.now()}
            })
            logger.info(f"Cleaned up {result.deleted_count} expired OTPs")
            return result.deleted_count
        except Exception as e:
            logger.error(f"OTP cleanup error: {e}")
            return 0
    
    def get_otp_status(self, mobile_number, purpose="verification"):
        """Get current OTP status for a mobile number"""
        try:
            otp_collection = self.db['otp_verification']
            otp_record = otp_collection.find_one({
                "mobile_number": mobile_number,
                "purpose": purpose,
                "verified": False
            })
            
            if not otp_record:
                return {"status": "no_otp"}
            
            if otp_record.get("blocked", False):
                return {"status": "blocked"}
            
            if otp_record["expires_at"] < datetime.now():
                return {"status": "expired"}
            
            return {
                "status": "active",
                "attempts": otp_record["attempts"],
                "max_attempts": otp_record["max_attempts"],
                "expires_at": otp_record["expires_at"]
            }
            
        except Exception as e:
            logger.error(f"OTP status check error: {e}")
            return {"status": "error", "error": str(e)}

def convert_image_to_base64(image):
    """Convert PIL image to base64 string for storage/display"""
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return img_str

def decode_qr_code(qr_image):
    """Decode QR code from image"""
    try:
        from pyzbar import pyzbar
        import numpy as np
        
        # Convert PIL image to numpy array
        img_array = np.array(qr_image)
        
        # Decode QR code
        decoded_objects = pyzbar.decode(img_array)
        
        if decoded_objects:
            qr_data = decoded_objects[0].data.decode('utf-8')
            return json.loads(qr_data)
        
        return None
        
    except ImportError:
        st.warning("QR code scanning requires pyzbar library. Install with: pip install pyzbar")
        return None
    except Exception as e:
        logger.error(f"QR decode error: {e}")
        return None