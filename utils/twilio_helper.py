"""
Twilio Trial Account Helper
Provides utilities and guidance for Twilio trial account limitations
"""
import os
import logging
import streamlit as st

logger = logging.getLogger(__name__)

def is_trial_account():
    """Check if using Twilio trial account based on common indicators"""
    try:
        from twilio.rest import Client
        
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        
        if not account_sid or not auth_token:
            return True  # Assume trial if no credentials
        
        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()
        
        # Trial accounts typically have "Trial" in the type
        return account.type.lower() == 'trial'
        
    except Exception as e:
        logger.warning(f"Could not determine account type: {e}")
        return True  # Assume trial on error

def show_trial_account_guidance():
    """Display trial account limitations and solutions in Streamlit"""
    
    if is_trial_account():
        st.warning("🔒 **Twilio Trial Account Detected**")
        
        with st.expander("📱 Trial Account SMS Limitations", expanded=False):
            st.write("**Current Limitations:**")
            st.write("• Can only send SMS to verified phone numbers")
            st.write("• Limited to a small number of messages per day")
            st.write("• All messages include 'Sent from your Twilio trial account' prefix")
            
            st.write("**💡 Solutions:**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Option 1: Verify Phone Numbers**")
                st.info("1. Visit: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
                st.info("2. Click 'Add a new number'")
                st.info("3. Enter the phone number")
                st.info("4. Choose SMS or Voice verification")
                st.info("5. Enter the verification code")
                
                if st.button("🌐 Open Twilio Console", help="Open Twilio phone verification page"):
                    st.markdown("[Verify Phone Numbers](https://console.twilio.com/us1/develop/phone-numbers/manage/verified)")
            
            with col2:
                st.write("**Option 2: Upgrade Account**")
                st.info("• Upgrade to a paid Twilio account")
                st.info("• Send SMS to any valid phone number")
                st.info("• Remove trial account limitations")
                st.info("• Professional SMS delivery")
                
                if st.button("💳 Upgrade Twilio Account", help="Learn about Twilio pricing"):
                    st.markdown("[Twilio Pricing](https://www.twilio.com/pricing)")
            
            st.divider()
            
            st.write("**🧪 Testing with Trial Account:**")
            st.write("1. **Use your own verified number** for initial testing")
            st.write("2. **Add team members' numbers** to verified list")
            st.write("3. **Test with known working numbers** first")
            
        return True
    
    return False

def get_verification_instructions(phone_number):
    """Get specific instructions for verifying a phone number"""
    return f"""
    **To verify {phone_number}:**
    
    1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
    2. Click "Add a new number"
    3. Enter: {phone_number}
    4. Choose verification method (SMS recommended)
    5. Enter the verification code you receive
    6. Try sending OTP again
    
    **Alternative:** Test with a number you've already verified.
    """

def check_common_sms_errors(error_message):
    """Analyze common SMS errors and provide solutions"""
    error_msg = str(error_message).lower()
    
    solutions = []
    
    if "21608" in error_msg or "unverified" in error_msg:
        solutions.append({
            "error": "Unverified Phone Number",
            "icon": "🔒",
            "solution": "This number needs to be verified in your Twilio console for trial accounts.",
            "action": "Verify at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified"
        })
    
    if "21614" in error_msg or "invalid" in error_msg:
        solutions.append({
            "error": "Invalid Phone Number",
            "icon": "📱",
            "solution": "Phone number format is incorrect.",
            "action": "Use format: +[country code][number] (e.g., +1234567890)"
        })
    
    if "20003" in error_msg or "authentication" in error_msg:
        solutions.append({
            "error": "Authentication Failed",
            "icon": "🔑",
            "solution": "Twilio credentials are incorrect.",
            "action": "Check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env file"
        })
    
    if "21606" in error_msg:
        solutions.append({
            "error": "Invalid From Number",
            "icon": "📞",
            "solution": "Twilio phone number is incorrect.",
            "action": "Check TWILIO_PHONE_NUMBER in .env file"
        })
    
    if not solutions:
        solutions.append({
            "error": "Unknown SMS Error",
            "icon": "❓",
            "solution": "An unexpected error occurred.",
            "action": "Check Twilio console logs for detailed error information"
        })
    
    return solutions

def display_sms_error_help(error_message):
    """Display helpful error information in Streamlit"""
    solutions = check_common_sms_errors(error_message)
    
    for solution in solutions:
        st.error(f"{solution['icon']} **{solution['error']}**")
        st.write(f"**Problem:** {solution['solution']}")
        st.write(f"**Solution:** {solution['action']}")
        st.write("")

def show_sms_testing_tips():
    """Show tips for testing SMS functionality"""
    with st.expander("💡 SMS Testing Tips", expanded=False):
        st.write("**Before Testing:**")
        st.write("✅ Verify your phone number in Twilio console")
        st.write("✅ Check that your .env file has correct Twilio credentials")
        st.write("✅ Ensure phone number includes country code (+1, +91, etc.)")
        
        st.write("**During Testing:**")
        st.write("📱 Start with your own verified phone number")
        st.write("⏱️ Wait a few seconds between test attempts")
        st.write("📋 Check Twilio console for delivery status")
        
        st.write("**If SMS Fails:**")
        st.write("🔍 Check the error message in the logs")
        st.write("🌐 Verify the phone number in Twilio console")
        st.write("🔄 Try with a different verified number")
        st.write("💻 Check Twilio console for detailed error logs")

def create_sms_status_indicator(sms_sent, error_message=None):
    """Create a visual SMS status indicator"""
    if sms_sent:
        st.success("✅ SMS sent successfully! Check your phone.")
    else:
        st.error("❌ SMS delivery failed")
        
        if error_message:
            display_sms_error_help(error_message)
        
        # Show trial account guidance if applicable
        if is_trial_account():
            st.info("💡 **Trial Account Tip:** Ensure the phone number is verified in your Twilio console.")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔗 Verify Phone Number"):
                    st.markdown("[Verify in Twilio Console](https://console.twilio.com/us1/develop/phone-numbers/manage/verified)")
            
            with col2:
                if st.button("📚 View SMS Help"):
                    show_sms_testing_tips()