# Twilio Trial Account SMS Setup Guide

## 🚨 Error: "Unable to create record: The number +91XXXXXXXXXX is unverified"

This error occurs because you're using a **Twilio Trial Account**, which has restrictions on sending SMS to unverified phone numbers.

## 🔍 Understanding Twilio Trial Accounts

Trial accounts are free Twilio accounts with the following limitations:

- ✅ **Can send SMS** to verified phone numbers only
- ❌ **Cannot send SMS** to unverified phone numbers
- 🔢 **Limited messages** per day (usually around 200-500)
- 📝 **All messages include** "Sent from your Twilio trial account" prefix

## 💡 Solutions

### Option 1: Verify Phone Numbers (Recommended for Testing)

**Step 1:** Go to Twilio Console
- Visit: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
- Log in with your Twilio account

**Step 2:** Add Phone Number
- Click "Add a new number" (red plus button)
- Enter the phone number with country code (e.g., +919876543210)
- Click "Add"

**Step 3:** Choose Verification Method
- Select "SMS" (recommended) or "Voice Call"
- Click "Send Verification Code"

**Step 4:** Enter Verification Code
- Check your phone for the verification code
- Enter the code in the Twilio console
- Click "Verify"

**Step 5:** Test SMS
- Go back to your EHR application
- Try generating OTP with the verified number
- SMS should now work successfully

### Option 2: Upgrade to Paid Account

**Benefits:**
- Send SMS to any valid phone number worldwide
- No daily message limits
- No "trial account" prefix in messages
- Professional SMS delivery

**Steps:**
1. Go to: https://console.twilio.com/billing
2. Add payment method
3. Choose a pricing plan
4. Upgrade your account

## 🧪 Testing Tips

### Before Testing:
- ✅ Verify at least one phone number (yours)
- ✅ Check Twilio credentials in `.env` file
- ✅ Ensure phone numbers include country code

### During Testing:
- 📱 Start with your own verified phone number
- ⏱️ Wait 30 seconds between test attempts
- 📋 Check Twilio console for delivery status

### If SMS Still Fails:
1. **Check Error Message** - Look at the specific error code
2. **Verify Phone Number** - Ensure it's verified in Twilio console
3. **Check Format** - Phone number must include country code (+91, +1, etc.)
4. **Try Different Number** - Test with another verified number
5. **Check Twilio Console** - View detailed logs and error messages

## 🌍 Country Code Examples

| Country | Code | Example |
|---------|------|---------|
| India | +91 | +919876543210 |
| USA | +1 | +11234567890 |
| UK | +44 | +441234567890 |
| Canada | +1 | +11234567890 |

## 🔧 Common Error Codes

| Error Code | Meaning | Solution |
|------------|---------|----------|
| 21608 | Unverified number (trial) | Verify number in console |
| 21614 | Invalid phone number | Check format (+country code) |
| 20003 | Authentication failed | Check SID/Token in .env |
| 21606 | Invalid from number | Check Twilio phone number |

## 📞 Quick Verification Checklist

Before reporting SMS issues, verify:

- [ ] Phone number is verified in Twilio console
- [ ] Phone number includes country code (+91...)
- [ ] Twilio credentials are correct in `.env` file
- [ ] You're not exceeding trial account limits
- [ ] Phone number format is valid

## 🆘 Getting Help

If you're still having issues:

1. **Check Twilio Console Logs**: https://console.twilio.com/us1/monitor/logs
2. **Review Error Messages**: Look for specific error codes
3. **Test with Known Working Number**: Use a verified number first
4. **Contact Twilio Support**: If account-specific issues persist

## 🎯 Quick Fix Summary

**For immediate testing:**
1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
2. Click "Add a new number"
3. Enter your phone number with country code
4. Verify via SMS
5. Test OTP generation in the EHR app

This should resolve the "unverified number" error and allow SMS delivery to work properly!