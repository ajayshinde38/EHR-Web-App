"""
Enhanced Doctor Dashboard - QR Code Scanning and OTP Patient Verification
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta
from bson import ObjectId
from PIL import Image
from utils.auth import check_user_role, get_current_user
from utils.database import get_users_collection, get_records_collection, get_assignments_collection
from utils.records import get_patient_records, save_medical_record, search_records
from utils.health_card import HealthCardGenerator, OTPManager, decode_qr_code
from utils.twilio_helper import show_trial_account_guidance, create_sms_status_indicator
from llm_integration import summarize_text
import logging

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Doctor Dashboard - EHR Web App",
    page_icon="👨‍⚕️",
    layout="wide"
)

def check_authentication():
    """Check if user is authenticated and has doctor role"""
    if not st.session_state.get('authenticated', False):
        st.error("Please login to access this page")
        st.stop()
    
    if not check_user_role('doctor') and st.session_state.user_role != 'admin':
        st.error("Access denied. This page is for doctors only.")
        st.stop()

def get_assigned_patients():
    """Get patients assigned to current doctor"""
    try:
        users_collection = get_users_collection()
        assignments_collection = get_assignments_collection()
        
        # First check if there's an assignment record
        assignment = assignments_collection.find_one({"doctor_id": st.session_state.user_id})
        
        if assignment and assignment.get('patient_ids'):
            patient_ids = assignment['patient_ids']
        else:
            # Check doctor's assigned_patients field
            doctor = users_collection.find_one({"_id": ObjectId(st.session_state.user_id)})
            patient_ids = doctor.get('assigned_patients', []) if doctor else []
        
        # Get patient details
        patients = []
        if patient_ids:
            patients = list(users_collection.find(
                {"_id": {"$in": [ObjectId(pid) for pid in patient_ids if ObjectId.is_valid(pid)]}}
            ))
        
        return patients
        
    except Exception as e:
        logger.error(f"Failed to get assigned patients: {str(e)}")
        return []

def search_patients():
    """Search patients by ID or name"""
    st.subheader("🔍 Search Patients")
    
    # Search input
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input(
            "Search by Patient ID or Name:",
            placeholder="Enter patient ID or name to search...",
            key="patient_search"
        )
    with col2:
        search_type = st.selectbox(
            "Search Type:",
            ["Name", "Patient ID", "Email"],
            key="search_type"
        )
    
    if search_term:
        try:
            users_collection = get_users_collection()
            
            # Build search query based on type
            if search_type == "Patient ID":
                if ObjectId.is_valid(search_term):
                    query = {"_id": ObjectId(search_term), "role": "patient"}
                else:
                    st.warning("Invalid Patient ID format")
                    return []
            elif search_type == "Name":
                query = {
                    "username": {"$regex": search_term, "$options": "i"},
                    "role": "patient"
                }
            else:  # Email
                query = {
                    "email": {"$regex": search_term, "$options": "i"},
                    "role": "patient"
                }
            
            # Execute search
            patients = list(users_collection.find(query))
            
            if patients:
                st.success(f"Found {len(patients)} patient(s)")
                
                # Display search results
                for patient in patients:
                    patient_id = str(patient['_id'])
                    records_count = get_patient_records_count(patient_id)
                    
                    with st.expander(f"👤 {patient['username']} (ID: {patient_id[:8]}...)"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Name:** {patient['username']}")
                            st.write(f"**Email:** {patient.get('email', 'Not provided')}")
                        with col2:
                            st.write(f"**Patient ID:** {patient_id}")
                            st.write(f"**Records:** {records_count}")
                        with col3:
                            if st.button(f"View Records", key=f"view_{patient_id}"):
                                st.session_state.selected_patient = patient_id
                                st.rerun()
                
                return patients
            else:
                st.info("No patients found matching your search criteria")
                return []
                
        except Exception as e:
            st.error(f"Search failed: {str(e)}")
            logger.error(f"Patient search failed: {str(e)}")
            return []
    
    return []

def get_patient_records_count(patient_id):
    """Get count of records for a patient"""
    try:
        records_collection = get_records_collection()
        return records_collection.count_documents({"patient_id": patient_id})
    except:
        return 0

def view_patient_medical_history(patient_id):
    """View complete medical history for a patient with LLM summaries"""
    try:
        # Get patient info
        users_collection = get_users_collection()
        patient = users_collection.find_one({"_id": ObjectId(patient_id)})
        
        if not patient:
            st.error("Patient not found")
            return
        
        st.subheader(f" Medical History: {patient['username']}")
        st.write(f"**Patient ID:** {patient_id}")
        st.write(f"**Email:** {patient.get('email', 'Not provided')}")
        
        # Get medical records
        records = get_patient_records(patient_id)
        
        if not records:
            st.info("No medical records found for this patient")
            return
        
        # Display records with enhanced information
        st.write(f"**Total Records:** {len(records)}")
        
        # Sort records by date (newest first)
        sorted_records = sorted(records, key=lambda x: x.get('timestamp', datetime.min), reverse=True)
        
        # Display each record
        for i, record in enumerate(sorted_records):
            record_date = record.get('timestamp', datetime.now()).strftime("%Y-%m-%d %H:%M")
            record_type = record.get('record_type', 'General')
            
            with st.expander(f" {record_type} - {record_date}", expanded=(i == 0)):
                # Record details
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**Original Content:**")
                    st.text_area(
                        "Medical Record",
                        value=record.get('content', 'No content'),
                        height=150,
                        disabled=True,
                        key=f"content_{record.get('_id')}"
                    )
                
                with col2:
                    st.write("**Record Information:**")
                    st.write(f"**Type:** {record_type}")
                    st.write(f"**Date:** {record_date}")
                    st.write(f"**File Type:** {record.get('file_type', 'Text')}")
                    if record.get('file_name'):
                        st.write(f"**File:** {record.get('file_name')}")
                
                # AI Summary
                if record.get('ai_summary'):
                    st.write("** AI Summary:**")
                    st.info(record.get('ai_summary'))
                
                # Doctor's notes section
                st.write("** Doctor's Notes:**")
                existing_notes = record.get('doctor_notes', '')
                
                new_notes = st.text_area(
                    "Add your professional notes:",
                    value=existing_notes,
                    height=100,
                    key=f"notes_{record.get('_id')}"
                )
                
                if st.button(f"💾 Save Notes", key=f"save_{record.get('_id')}"):
                    if update_doctor_notes(str(record.get('_id')), new_notes, st.session_state.user_id):
                        st.success("✅ Doctor's notes saved successfully!")
                        st.rerun()
                    else:
                        st.error(" Failed to save notes")
                
                st.divider()
    
    except Exception as e:
        st.error(f"Error loading patient history: {str(e)}")
        logger.error(f"Error loading patient history: {str(e)}")

def update_doctor_notes(record_id, notes, doctor_id):
    """Update doctor's notes for a medical record"""
    try:
        records_collection = get_records_collection()
        
        result = records_collection.update_one(
            {"_id": ObjectId(record_id)},
            {
                "$set": {
                    "doctor_notes": notes,
                    "last_reviewed_by": doctor_id,
                    "last_reviewed_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        logger.error(f"Failed to update doctor notes: {str(e)}")
        return False

def add_doctor_observation():
    """Add a new doctor's observation/note as a medical record"""
    st.subheader("📝 Add Doctor's Observation")
    
    # Get assigned patients for selection
    patients = get_assigned_patients()
    
    if not patients:
        st.warning("You need to have assigned patients to add observations")
        return
    
    # Patient selection
    patient_options = {
        f"{p['username']} (ID: {str(p['_id'])[:8]}...)": str(p['_id'])
        for p in patients
    }
    
    selected_patient_key = st.selectbox(
        "Select Patient:",
        options=list(patient_options.keys()),
        index=None,
        placeholder="Choose a patient...",
        key="obs_patient_select"
    )
    
    if selected_patient_key:
        patient_id = patient_options[selected_patient_key]
        
        # Observation form
        with st.form("doctor_observation_form"):
            observation_type = st.selectbox(
                "Observation Type:",
                ["Clinical Examination", "Follow-up Notes", "Treatment Plan", "Consultation Notes", "Progress Report"],
                key="obs_type"
            )
            
            observation_text = st.text_area(
                "Doctor's Observation:",
                placeholder="Enter your professional medical observation...",
                height=200,
                key="obs_text"
            )
            
            # Additional fields
            col1, col2 = st.columns(2)
            with col1:
                diagnosis = st.text_input("Diagnosis (optional):", key="obs_diagnosis")
            with col2:
                treatment = st.text_input("Treatment Plan (optional):", key="obs_treatment")
            
            submitted = st.form_submit_button("💾 Save Observation")
            
            if submitted and observation_text:
                try:
                    # Prepare the complete observation
                    complete_observation = f"""
DOCTOR'S OBSERVATION - {observation_type}
Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Doctor: {st.session_state.get('username', 'Unknown')}

OBSERVATION:
{observation_text}
"""
                    
                    if diagnosis:
                        complete_observation += f"\nDIAGNOSIS: {diagnosis}"
                    
                    if treatment:
                        complete_observation += f"\nTREATMENT PLAN: {treatment}"
                    
                    # Save as medical record
                    record_data = {
                        'patient_id': patient_id,
                        'content': complete_observation,
                        'record_type': f"Doctor's {observation_type}",
                        'file_type': 'Doctor Observation',
                        'file_name': f"Doctor_Observation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        'doctor_id': st.session_state.user_id,
                        'created_by_doctor': True
                    }
                    
                    if save_medical_record(record_data):
                        st.success("✅ Doctor's observation saved successfully!")
                        st.rerun()
                    else:
                        st.error(" Failed to save observation")
                        
                except Exception as e:
                    st.error(f" Error saving observation: {str(e)}")
                    logger.error(f"Error saving doctor observation: {str(e)}")
            
            elif submitted:
                st.warning("Please enter your observation text")

def display_assigned_patients_overview():
    """Display overview of assigned patients"""
    st.header("👥 Your Assigned Patients")
    
    patients = get_assigned_patients()
    
    if not patients:
        st.info("👥 No patients assigned yet.")
        return
    
    # Create patient overview cards
    cols = st.columns(min(len(patients), 3))
    
    for i, patient in enumerate(patients):
        patient_id = str(patient['_id'])
        records_count = get_patient_records_count(patient_id)
        
        with cols[i % 3]:
            with st.container():
                st.markdown(f"""
                <div style="border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin: 10px 0;">
                    <h4>👤 {patient['username']}</h4>
                    <p><strong>Patient ID:</strong> {patient_id[:12]}...</p>
                    <p><strong>Email:</strong> {patient.get('email', 'Not provided')}</p>
                    <p><strong>Medical Records:</strong> {records_count}</p>
                    <p><strong>Last Updated:</strong> {patient.get('updated_at', 'Unknown')}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"📋 View History", key=f"view_history_{patient_id}"):
                    st.session_state.selected_patient = patient_id
                    st.session_state.view_mode = "history"
                    st.rerun()

def qr_code_scanner():
    """QR Code scanning interface for patient health cards"""
    st.subheader("📱 QR Code Patient Scanner")
    st.write("Scan patient's health card QR code for instant access to medical records")
    
    # QR Code upload option
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.write("**📷 Upload QR Code Image**")
        qr_image_file = st.file_uploader(
            "Choose QR code image",
            type=['png', 'jpg', 'jpeg'],
            help="Upload a clear image of the patient's health card QR code"
        )
        
        if qr_image_file:
            # Display uploaded image
            qr_image = Image.open(qr_image_file)
            st.image(qr_image, caption="Uploaded QR Code", width=300)
            
            # Process QR code
            if st.button("🔍 Scan QR Code", type="primary"):
                with st.spinner("🔍 Processing QR code..."):
                    try:
                        # Decode QR code
                        qr_data = decode_qr_code(qr_image)
                        
                        if qr_data:
                            st.success("✅ QR Code scanned successfully!")
                            
                            # Display QR data
                            with st.expander(" QR Code Data", expanded=True):
                                col_a, col_b = st.columns(2)
                                
                                with col_a:
                                    st.write(f"**🆔 Patient ID:** {qr_data.get('patient_id', 'N/A')}")
                                    st.write(f"**👤 Name:** {qr_data.get('name', 'N/A')}")
                                    st.write(f"**📅 DOB:** {qr_data.get('dob', 'N/A')}")
                                
                                with col_b:
                                    st.write(f"**📱 Mobile:** {qr_data.get('mobile', 'N/A')}")
                                    st.write(f"**🩸 Blood Group:** {qr_data.get('blood_group', 'N/A')}")
                                    st.write(f"**🚨 Emergency:** {qr_data.get('emergency_contact', 'N/A')}")
                            
                            # Store QR data in session state for OTP verification
                            st.session_state.qr_patient_data = qr_data
                            st.session_state.show_otp_verification = True
                            
                            st.info("📱 **Next Step:** OTP verification required to access medical records")
                            st.rerun()
                            
                        else:
                            st.error(" Could not decode QR code. Please ensure the image is clear and contains a valid health card QR code.")
                            st.info(" **Tips for better scanning:**")
                            st.write("• Ensure good lighting")
                            st.write("• Keep the QR code flat and unobstructed")
                            st.write("• Use a high-resolution image")
                            
                    except Exception as e:
                        st.error(f" Error processing QR code: {str(e)}")
                        logger.error(f"QR code processing error: {e}")
    
    with col2:
        st.write("** Manual Health ID Entry**")
        st.write("Alternative: Enter patient's health card ID manually")
        
        health_id = st.text_input(
            "Health Card ID",
            placeholder="HC-2025-XXXXXX",
            help="Enter the health card ID printed on the card"
        )
        
        if health_id and st.button("🔍 Lookup Patient"):
            with st.spinner("🔍 Looking up patient..."):
                try:
                    card_generator = HealthCardGenerator()
                    patient_data = card_generator.get_patient_by_health_id(health_id)
                    
                    if patient_data:
                        st.success("✅ Patient found!")
                        
                        # Store patient data for OTP verification
                        qr_data = {
                            "patient_id": health_id,
                            "name": patient_data['health_card']['patient_name'],
                            "mobile": patient_data['health_card']['mobile_number']
                        }
                        
                        st.session_state.qr_patient_data = qr_data
                        st.session_state.show_otp_verification = True
                        st.rerun()
                    else:
                        st.error(" No patient found with this health card ID")
                        
                except Exception as e:
                    st.error(f" Error looking up patient: {str(e)}")

def otp_verification_interface():
    """OTP verification interface for patient access"""
    if not st.session_state.get('qr_patient_data'):
        st.warning("⚠️ No patient data found. Please scan QR code first.")
        return
    
    patient_data = st.session_state.qr_patient_data
    
    st.subheader("🔐 OTP Verification Required")
    st.write(f"**Patient:** {patient_data.get('name', 'Unknown')}")
    st.write(f"**Mobile:** {patient_data.get('mobile', 'Unknown')}")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # OTP generation
        if not st.session_state.get('otp_sent', False):
            if st.button("📱 Send OTP", type="primary", help="Send OTP to patient's mobile number"):
                with st.spinner("📱 Sending OTP..."):
                    try:
                        import os
                        from dotenv import load_dotenv
                        load_dotenv()
                        
                        otp_manager = OTPManager()
                        mobile = patient_data.get('mobile', '')
                        
                        if mobile:
                            otp_result = otp_manager.generate_otp(mobile, purpose="access")
                            
                            if otp_result["success"]:
                                # Store OTP session data
                                st.session_state.otp_sent = True
                                st.session_state.otp_expires_at = otp_result["expires_at"]
                                
                                # Show OTP in UI only if in demo mode
                                demo_mode = os.getenv('DEMO_MODE', 'true').lower() == 'true'
                                show_otp_in_ui = os.getenv('SHOW_OTP_IN_UI', 'true').lower() == 'true'
                                sms_enabled = os.getenv('SMS_ENABLED', 'false').lower() == 'true'
                                
                                st.success(f"✅ {otp_result['message']}")
                                
                                # Check for SMS errors and display appropriate guidance
                                sms_error = st.session_state.get('sms_error')
                                fallback_otp = st.session_state.get('fallback_otp')
                                
                                if sms_error:
                                    st.warning(f" SMS Issue: {sms_error}")
                                    
                                    # Show trial account guidance
                                    show_trial_account_guidance()
                                    
                                    # Clear the error from session state
                                    if 'sms_error' in st.session_state:
                                        del st.session_state['sms_error']
                                
                                if demo_mode and show_otp_in_ui:
                                    st.session_state.demo_otp = otp_result["otp"]  # For demo purposes
                                    st.info(f" **Demo OTP:** {otp_result['otp']} (Demo mode - OTP displayed for testing)")
                                elif fallback_otp:
                                    st.session_state.demo_otp = fallback_otp
                                    st.warning(f" **Fallback OTP:** {fallback_otp} (SMS failed - use this code)")
                                    if 'fallback_otp' in st.session_state:
                                        del st.session_state['fallback_otp']
                                elif sms_enabled:
                                    st.info(f"📱 **OTP sent to {mobile}** - Check your mobile phone for the verification code")
                                else:
                                    st.info(f"📱 **OTP generated** - In production, this would be sent via SMS to {mobile}")
                                
                                st.rerun()
                            else:
                                st.error(f" Failed to generate OTP: {otp_result.get('error', 'Unknown error')}")
                        else:
                            st.error(" No mobile number found for this patient")
                            
                    except Exception as e:
                        st.error(f" Error sending OTP: {str(e)}")
        
        else:
            # OTP verification
            st.success("✅ OTP sent successfully")
            
            # Show OTP status if available
            if st.session_state.get('otp_expires_at'):
                expires_at = st.session_state.otp_expires_at
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                
                remaining_time = expires_at - datetime.now()
                if remaining_time.total_seconds() > 0:
                    minutes = int(remaining_time.total_seconds() // 60)
                    seconds = int(remaining_time.total_seconds() % 60)
                    st.info(f"⏰ OTP expires in {minutes}:{seconds:02d}")
                else:
                    st.warning(" OTP has expired. Please request a new one.")
            
            otp_input = st.text_input(
                "Enter OTP",
                placeholder="Enter 6-digit OTP",
                max_chars=6,
                help="Enter the OTP sent to patient's mobile number"
            )
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                if st.button("🔓 Verify OTP", type="primary"):
                    if otp_input:
                        try:
                            otp_manager = OTPManager()
                            mobile = patient_data.get('mobile', '')
                            
                            # Verify OTP with new API
                            verification_result = otp_manager.verify_otp(mobile, otp_input, purpose="access")
                            
                            if verification_result["success"]:
                                st.success(f"✅ {verification_result['message']}")
                                
                                # Load complete patient data
                                with st.spinner("📋 Loading patient medical records..."):
                                    card_generator = HealthCardGenerator()
                                    
                                    # Try to get patient by health ID or mobile
                                    patient_id = patient_data.get('patient_id', '')
                                    complete_data = card_generator.get_patient_by_health_id(patient_id)
                                    
                                    if not complete_data:
                                        # Try by mobile number
                                        health_card = card_generator.get_patient_by_mobile(mobile)
                                        if health_card:
                                            complete_data = card_generator.get_patient_by_health_id(health_card['health_card_id'])
                                    
                                    if complete_data:
                                        # Store in session state
                                        st.session_state.verified_patient_data = complete_data
                                        st.session_state.patient_verified = True
                                        st.session_state.selected_patient = complete_data['patient']['_id']
                                        
                                        # Clear OTP session data
                                        st.session_state.otp_sent = False
                                        st.session_state.show_otp_verification = False
                                        
                                        # Redirect to patient access view
                                        st.session_state.active_tab = "patient_access"
                                        
                                        st.rerun()
                                    else:
                                        st.error("❌ Could not load complete patient data")
                            else:
                                st.error(f"❌ {verification_result.get('error', 'Invalid OTP')}")
                                
                        except Exception as e:
                            st.error(f"❌ Error verifying OTP: {str(e)}")
                    else:
                        st.warning("⚠️ Please enter OTP")
            
            with col_b:
                if st.button("🔄 Resend OTP"):
                    try:
                        import os
                        from dotenv import load_dotenv
                        load_dotenv()
                        
                        otp_manager = OTPManager()
                        mobile = patient_data.get('mobile', '')
                        
                        if mobile:
                            # Generate new OTP
                            otp_result = otp_manager.generate_otp(mobile, purpose="access")
                            
                            if otp_result["success"]:
                                # Update session data
                                st.session_state.otp_expires_at = otp_result["expires_at"]
                                
                                # Show OTP in UI only if in demo mode
                                demo_mode = os.getenv('DEMO_MODE', 'true').lower() == 'true'
                                show_otp_in_ui = os.getenv('SHOW_OTP_IN_UI', 'true').lower() == 'true'
                                sms_enabled = os.getenv('SMS_ENABLED', 'false').lower() == 'true'
                                
                                if demo_mode and show_otp_in_ui:
                                    st.session_state.demo_otp = otp_result["otp"]
                                    st.success(f"✅ New OTP sent!")
                                    st.info(f"🔐 **Demo OTP:** {otp_result['otp']}")
                                elif sms_enabled:
                                    st.success(f"✅ New OTP sent to {mobile}!")
                                    st.info(f"📱 Check your mobile phone for the new verification code")
                                else:
                                    st.success(f"✅ New OTP generated!")
                                    st.info(f"📱 In production, this would be sent to {mobile}")
                                
                                st.rerun()
                            else:
                                st.error(f"❌ Failed to resend OTP: {otp_result.get('error', 'Unknown error')}")
                        else:
                            st.error("❌ No mobile number available")
                    except Exception as e:
                        st.error(f"❌ Error resending OTP: {str(e)}")
    
    with col2:
        st.write("**⏰ OTP Information**")
        st.info("• OTP is valid for 5 minutes")
        st.info("• Maximum 3 verification attempts per OTP")
        st.info("• Enter the 6-digit code sent to patient's mobile")
        st.info("• Use 'Resend OTP' if code not received")
        
        if st.button("❌ Cancel Verification"):
            # Clear all session data
            for key in ['qr_patient_data', 'otp_sent', 'show_otp_verification', 'demo_otp', 'otp_expires_at']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

def display_verified_patient_data():
    """Display complete patient data after successful verification"""
    if not st.session_state.get('verified_patient_data'):
        st.warning("⚠️ No verified patient data found")
        return
    
    patient_data = st.session_state.verified_patient_data
    health_card = patient_data['health_card']
    patient = patient_data['patient']
    medical_records = patient_data['medical_records']
    
    st.success("🔓 **Patient Data Access Granted**")
    
    # Patient overview
    st.subheader("👤 Patient Information")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write("**📋 Basic Information**")
        st.write(f"**Name:** {health_card['patient_name']}")
        st.write(f"**Health ID:** {health_card['health_card_id']}")
        st.write(f"**Mobile:** {health_card['mobile_number']}")
        
    with col2:
        st.write("**🏥 Health Card Details**")
        st.write(f"**Issue Date:** {health_card['issued_date'].strftime('%d/%m/%Y')}")
        st.write(f"**Valid Until:** {health_card['validity_date'].strftime('%d/%m/%Y')}")
        st.write(f"**Status:** {health_card['status'].title()}")
    
    with col3:
        st.write("**📊 Quick Stats**")
        st.write(f"**Total Records:** {len(medical_records)}")
        st.write(f"**Account Created:** {patient.get('created_at', 'Unknown')}")
        st.write(f"**Last Access:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    st.divider()
    
    # Action buttons
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("📋 View Medical History", type="primary", use_container_width=True):
            st.session_state.view_section = "history"
            st.rerun()
    
    with col_b:
        if st.button("⚡ Quick Summary", use_container_width=True):
            st.session_state.view_section = "quick_summary"
            st.rerun()
    
    with col_c:
        if st.button("📝 Add Observation", use_container_width=True):
            st.session_state.view_section = "add_observation"
            st.rerun()
    
    with col_d:
        if st.button("🔒 End Session", use_container_width=True):
            for key in ['verified_patient_data', 'patient_verified', 'qr_patient_data', 'view_section']:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("✅ Patient session ended")
            st.rerun()
    
    st.divider()
    
    # Display section based on selection
    view_section = st.session_state.get('view_section', 'records')
    
    if view_section == 'history':
        # Medical History Section
        st.subheader("📋 Complete Medical History")
        patient_id = str(patient['_id'])
        view_patient_medical_history(patient_id)
        
        if st.button("⬅️ Back to Overview"):
            st.session_state.view_section = "records"
            st.rerun()
    
    elif view_section == 'quick_summary':
        # Quick Summary Section
        st.subheader("⚡ AI-Powered Quick Summary")
        
        if medical_records and len(medical_records) > 0:
            with st.spinner("🤖 Generating intelligent medical summary..."):
                try:
                    # Combine all record contents
                    all_content = []
                    for record in medical_records:
                        content = record.get('content', '')
                        record_type = record.get('record_type', 'General')
                        record_date = record.get('created_at', datetime.now())
                        if isinstance(record_date, str):
                            try:
                                record_date = datetime.fromisoformat(record_date.replace('Z', '+00:00'))
                            except:
                                record_date = datetime.now()
                        
                        all_content.append(f"[{record_date.strftime('%Y-%m-%d')} - {record_type}]\n{content}")
                    
                    combined_text = "\n\n---\n\n".join(all_content)
                    
                    # Limit text length for processing
                    if len(combined_text) > 3000:
                        combined_text = combined_text[:3000] + "\n\n[Note: Content truncated for processing]"
                    
                    # Generate AI summary
                    summary = summarize_text(combined_text)
                    
                    # Display summary in a nice format
                    st.success("✅ Summary Generated Successfully!")
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown("### 📄 Medical Summary Report")
                        st.markdown(f"**Patient:** {health_card['patient_name']}")
                        st.markdown(f"**Health ID:** {health_card['health_card_id']}")
                        st.markdown(f"**Generated:** {datetime.now().strftime('%d/%m/%Y at %H:%M')}")
                        st.markdown(f"**Total Records Analyzed:** {len(medical_records)}")
                    
                    with col2:
                        st.markdown("### 📊 Quick Stats")
                        st.metric("Records", len(medical_records))
                        st.metric("Blood Group", health_card.get('blood_group', 'N/A'))
                        
                        # Count record types
                        record_types = {}
                        for record in medical_records:
                            rtype = record.get('record_type', 'General')
                            record_types[rtype] = record_types.get(rtype, 0) + 1
                        
                        if record_types:
                            st.write("**Record Types:**")
                            for rtype, count in record_types.items():
                                st.write(f"• {rtype}: {count}")
                    
                    st.divider()
                    
                    # Display the AI summary
                    st.markdown("### 🤖 AI Analysis")
                    st.info(summary)
                    
                    st.divider()
                    
                    # Additional options
                    col_x, col_y = st.columns(2)
                    
                    with col_x:
                        if st.button("📋 View Full History", use_container_width=True):
                            st.session_state.view_section = "history"
                            st.rerun()
                    
                    with col_y:
                        if st.button("🔄 Regenerate Summary", use_container_width=True):
                            st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error generating summary: {str(e)}")
                    logger.error(f"Summary generation error: {str(e)}")
                    st.info("💡 Try viewing individual records in the Medical History section")
        else:
            st.warning("⚠️ No medical records available to summarize")
            st.info("This patient doesn't have any medical records yet. Add observations or upload documents to generate a summary.")
        
        if st.button("⬅️ Back to Overview"):
            st.session_state.view_section = "records"
            st.rerun()
    
    elif view_section == 'add_observation':
        # Add Observation Section
        st.subheader("📝 Add New Medical Observation")
        
        with st.form("quick_observation_form"):
            observation_title = st.text_input("Observation Title*", placeholder="e.g., Regular Checkup, Follow-up Visit")
            observation_type = st.selectbox("Type*", [
                "General Consultation", "Follow-up", "Emergency Visit", 
                "Routine Checkup", "Specialist Consultation", "Treatment Review"
            ])
            
            observation_content = st.text_area(
                "Medical Observation*", 
                height=200,
                placeholder="Enter detailed medical observation, diagnosis, treatment plan, etc."
            )
            
            col1, col2 = st.columns(2)
            with col1:
                priority = st.selectbox("Priority", ["Normal", "High", "Urgent"])
                prescription = st.text_area("Prescription", placeholder="List medications and dosage")
            
            with col2:
                next_appointment = st.date_input("Next Appointment", value=None)
                doctor_notes = st.text_area("Doctor Notes", placeholder="Additional notes")
            
            col_x, col_y = st.columns(2)
            with col_x:
                submit_observation = st.form_submit_button("💾 Save Observation", type="primary", use_container_width=True)
            with col_y:
                cancel_button = st.form_submit_button("❌ Cancel", use_container_width=True)
            
            if submit_observation:
                if observation_title and observation_content:
                    try:
                        patient_id = str(patient['_id'])
                        
                        # Prepare observation data
                        observation_data = {
                            "title": observation_title,
                            "content": observation_content,
                            "record_type": observation_type,
                            "record_date": datetime.now().isoformat()[:10],
                            "priority": priority,
                            "additional_notes": f"Prescription: {prescription}\nDoctor Notes: {doctor_notes}\nNext Appointment: {next_appointment or 'Not scheduled'}",
                            "patient_id": patient_id,
                            "created_at": datetime.now().isoformat(),
                            "created_by": st.session_state.get('username', 'doctor'),
                            "doctor_id": st.session_state.get('user_id', '')
                        }
                        
                        # Save observation
                        result = save_medical_record(observation_data)
                        
                        if result:
                            st.success("✅ Medical observation saved successfully!")
                            
                            # Refresh patient data
                            card_generator = HealthCardGenerator()
                            updated_data = card_generator.get_patient_by_health_id(health_card['health_card_id'])
                            if updated_data:
                                st.session_state.verified_patient_data = updated_data
                            
                            st.session_state.view_section = "records"
                            st.rerun()
                        else:
                            st.error("❌ Failed to save observation")
                    
                    except Exception as e:
                        st.error(f"❌ Error saving observation: {str(e)}")
                else:
                    st.error("❌ Please fill in Title and Observation content")
            
            if cancel_button:
                st.session_state.view_section = "records"
                st.rerun()
    
    else:
        # Medical Records Overview Section (default)
        st.subheader("📋 Recent Medical Records")
        
        if medical_records:
            # Sort records by date (newest first)
            sorted_records = sorted(medical_records, 
                                  key=lambda x: x.get('created_at', datetime.min), 
                                  reverse=True)
            
            # Show only recent 5 records in overview
            for i, record in enumerate(sorted_records[:5]):
                record_date = record.get('created_at', datetime.now())
                if isinstance(record_date, str):
                    try:
                        record_date = datetime.fromisoformat(record_date.replace('Z', '+00:00'))
                    except:
                        record_date = datetime.now()
                
                record_title = record.get('title', f'Medical Record {i+1}')
                record_type = record.get('record_type', 'General')
                
                with st.expander(f"📄 {record_title} - {record_date.strftime('%d/%m/%Y')}", 
                               expanded=(i == 0)):
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write("**📝 Content:**")
                        content = record.get('content', 'No content available')
                        st.text_area("Record Content", value=content[:500], height=150, disabled=True, key=f"content_{i}")
                    
                    with col2:
                        st.write("**📊 Details:**")
                        st.write(f"**Type:** {record_type}")
                        st.write(f"**Date:** {record_date.strftime('%d/%m/%Y')}")
                        
                        if record.get('priority'):
                            st.write(f"**Priority:** {record['priority']}")
            
            if len(sorted_records) > 5:
                st.info(f"📋 Showing 5 most recent records. Total records: {len(sorted_records)}. Click 'View Medical History' to see all.")
        else:
            st.info("📭 No medical records found for this patient")

def main():
    """Enhanced main doctor dashboard function with QR scanning"""
    # Check authentication
    check_authentication()
    
    # Get current user
    current_user = get_current_user()
    if not current_user:
        st.error("Failed to load user data")
        st.stop()
    
    # Page header
    st.title("👨‍⚕️ Enhanced Doctor Dashboard")
    st.write(f"Welcome back, **Dr. {current_user.get('username', 'Doctor')}**!")
    
    # Simplified 3-section dashboard
    tab1, tab2, tab3 = st.tabs([
        "📱 QR Scanner & Patient Access", 
        "👥 My Patients",
        "🔍 Search Patients"
    ])
    
    with tab1:
        # QR Scanner and Patient Access Section
        st.subheader("📱 Quick Patient Access via QR Code")
        
        # Check if we should show OTP or patient data
        if st.session_state.get('show_otp_verification', False):
            otp_verification_interface()
        elif st.session_state.get('patient_verified', False):
            display_verified_patient_data()
        else:
            # Show QR scanner
            qr_code_scanner()
    
    with tab2:
        display_assigned_patients_overview()
    
    with tab3:
        search_patients()
        
        # If patient selected from search, show their history
        if 'selected_patient' in st.session_state and not st.session_state.get('patient_verified'):
            st.divider()
            view_patient_medical_history(st.session_state.selected_patient)
    
    # Enhanced sidebar
    with st.sidebar:
        st.header("👨‍⚕️ Doctor Tools")
        
        # Quick stats
        try:
            assigned_patients = get_assigned_patients()
            st.metric("👥 My Patients", len(assigned_patients))
            
            # Show current session info
            if st.session_state.get('patient_verified'):
                patient_data = st.session_state.verified_patient_data
                health_card = patient_data['health_card']
                
                st.success("🔓 **Active Session**")
                st.write(f"**Patient:** {health_card['patient_name'][:20]}...")
                st.write(f"**Health ID:** {health_card['health_card_id']}")
                
                if st.button("🔒 End Session", type="secondary"):
                    for key in ['verified_patient_data', 'patient_verified', 'qr_patient_data']:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()
            
        except Exception as e:
            st.warning("Unable to load patient count")
        
        st.divider()
        
        # Quick actions
        st.header("⚡ Quick Actions")
        
        if st.button("📱 New QR Scan", use_container_width=True):
            # Clear QR session data for new scan
            for key in ['qr_patient_data', 'otp_sent', 'show_otp_verification', 'view_section']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
        
        if st.session_state.get('patient_verified'):
            if st.button("⚡ Quick Summary", type="primary", use_container_width=True):
                st.session_state.view_section = "quick_summary"
                st.rerun()
        
        if st.button("🔍 Patient Lookup", use_container_width=True):
            st.info("Use the Search Patients tab")
        
        st.divider()
        
        # Help section
        st.header("❓ Help & Guide")
        
        with st.expander("📱 QR Scanner Guide"):
            st.write("**How to use QR Scanner:**")
            st.write("1. Ask patient to show health card")
            st.write("2. Upload QR code image")
            st.write("3. Click 'Scan QR Code'")
            st.write("4. Send OTP to patient's mobile")
            st.write("5. Enter OTP for verification")
            st.write("6. Access medical records")
        
        with st.expander("🔐 Security Features"):
            st.write("**Security measures:**")
            st.write("• OTP verification required")
            st.write("• 5-minute OTP validity")
            st.write("• Encrypted QR codes")
            st.write("• Secure session management")
            st.write("• Doctor authentication")
        
        st.caption("🔒 Secure • 🏥 Professional • 📱 Digital")

# Run the main function directly
if __name__ == "__main__":
    main()