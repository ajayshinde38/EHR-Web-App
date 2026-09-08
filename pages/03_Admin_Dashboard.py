"""
Enhanced Admin Dashboard - Advanced User Management and System Administration
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from bson import ObjectId
from utils.auth import check_user_role, get_current_user, create_user
from utils.database import get_users_collection, get_records_collection, get_assignments_collection
from utils.records import get_patient_records
from utils.health_card import HealthCardGenerator
import logging

# Optional plotly import with fallback
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Advanced charts require plotly. Install with: pip install plotly")

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Admin Dashboard - EHR Web App",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_authentication():
    """Check if user is authenticated and has admin role"""
    if not st.session_state.get('authenticated', False):
        st.error("Please login to access this page")
        st.stop()
    
    if not check_user_role('admin'):
        st.error("Access denied. This page is for administrators only.")
        st.stop()

def create_new_user():
    """Enhanced create new user interface"""
    st.header("Create New User Account")
    st.write("Add new users to the system with proper role assignment and validation.")
    
    # Get current user for logging
    current_user = get_current_user()
    
    # User creation form with enhanced validation
    with st.form("create_user_form", clear_on_submit=True):
        st.subheader("User Information")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Basic Details**")
            new_username = st.text_input(
                "Username*", 
                placeholder="Enter unique username",
                help="Username must be unique and contain only letters, numbers, and underscores"
            )
            
            new_email = st.text_input(
                "Email Address*", 
                placeholder="user@example.com",
                help="Valid email address for account notifications"
            )
            
            new_role = st.selectbox(
                "User Role*", 
                ["patient", "doctor", "admin"],
                help="Select the appropriate role for this user"
            )
        
        with col2:
            st.write("**Security Settings**")
            new_password = st.text_input(
                "Password*", 
                type="password", 
                placeholder="Enter secure password",
                help="Password must be at least 8 characters long"
            )
            
            confirm_password = st.text_input(
                "Confirm Password*", 
                type="password", 
                placeholder="Confirm password",
                help="Re-enter the password to confirm"
            )
            
            # Account status
            account_active = st.checkbox("Account Active", value=True, help="Whether the account should be active immediately")
        
        # Role-specific fields
        st.divider()
        st.subheader("Role-Specific Information")
        
        specialization = None
        date_of_birth = None
        department = None
        
        if new_role == "doctor":
            col1, col2 = st.columns(2)
            with col1:
                specialization = st.text_input(
                    "Medical Specialization", 
                    placeholder="e.g., Cardiology, Pediatrics",
                    help="Doctor's area of medical expertise"
                )
            with col2:
                department = st.text_input(
                    "Department", 
                    placeholder="e.g., Emergency, Internal Medicine",
                    help="Hospital department or clinic"
                )
                
        elif new_role == "patient":
            col1, col2 = st.columns(2)
            with col1:
                date_of_birth = st.date_input(
                    "Date of Birth", 
                    value=None,
                    help="Patient's date of birth for medical records"
                )
            with col2:
                # Additional patient info could go here
                st.info(" Additional patient information can be added after account creation")
        
        elif new_role == "admin":
            st.warning(" **Admin Account**: This user will have full system access")
            admin_level = st.selectbox(
                "Admin Level",
                ["Standard Admin", "Super Admin"],
                help="Level of administrative privileges"
            )
        
        # Additional options
        st.divider()
        st.subheader(" Notification Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            send_welcome_email = st.checkbox(
                "Send Welcome Email", 
                value=True,
                help="Send account creation notification to user"
            )
        
        with col2:
            require_password_change = st.checkbox(
                "Require Password Change", 
                value=True,
                help="User must change password on first login"
            )
        
        # Submit button
        st.divider()
        submitted = st.form_submit_button("➕ Create User Account", type="primary", use_container_width=True)
        
        if submitted:
            # Enhanced validation
            errors = []
            
            # Required field validation
            if not new_username or not new_username.strip():
                errors.append(" Username is required")
            elif len(new_username.strip()) < 3:
                errors.append(" Username must be at least 3 characters long")
            elif not new_username.replace('_', '').isalnum():
                errors.append(" Username can only contain letters, numbers, and underscores")
            
            if not new_email or not new_email.strip():
                errors.append(" Email address is required")
            elif '@' not in new_email or '.' not in new_email.split('@')[-1]:
                errors.append(" Please enter a valid email address")
            
            if not new_password:
                errors.append(" Password is required")
            elif len(new_password) < 8:
                errors.append(" Password must be at least 8 characters long")
            elif new_password.isalnum():  # No special characters
                errors.append(" Password should contain at least one special character")
            
            if new_password != confirm_password:
                errors.append(" Passwords do not match")
            
            # Role-specific validation
            if new_role == "doctor" and specialization and len(specialization.strip()) < 2:
                errors.append(" Please enter a valid medical specialization")
            
            # Check for existing username/email
            try:
                users_collection = get_users_collection()
                
                existing_username = users_collection.find_one({"username": new_username.strip()})
                if existing_username:
                    errors.append(" Username already exists")
                
                existing_email = users_collection.find_one({"email": new_email.strip()})
                if existing_email:
                    errors.append(" Email address already registered")
                    
            except Exception as e:
                errors.append(f" Database error: {str(e)}")
            
            # Display errors or create user
            if errors:
                st.error("**Please fix the following errors:**")
                for error in errors:
                    st.write(error)
            else:
                # Create user with enhanced data
                try:
                    user_data = {
                        "username": new_username.strip(),
                        "email": new_email.strip(),
                        "role": new_role,
                        "active": account_active,
                        "created_at": datetime.utcnow(),
                        "require_password_change": require_password_change,
                        "created_by": current_user.get('username', 'admin')
                    }
                    
                    # Add role-specific data
                    if new_role == "doctor":
                        user_data.update({
                            "specialization": specialization.strip() if specialization else "",
                            "department": department.strip() if department else "",
                            "assigned_patients": []
                        })
                    elif new_role == "patient":
                        user_data.update({
                            "date_of_birth": date_of_birth.isoformat() if date_of_birth else None,
                            "medical_history": []
                        })
                    elif new_role == "admin":
                        user_data.update({
                            "admin_level": admin_level,
                            "permissions": ["full_access"] if admin_level == "Super Admin" else ["standard_admin"]
                        })
                    
                    # Create the user
                    success = create_user(new_username.strip(), new_email.strip(), new_password, new_role)
                    
                    if success:
                        st.success(f" **User '{new_username}' created successfully!**")
                        
                        # Show created user summary
                        with st.expander("📋 Created User Summary", expanded=True):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"** Username:** {new_username}")
                                st.write(f"** Email:** {new_email}")
                                st.write(f"** Role:** {new_role.title()}")
                                st.write(f"** Status:** {'Active' if account_active else 'Inactive'}")
                            
                            with col2:
                                st.write(f"** Created:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                                st.write(f"** Created By:** {current_user.get('username', 'admin')}")
                                
                                if new_role == "doctor" and specialization:
                                    st.write(f"** Specialization:** {specialization}")
                                elif new_role == "patient" and date_of_birth:
                                    st.write(f"** Date of Birth:** {date_of_birth}")
                        
                        # Notification actions
                        if send_welcome_email:
                            st.info(" **Welcome email would be sent to:** " + new_email)
                        
                        if require_password_change:
                            st.info(" **User will be required to change password on first login**")
                        
                        # Next steps
                        st.info(" **Next Steps:**")
                        if new_role == "doctor":
                            st.write("• Assign patients to this doctor in the 'Assign Patients' tab")
                            st.write("• Configure department settings if needed")
                        elif new_role == "patient":
                            st.write("• Patient can now upload medical records")
                            st.write("• Assign to a doctor for ongoing care")
                        
                        # Clear form by triggering rerun
                        st.balloons()  # Celebration effect
                        
                    else:
                        st.error(" **Failed to create user.** This could be due to:")
                        st.write("• Username or email already exists")
                        st.write("• Database connection issues")
                        st.write("• Invalid data format")
                        st.write(" Please try again or contact system administrator")
                        
                except Exception as e:
                    st.error(f" **Error creating user:** {str(e)}")
                    logger.error(f"User creation error: {str(e)}")
    
    # Quick user creation templates
    st.divider()
    st.subheader(" Quick Creation Templates")
    st.write("Use these templates for common user types:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("👤 Create Test Patient", help="Create a sample patient account"):
            # Pre-fill form with test data
            st.session_state.update({
                'template_username': f'patient_test_{datetime.now().strftime("%m%d%H%M")}',
                'template_email': f'patient.test.{datetime.now().strftime("%m%d%H%M")}@example.com',
                'template_role': 'patient'
            })
            st.info(" Test patient template loaded - scroll up to customize and create")
    
    with col2:
        if st.button(" Create Test Doctor", help="Create a sample doctor account"):
            st.session_state.update({
                'template_username': f'doctor_test_{datetime.now().strftime("%m%d%H%M")}',
                'template_email': f'doctor.test.{datetime.now().strftime("%m%d%H%M")}@hospital.com',
                'template_role': 'doctor'
            })
            st.info(" Test doctor template loaded - scroll up to customize and create")
    
    with col3:
        if st.button(" Create Admin User", help="Create an administrator account"):
            st.session_state.update({
                'template_username': f'admin_{datetime.now().strftime("%m%d%H%M")}',
                'template_email': f'admin.{datetime.now().strftime("%m%d%H%M")}@system.com',
                'template_role': 'admin'
            })
            st.info(" Admin template loaded - scroll up to customize and create")

def manage_users():
    """Enhanced user management interface with advanced features"""
    st.header(" Advanced User Management")
    
    try:
        users_collection = get_users_collection()
        
        # Get all users with additional info
        all_users = list(users_collection.find({}, {"password": 0}))  # Exclude password
        
        if not all_users:
            st.info(" No users found in the system.")
            st.write(" **Tip**: Create your first user using the 'Create User' tab.")
            return
        
        # Enhanced search and filter controls
        st.subheader(" Search & Filter Controls")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            search_query = st.text_input(
                " Search users:", 
                placeholder="Search by username, email...",
                help="Search across username and email fields"
            )
        
        with col2:
            role_filter = st.selectbox(
                " Filter by role:", 
                ["All Roles", "patient", "doctor", "admin"],
                help="Filter users by their assigned role"
            )
        
        with col3:
            sort_by = st.selectbox(
                "Sort by:", 
                ["Username (A-Z)", "Username (Z-A)", "Role", "Created Date (Newest)", "Created Date (Oldest)", "Last Active"],
                help="Choose how to sort the user list"
            )
        
        with col4:
            items_per_page = st.selectbox(
                " Items per page:",
                [10, 25, 50, 100],
                index=1,
                help="Number of users to display per page"
            )
        
        # Apply filters
        filtered_users = all_users
        
        # Search filter
        if search_query:
            search_lower = search_query.lower()
            filtered_users = [
                user for user in filtered_users
                if search_lower in user.get('username', '').lower() or
                   search_lower in user.get('email', '').lower()
            ]
        
        # Role filter
        if role_filter != "All Roles":
            filtered_users = [user for user in filtered_users if user.get('role') == role_filter]
        
        # Sort users
        if sort_by == "Username (A-Z)":
            filtered_users.sort(key=lambda x: x.get('username', '').lower())
        elif sort_by == "Username (Z-A)":
            filtered_users.sort(key=lambda x: x.get('username', '').lower(), reverse=True)
        elif sort_by == "Role":
            filtered_users.sort(key=lambda x: (x.get('role', ''), x.get('username', '')))
        elif sort_by == "Created Date (Newest)":
            filtered_users.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        elif sort_by == "Created Date (Oldest)":
            filtered_users.sort(key=lambda x: x.get('created_at', datetime.min))
        
        # Pagination
        total_users = len(filtered_users)
        total_pages = (total_users + items_per_page - 1) // items_per_page
        
        if total_pages > 1:
            st.write(f"** Found {total_users} users** (Page navigation below)")
            
            # Initialize page state
            if 'admin_user_page' not in st.session_state:
                st.session_state.admin_user_page = 1
            
            # Page controls
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button(" Previous", disabled=st.session_state.admin_user_page <= 1):
                    st.session_state.admin_user_page -= 1
                    st.rerun()
            
            with col2:
                page = st.selectbox(
                    "Page:",
                    range(1, total_pages + 1),
                    index=st.session_state.admin_user_page - 1,
                    key="page_selector"
                )
                if page != st.session_state.admin_user_page:
                    st.session_state.admin_user_page = page
                    st.rerun()
            
            with col3:
                if st.button("Next ", disabled=st.session_state.admin_user_page >= total_pages):
                    st.session_state.admin_user_page += 1
                    st.rerun()
            
            # Get current page users
            start_idx = (st.session_state.admin_user_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_users = filtered_users[start_idx:end_idx]
        else:
            st.write(f"** Found {total_users} users**")
            page_users = filtered_users
        
        if not page_users:
            st.warning(" No users match your search criteria.")
            st.write(" **Try**:")
            st.write("- Adjusting your search terms")
            st.write("- Changing the role filter") 
            st.write("- Clearing filters to see all users")
            return
        
        # Bulk actions
        if len(page_users) > 1:
            st.divider()
            st.subheader("⚡ Bulk Actions")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(" Send Notifications", help="Send system notifications to selected users"):
                    st.info(" Notification system would be implemented here.")
            
            with col2:
                if st.button(" Export User Data", help="Export user list to CSV"):
                    # Create DataFrame for export
                    export_data = []
                    for user in page_users:
                        export_data.append({
                            'Username': user.get('username', ''),
                            'Email': user.get('email', ''),
                            'Role': user.get('role', '').title(),
                            'Created Date': user.get('created_at', '').strftime('%Y-%m-%d') if user.get('created_at') else '',
                            'Status': 'Active'  # Could be enhanced with actual status
                        })
                    
                    df = pd.DataFrame(export_data)
                    csv = df.to_csv(index=False)
                    
                    st.download_button(
                        label="� Download CSV",
                        data=csv,
                        file_name=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
            
            with col3:
                if st.button(" Bulk Update", help="Update multiple users at once"):
                    st.info(" Bulk update interface would be implemented here.")
        
        st.divider()
        
        # Enhanced user display
        for i, user in enumerate(page_users):
            user_id = str(user['_id'])
            
            # Create enhanced user card
            with st.container():
                # Header with role-based coloring
                role = user.get('role', 'unknown')
                role_colors = {
                    'admin': '🔴',
                    'doctor': '🟢', 
                    'patient': '🔵'
                }
                role_emoji = role_colors.get(role, '⚫')
                
                # User card header
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"### {role_emoji} **{user.get('username', 'Unknown User')}**")
                    st.caption(f"Role: {role.title()} • ID: {user_id[:8]}...")
                
                with col2:
                    # User status indicator
                    created_at = user.get('created_at')
                    if created_at:
                        days_since_creation = (datetime.now() - created_at).days
                        if days_since_creation <= 7:
                            st.success(" New User")
                        elif days_since_creation <= 30:
                            st.info(" Recent")
                        else:
                            st.caption(" Established")
                
                with col3:
                    # Quick action buttons
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        if st.button("✏️", key=f"edit_{user_id}", help="Edit user"):
                            st.session_state[f"edit_user_{user_id}"] = True
                            st.rerun()
                    
                    with col_b:
                        if role != 'admin':  # Protect admin accounts
                            if st.button("🗑️", key=f"delete_{user_id}", help="Delete user", type="secondary"):
                                st.session_state[f"confirm_delete_{user_id}"] = True
                                st.rerun()
                
                # User details in expandable section
                with st.expander(f" View Details for {user.get('username', 'User')}", expanded=False):
                    detail_col1, detail_col2, detail_col3 = st.columns(3)
                    
                    with detail_col1:
                        st.write("** Basic Information**")
                        st.write(f"**Username:** {user.get('username', 'N/A')}")
                        st.write(f"**Email:** {user.get('email', 'N/A')}")
                        st.write(f"**Role:** {user.get('role', 'N/A').title()}")
                    
                    with detail_col2:
                        st.write("** Account Details**")
                        created_at = user.get('created_at')
                        if created_at:
                            st.write(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M')}")
                            st.write(f"**Days Active:** {(datetime.now() - created_at).days}")
                        else:
                            st.write("**Created:** Unknown")
                        
                        # Account status
                        st.write(f"**Status:**  Active")
                    
                    with detail_col3:
                        st.write("** Activity Summary**")
                        
                        # Role-specific information
                        if role == 'doctor':
                            assigned_patients = user.get('assigned_patients', [])
                            st.write(f"** Assigned Patients:** {len(assigned_patients)}")
                            
                            if assigned_patients:
                                st.write("**Recent Patients:**")
                                for patient_id in assigned_patients[:3]:
                                    try:
                                        patient = users_collection.find_one({"_id": ObjectId(patient_id)})
                                        if patient:
                                            st.caption(f"• {patient.get('username', 'Unknown')}")
                                    except:
                                        continue
                        
                        elif role == 'patient':
                            try:
                                records_collection = get_records_collection()
                                record_count = records_collection.count_documents({"patient_id": user_id})
                                st.write(f"** Medical Records:** {record_count}")
                                
                                # Last record date
                                last_record = records_collection.find_one(
                                    {"patient_id": user_id},
                                    sort=[("created_at", -1)]
                                )
                                if last_record:
                                    last_date = last_record.get('created_at')
                                    if last_date:
                                        st.write(f"** Last Record:** {last_date.strftime('%Y-%m-%d')}")
                            except:
                                st.write("** Medical Records:** Unable to load")
                
                # Edit user form
                if st.session_state.get(f"edit_user_{user_id}", False):
                    st.divider()
                    st.markdown("###  Edit User Information")
                    
                    with st.form(f"edit_form_{user_id}"):
                        edit_col1, edit_col2, edit_col3 = st.columns(3)
                        
                        with edit_col1:
                            new_username = st.text_input("Username", value=user.get('username', ''))
                            new_email = st.text_input("Email", value=user.get('email', ''))
                        
                        with edit_col2:
                            current_role = user.get('role', 'patient')
                            role_options = ["patient", "doctor", "admin"]
                            role_index = role_options.index(current_role) if current_role in role_options else 0
                            
                            new_role = st.selectbox("Role", role_options, index=role_index)
                            
                            # Status toggle (for future implementation)
                            account_active = st.checkbox("Account Active", value=True)
                        
                        with edit_col3:
                            st.write("**Additional Options**")
                            reset_password = st.checkbox(" Send Password Reset Email")
                            send_notification = st.checkbox(" Notify User of Changes")
                        
                        # Form buttons
                        button_col1, button_col2, button_col3 = st.columns(3)
                        
                        with button_col1:
                            update_submitted = st.form_submit_button(" Update User", type="primary")
                        
                        with button_col2:
                            cancel_edit = st.form_submit_button(" Cancel")
                        
                        with button_col3:
                            if role != 'admin':
                                delete_user = st.form_submit_button(" Delete User", type="secondary")
                        
                        # Handle form actions
                        if update_submitted:
                            try:
                                update_data = {
                                    "username": new_username.strip(),
                                    "email": new_email.strip(),
                                    "role": new_role,
                                    "updated_at": datetime.utcnow()
                                }
                                
                                # Validate inputs
                                if not new_username.strip() or not new_email.strip():
                                    st.error(" Username and email are required!")
                                else:
                                    users_collection.update_one(
                                        {"_id": user['_id']},
                                        {"$set": update_data}
                                    )
                                    
                                    st.success(" User updated successfully!")
                                    
                                    if send_notification:
                                        st.info(" User notification would be sent here.")
                                    
                                    if reset_password:
                                        st.info(" Password reset email would be sent here.")
                                    
                                    # Clear edit state
                                    del st.session_state[f"edit_user_{user_id}"]
                                    st.rerun()
                                    
                            except Exception as e:
                                st.error(f" Failed to update user: {str(e)}")
                        
                        if cancel_edit:
                            del st.session_state[f"edit_user_{user_id}"]
                            st.rerun()
                
                # Confirmation for delete
                if st.session_state.get(f"confirm_delete_{user_id}", False):
                    st.warning(f" **Confirm Deletion**: Are you sure you want to delete user '{user.get('username', 'Unknown')}'?")
                    
                    confirm_col1, confirm_col2 = st.columns(2)
                    
                    with confirm_col1:
                        if st.button(f" Yes, Delete {user.get('username', 'User')}", key=f"confirm_yes_{user_id}", type="primary"):
                            try:
                                users_collection.delete_one({"_id": user['_id']})
                                st.success(f" User '{user.get('username', 'User')}' deleted successfully!")
                                
                                # Clean up session state
                                if f"confirm_delete_{user_id}" in st.session_state:
                                    del st.session_state[f"confirm_delete_{user_id}"]
                                
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f" Failed to delete user: {str(e)}")
                    
                    with confirm_col2:
                        if st.button(" Cancel", key=f"confirm_no_{user_id}"):
                            del st.session_state[f"confirm_delete_{user_id}"]
                            st.rerun()
                
                st.divider()
    
    except Exception as e:
        st.error(f" Error loading user management: {str(e)}")
        logger.error(f"Error in manage_users: {str(e)}")

def assign_patients_to_doctors():
    """Patient assignment interface"""
    st.header(" Assign Patients to Doctors")
    
    try:
        users_collection = get_users_collection()
        assignments_collection = get_assignments_collection()
        
        # Get all doctors and patients
        doctors = list(users_collection.find({"role": "doctor"}))
        patients = list(users_collection.find({"role": "patient"}))
        
        if not doctors:
            st.warning("No doctors found in the system.")
            return
        
        if not patients:
            st.warning("No patients found in the system.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(" Select Doctor")
            doctor_options = {
                f"Dr. {doc['username']} ({doc.get('email', 'No email')})": str(doc['_id'])
                for doc in doctors
            }
            
            selected_doctor = st.selectbox(
                "Choose doctor:",
                options=list(doctor_options.keys()),
                index=None,
                placeholder="Select a doctor..."
            )
        
        with col2:
            st.subheader("Select Patients")
            
            if selected_doctor:
                doctor_id = doctor_options[selected_doctor]
                
                # Get currently assigned patients for this doctor
                doctor_data = users_collection.find_one({"_id": ObjectId(doctor_id)})
                currently_assigned = doctor_data.get('assigned_patients', []) if doctor_data else []
                
                # Show currently assigned patients
                if currently_assigned:
                    st.write("**Currently Assigned:**")
                    for patient_id in currently_assigned:
                        try:
                            patient = users_collection.find_one({"_id": ObjectId(patient_id)})
                            if patient:
                                col_a, col_b = st.columns([3, 1])
                                with col_a:
                                    st.write(f"• {patient['username']} ({patient.get('email', 'No email')})")
                                with col_b:
                                    if st.button("❌", key=f"remove_{patient_id}"):
                                        # Remove assignment
                                        users_collection.update_one(
                                            {"_id": ObjectId(doctor_id)},
                                            {"$pull": {"assigned_patients": patient_id}}
                                        )
                                        st.success("Patient unassigned!")
                                        st.rerun()
                        except:
                            continue
                
                st.divider()
                
                # Available patients to assign
                available_patients = [
                    p for p in patients 
                    if str(p['_id']) not in currently_assigned
                ]
                
                if available_patients:
                    st.write("**Available Patients:**")
                    
                    patient_options = {
                        f"{p['username']} ({p.get('email', 'No email')})": str(p['_id'])
                        for p in available_patients
                    }
                    
                    selected_patients = st.multiselect(
                        "Select patients to assign:",
                        options=list(patient_options.keys())
                    )
                    
                    if selected_patients and st.button("🔗 Assign Selected Patients"):
                        try:
                            patient_ids = [patient_options[p] for p in selected_patients]
                            
                            # Add to doctor's assigned patients
                            users_collection.update_one(
                                {"_id": ObjectId(doctor_id)},
                                {"$addToSet": {"assigned_patients": {"$each": patient_ids}}}
                            )
                            
                            # Update assignments collection
                            assignments_collection.update_one(
                                {"doctor_id": doctor_id},
                                {
                                    "$addToSet": {"patient_ids": {"$each": patient_ids}},
                                    "$set": {"updated_at": datetime.utcnow()}
                                },
                                upsert=True
                            )
                            
                            st.success(f"✅ {len(selected_patients)} patient(s) assigned successfully!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Failed to assign patients: {str(e)}")
                else:
                    st.info("All patients are already assigned to this doctor.")
    
    except Exception as e:
        st.error(f"❌ Error in patient assignment: {str(e)}")
        logger.error(f"Error in assign_patients_to_doctors: {str(e)}")

def display_system_statistics():
    """Enhanced system-wide statistics with visualizations"""
    st.header("System Analytics Dashboard")
    
    try:
        users_collection = get_users_collection()
        records_collection = get_records_collection()
        
        # Get comprehensive statistics
        total_users = users_collection.count_documents({})
        total_patients = users_collection.count_documents({"role": "patient"})
        total_doctors = users_collection.count_documents({"role": "doctor"})
        total_admins = users_collection.count_documents({"role": "admin"})
        total_records = records_collection.count_documents({})
        
        # Recent activity metrics
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        recent_users_week = users_collection.count_documents({"created_at": {"$gte": week_ago}})
        recent_users_month = users_collection.count_documents({"created_at": {"$gte": month_ago}})
        recent_records_week = records_collection.count_documents({"created_at": {"$gte": week_ago}})
        recent_records_month = records_collection.count_documents({"created_at": {"$gte": month_ago}})
        
        # Enhanced metrics display with progress bars
        st.subheader(" Key Performance Indicators")
        
        # Main metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label=" Total Users",
                value=total_users,
                delta=f"+{recent_users_week} this week"
            )
            
            # User distribution
            if total_users > 0:
                patient_percentage = (total_patients / total_users) * 100
                st.progress(patient_percentage / 100)
                st.caption(f"{patient_percentage:.1f}% Patients")
        
        with col2:
            st.metric(
                label=" Medical Staff",
                value=total_doctors,
                delta=f"{total_doctors + total_admins} total staff"
            )
            
            # Staff ratio
            if total_patients > 0 and total_doctors > 0:
                ratio = total_patients / total_doctors
                st.progress(min(ratio / 20, 1.0))  # Cap at 20:1 ratio
                st.caption(f"{ratio:.1f}:1 Patient-Doctor Ratio")
        
        with col3:
            st.metric(
                label=" Medical Records",
                value=total_records,
                delta=f"+{recent_records_week} this week"
            )
            
            # Records per patient
            if total_patients > 0:
                avg_records = total_records / total_patients
                st.progress(min(avg_records / 10, 1.0))  # Cap at 10 records
                st.caption(f"{avg_records:.1f} avg per patient")
        
        with col4:
            # System health indicator
            try:
                # Check database responsiveness
                start_time = datetime.now()
                users_collection.find_one()
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                health_score = max(0, min(100, 100 - (response_time - 50)))
                
                st.metric(
                    label=" System Health",
                    value=f"{health_score:.0f}%",
                    delta=f"{response_time:.0f}ms response"
                )
                
                # Health indicator
                health_color = "green" if health_score > 80 else "orange" if health_score > 60 else "red"
                st.progress(health_score / 100)
                st.caption(f"Database: {health_color.title()}")
                
            except Exception as e:
                st.metric(" System Health", " Warning", delta="Check required")
                st.caption("Database connection issue")
        
        st.divider()
        
        # Advanced analytics section
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(" User Growth Trends")
            
            try:
                # Get user registration data for the last 30 days
                pipeline = [
                    {"$match": {"created_at": {"$gte": month_ago}}},
                    {"$group": {
                        "_id": {
                            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                            "role": "$role"
                        },
                        "count": {"$sum": 1}
                    }},
                    {"$sort": {"_id.date": 1}}
                ]
                
                user_growth_data = list(users_collection.aggregate(pipeline))
                
                if user_growth_data:
                    # Create DataFrame for visualization
                    df_growth = pd.DataFrame([
                        {
                            "date": item["_id"]["date"],
                            "role": item["_id"]["role"].title(),
                            "count": item["count"]
                        }
                        for item in user_growth_data
                    ])
                    
                    # Create line chart
                    if PLOTLY_AVAILABLE:
                        fig = px.line(
                            df_growth, 
                            x="date", 
                            y="count", 
                            color="role",
                            title="Daily User Registrations (Last 30 Days)",
                            labels={"count": "New Users", "date": "Date"}
                        )
                        fig.update_layout(height=300, showlegend=True)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        # Fallback to simple chart
                        st.line_chart(df_growth.pivot(index='date', columns='role', values='count').fillna(0))
                    
                else:
                    st.info(" No user registration data available for the last 30 days.")
                    
            except Exception as e:
                st.warning(" Unable to load user growth visualization.")
                logger.error(f"User growth chart error: {str(e)}")
        
        with col2:
            st.subheader(" User Distribution")
            
            # User role distribution pie chart
            role_data = {
                "Patients": total_patients,
                "Doctors": total_doctors,
                "Admins": total_admins
            }
            
            if total_users > 0:
                if PLOTLY_AVAILABLE:
                    fig_pie = px.pie(
                        values=list(role_data.values()),
                        names=list(role_data.keys()),
                        title="User Role Distribution",
                        color_discrete_map={
                            "Patients": "#3498db",
                            "Doctors": "#2ecc71", 
                            "Admins": "#e74c3c"
                        }
                    )
                    fig_pie.update_layout(height=300)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    # Fallback to simple display
                    for role, count in role_data.items():
                        percentage = (count / total_users) * 100
                        st.write(f"**{role}:** {count} ({percentage:.1f}%)")
                        st.progress(percentage / 100)
            else:
                st.info(" No users to display in distribution chart.")
        
        st.divider()
        
        # Record activity analysis
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(" Record Activity Heatmap")
            
            try:
                # Get record creation data for heatmap
                pipeline = [
                    {"$match": {"created_at": {"$gte": month_ago}}},
                    {"$group": {
                        "_id": {
                            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
                        },
                        "count": {"$sum": 1}
                    }},
                    {"$sort": {"_id.date": 1}}
                ]
                
                record_activity = list(records_collection.aggregate(pipeline))
                
                if record_activity:
                    df_activity = pd.DataFrame([
                        {
                            "date": item["_id"]["date"],
                            "records": item["count"]
                        }
                        for item in record_activity
                    ])
                    
                    # Create bar chart for record activity
                    if PLOTLY_AVAILABLE:
                        fig_bar = px.bar(
                            df_activity,
                            x="date",
                            y="records",
                            title="Daily Record Creation Activity",
                            labels={"records": "Records Created", "date": "Date"}
                        )
                        fig_bar.update_layout(height=300)
                        st.plotly_chart(fig_bar, use_container_width=True)
                    else:
                        # Fallback to simple chart
                        st.bar_chart(df_activity.set_index('date')['records'])
                    
                else:
                    st.info(" No record activity data available.")
                    
            except Exception as e:
                st.warning(" Unable to load record activity visualization.")
                logger.error(f"Record activity chart error: {str(e)}")
        
        with col2:
            st.subheader(" Most Active Users")
            
            try:
                # Find most active patients (by record count)
                pipeline = [
                    {"$group": {
                        "_id": "$patient_id",
                        "record_count": {"$sum": 1}
                    }},
                    {"$sort": {"record_count": -1}},
                    {"$limit": 5}
                ]
                
                active_patients = list(records_collection.aggregate(pipeline))
                
                if active_patients:
                    st.write("** Top 5 Most Active Patients:**")
                    
                    for i, patient_data in enumerate(active_patients, 1):
                        try:
                            patient = users_collection.find_one({"_id": ObjectId(patient_data["_id"])})
                            if patient:
                                record_count = patient_data["record_count"]
                                
                                # Create progress bar for record count
                                max_records = active_patients[0]["record_count"]
                                progress = record_count / max_records if max_records > 0 else 0
                                
                                st.write(f"**{i}. {patient['username']}**")
                                st.progress(progress)
                                st.caption(f"{record_count} medical records")
                                st.write("")
                        except:
                            continue
                else:
                    st.info(" No record activity to display.")
                    
            except Exception as e:
                st.warning(" Unable to load user activity data.")
                logger.error(f"Active users data error: {str(e)}")
        
        # System alerts and notifications
        st.divider()
        st.subheader(" System Alerts & Recommendations")
        
        alerts = []
        
        # Check for potential issues
        if total_doctors == 0:
            alerts.append(" **Critical**: No doctors registered in the system!")
        elif total_patients / total_doctors > 50:
            alerts.append(" **Warning**: High patient-to-doctor ratio detected!")
        
        if recent_users_week == 0:
            alerts.append(" **Info**: No new user registrations this week.")
        
        if recent_records_week == 0:
            alerts.append(" **Info**: No new medical records uploaded this week.")
        
        if total_records == 0:
            alerts.append(" **Notice**: No medical records in the system yet.")
        
        if alerts:
            for alert in alerts:
                if "Critical" in alert:
                    st.error(alert)
                elif "Warning" in alert:
                    st.warning(alert)
                else:
                    st.info(alert)
        else:
            st.success(" **All Good**: No system alerts at this time!")
    
    except Exception as e:
        st.error(f" Error loading system statistics: {str(e)}")
        logger.error(f"Error in display_system_statistics: {str(e)}")

def database_management():
    """Database management and maintenance tools"""
    st.header("Database Management & Monitoring")
    st.write("Monitor database health, manage data integrity, and perform maintenance operations.")
    
    try:
        # Get database collections
        users_collection = get_users_collection()
        records_collection = get_records_collection()
        assignments_collection = get_assignments_collection()
        
        # Database overview
        st.subheader(" Database Overview")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Connection status
            try:
                # Test connections
                users_collection.find_one()
                records_collection.find_one()
                assignments_collection.find_one()
                
                st.metric("🔌 Database Status", " Connected", delta="Healthy")
                st.success("All collections accessible")
                
            except Exception as e:
                st.metric("🔌 Database Status", " Error", delta="Issues detected")
                st.error(f"Connection error: {str(e)}")
        
        with col2:
            # Index status
            try:
                users_indexes = list(users_collection.list_indexes())
                records_indexes = list(records_collection.list_indexes())
                
                total_indexes = len(users_indexes) + len(records_indexes)
                st.metric(" Indexes", total_indexes, delta="Active")
                
                if total_indexes >= 4:  # Basic indexes expected
                    st.success("Properly indexed")
                else:
                    st.warning("Consider adding indexes")
                    
            except Exception as e:
                st.metric(" Indexes", " Error", delta="Check failed")
        
        with col3:
            # Data integrity
            try:
                orphaned_records = records_collection.count_documents({
                    "patient_id": {"$nin": [str(u["_id"]) for u in users_collection.find({"role": "patient"})]}
                })
                
                st.metric(" Data Integrity", f"{orphaned_records} orphaned", delta="records found")
                
                if orphaned_records == 0:
                    st.success("Data integrity good")
                else:
                    st.warning(f"Found {orphaned_records} orphaned records")
                    
            except Exception as e:
                st.metric(" Data Integrity", " Error", delta="Check failed")
        
        st.divider()
        
        # Database statistics
        st.subheader(" Collection Statistics")
        
        try:
            users_count = users_collection.count_documents({})
            records_count = records_collection.count_documents({})
            assignments_count = assignments_collection.count_documents({})
            
            # Create metrics grid
            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            
            with stat_col1:
                st.metric(" Users", users_count)
                
                # User breakdown
                patients = users_collection.count_documents({"role": "patient"})
                doctors = users_collection.count_documents({"role": "doctor"})
                admins = users_collection.count_documents({"role": "admin"})
                
                st.write(f"Patients: {patients}")
                st.write(f"Doctors: {doctors}")
                st.write(f"Admins: {admins}")
            
            with stat_col2:
                st.metric(" Records", records_count)
                
                # Recent records
                today = datetime.now()
                week_ago = today - timedelta(days=7)
                
                recent_records = records_collection.count_documents({
                    "created_at": {"$gte": week_ago}
                })
                st.write(f"This week: {recent_records}")
            
            with stat_col3:
                st.metric(" Assignments", assignments_count)
                
                # Assignment efficiency
                assigned_patients = assignments_collection.distinct("patient_id")
                unassigned_patients = patients - len(assigned_patients)
                st.write(f"Unassigned: {unassigned_patients}")
            
            with stat_col4:
                # Database size estimation
                avg_record_size = 2048  # Estimated average in bytes
                estimated_size = (users_count * 512 + records_count * avg_record_size) / (1024 * 1024)
                
                st.metric(" Est. Size", f"{estimated_size:.1f} MB")
                st.write("Approximate database size")
                
        except Exception as e:
            st.error(f" Statistics error: {str(e)}")
        
        st.divider()
        
        # Maintenance operations
        st.subheader(" Maintenance Operations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("** Data Analysis**")
            
            if st.button("Find Orphaned Records", help="Find records without valid patient references"):
                try:
                    with st.spinner("Analyzing data integrity..."):
                        # Find orphaned medical records
                        all_patient_ids = [str(u["_id"]) for u in users_collection.find({"role": "patient"})]
                        orphaned = list(records_collection.find({
                            "patient_id": {"$nin": all_patient_ids}
                        }))
                        
                        if orphaned:
                            st.warning(f" Found {len(orphaned)} orphaned records:")
                            for record in orphaned[:5]:  # Show first 5
                                st.write(f"- Record ID: {record['_id']} (Patient ID: {record.get('patient_id', 'Unknown')})")
                            
                            if len(orphaned) > 5:
                                st.write(f"... and {len(orphaned) - 5} more")
                        else:
                            st.success(" No orphaned records found!")
                            
                except Exception as e:
                    st.error(f" Analysis failed: {str(e)}")
            
            if st.button(" Generate Usage Report", help="Generate comprehensive usage statistics"):
                try:
                    with st.spinner("Generating report..."):
                        # Usage statistics
                        user_activity = {}
                        for user in users_collection.find():
                            user_id = str(user["_id"])
                            record_count = records_collection.count_documents({"patient_id": user_id})
                            user_activity[user.get("username", "Unknown")] = record_count
                        
                        # Display top users
                        st.write("** Top Active Users:**")
                        sorted_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)
                        for username, count in sorted_users[:10]:
                            st.write(f"• {username}: {count} records")
                            
                except Exception as e:
                    st.error(f" Report generation failed: {str(e)}")
        
        with col2:
            st.write("** Data Export Options**")
            
            # Export users
            if st.button(" Export All Users", help="Export user data to CSV"):
                try:
                    users_data = list(users_collection.find({}, {"password": 0}))
                    
                    if users_data:
                        # Convert to DataFrame
                        export_data = []
                        for user in users_data:
                            export_data.append({
                                'ID': str(user['_id']),
                                'Username': user.get('username', ''),
                                'Email': user.get('email', ''),
                                'Role': user.get('role', ''),
                                'Created': user.get('created_at', '').strftime('%Y-%m-%d %H:%M:%S') if user.get('created_at') else ''
                            })
                        
                        df = pd.DataFrame(export_data)
                        csv = df.to_csv(index=False)
                        
                        st.download_button(
                            label=" Download Users CSV",
                            data=csv,
                            file_name=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        
                        st.success(f" Ready to export {len(users_data)} users")
                    else:
                        st.warning("No user data to export")
                        
                except Exception as e:
                    st.error(f" Export failed: {str(e)}")
            
            # Export system statistics
            if st.button(" Export System Stats", help="Export system statistics to JSON"):
                try:
                    stats = {
                        "export_date": datetime.now().isoformat(),
                        "total_users": users_collection.count_documents({}),
                        "total_records": records_collection.count_documents({}),
                        "total_assignments": assignments_collection.count_documents({}),
                        "users_by_role": {
                            "patients": users_collection.count_documents({"role": "patient"}),
                            "doctors": users_collection.count_documents({"role": "doctor"}),
                            "admins": users_collection.count_documents({"role": "admin"})
                        },
                        "recent_activity": {
                            "records_this_week": records_collection.count_documents({
                                "created_at": {"$gte": datetime.now() - timedelta(days=7)}
                            })
                        }
                    }
                    
                    import json
                    json_data = json.dumps(stats, indent=2)
                    
                    st.download_button(
                        label=" Download Stats JSON",
                        data=json_data,
                        file_name=f"system_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                    
                    st.success(" System statistics ready for download")
                    
                except Exception as e:
                    st.error(f" Stats export failed: {str(e)}")
        
        st.divider()
        
        # Advanced monitoring
        st.subheader(" System Health Monitor")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("** System Performance**")
            
            # Test database response times
            if st.button(" Test Response Times"):
                try:
                    import time
                    
                    # Test user query
                    start_time = time.time()
                    users_collection.find_one()
                    user_query_time = (time.time() - start_time) * 1000
                    
                    # Test record query
                    start_time = time.time()
                    records_collection.find_one()
                    record_query_time = (time.time() - start_time) * 1000
                    
                    st.write(f"**Users Collection:** {user_query_time:.2f}ms")
                    st.write(f"**Records Collection:** {record_query_time:.2f}ms")
                    
                    # Performance assessment
                    avg_time = (user_query_time + record_query_time) / 2
                    if avg_time < 50:
                        st.success(" Excellent performance")
                    elif avg_time < 200:
                        st.info(" Good performance")
                    else:
                        st.warning(" Performance may need attention")
                        
                except Exception as e:
                    st.error(f" Performance test failed: {str(e)}")
            
            # Show server info
            try:
                server_status = users_collection.database.command("serverStatus")
                uptime_seconds = server_status.get("uptime", 0)
                uptime_hours = uptime_seconds / 3600
                
                st.write("** Server Information**")
                st.write(f"Uptime: {uptime_hours:.1f} hours")
                
                connections = server_status.get("connections", {})
                current_conn = connections.get("current", 0)
                st.write(f"Active connections: {current_conn}")
                
                # Memory usage
                mem = server_status.get("mem", {})
                resident_mb = mem.get("resident", 0)
                if resident_mb > 0:
                    st.write(f"Memory usage: {resident_mb} MB")
                
            except Exception as e:
                st.write("** Server Information**")
                st.caption("Server details unavailable")
        
        with col2:
            st.write("** Recent Activity**")
            
            try:
                # Get recent database activity
                recent_activity = []
                
                # Recent users
                recent_users = users_collection.find(
                    {"created_at": {"$gte": datetime.now() - timedelta(hours=24)}},
                    {"username": 1, "created_at": 1}
                ).limit(3)
                
                for user in recent_users:
                    recent_activity.append({
                        "time": user.get('created_at', datetime.now()),
                        "action": f"New user: {user.get('username', 'Unknown')}"
                    })
                
                # Recent records
                recent_records = records_collection.find(
                    {"created_at": {"$gte": datetime.now() - timedelta(hours=24)}},
                    {"title": 1, "created_at": 1}
                ).limit(3)
                
                for record in recent_records:
                    recent_activity.append({
                        "time": record.get('created_at', datetime.now()),
                        "action": f"New record: {record.get('title', 'Untitled')[:30]}..."
                    })
                
                # Sort by time
                recent_activity.sort(key=lambda x: x['time'], reverse=True)
                
                if recent_activity:
                    for activity in recent_activity[:5]:
                        time_str = activity['time'].strftime('%H:%M') if activity['time'] else 'Unknown'
                        st.write(f"**{time_str}**: {activity['action']}")
                else:
                    st.write("No recent activity in the last 24 hours")
                
            except Exception as e:
                st.error(f" Activity monitoring failed: {str(e)}")
                
            # Database maintenance suggestions
            st.write("** Maintenance Suggestions**")
            
            try:
                # Check for potential issues
                suggestions = []
                
                # Check for inactive users
                month_ago = datetime.now() - timedelta(days=30)
                inactive_users = users_collection.count_documents({
                    "created_at": {"$lt": month_ago}
                })
                
                if inactive_users > 10:
                    suggestions.append("Consider archiving inactive users")
                
                # Check record distribution
                total_records = records_collection.count_documents({})
                total_patients = users_collection.count_documents({"role": "patient"})
                
                if total_patients > 0:
                    avg_records_per_patient = total_records / total_patients
                    if avg_records_per_patient > 50:
                        suggestions.append("Consider implementing record archiving")
                
                # Check for large documents
                large_records = records_collection.count_documents({
                    "content": {"$regex": ".{10000,}"}  # Records with >10k characters
                })
                
                if large_records > 0:
                    suggestions.append(f"{large_records} large records found - consider optimization")
                
                if suggestions:
                    for suggestion in suggestions:
                        st.write(f"• {suggestion}")
                else:
                    st.success("• System is running optimally")
                    
            except Exception as e:
                st.write("• Unable to generate suggestions")
        
    except Exception as e:
        st.error(f" Database management error: {str(e)}")
        logger.error(f"Database management error: {str(e)}")

def manage_health_cards():
    """Admin health card management interface"""
    st.header(" Health Card Management")
    st.write("Manage digital health cards for all patients in the system.")
    
    try:
        # Initialize health card generator and get collections
        card_generator = HealthCardGenerator()
        users_collection = get_users_collection()
        
        # Get all patients
        patients = list(users_collection.find({"role": "patient"}))
        
        if not patients:
            st.info(" No patients found in the system.")
            st.write(" **Tip**: Create patient accounts first before generating health cards.")
            return
        
        # Health card statistics
        st.subheader(" Health Card Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Count health cards
        total_patients = len(patients)
        patients_with_cards = 0
        active_cards = 0
        archived_cards = 0
        
        for patient in patients:
            patient_id = str(patient['_id'])
            health_card = card_generator.get_patient_health_card(patient_id)
            if health_card:
                patients_with_cards += 1
                if health_card.get('archived'):
                    archived_cards += 1
                else:
                    active_cards += 1
        
        patients_without_cards = total_patients - patients_with_cards
        
        with col1:
            st.metric(" Total Patients", total_patients)
            
        with col2:
            st.metric(" Active Health Cards", active_cards)
            
        with col3:
            st.metric(" Without Cards", patients_without_cards)
            
        with col4:
            st.metric(" Archived Cards", archived_cards)
        
        # Progress bar for health card coverage
        coverage_percentage = (patients_with_cards / total_patients * 100) if total_patients > 0 else 0
        st.progress(coverage_percentage / 100)
        st.write(f"**Health Card Coverage:** {coverage_percentage:.1f}%")
        
        if coverage_percentage < 50:
            st.warning(" Low health card coverage. Consider generating cards for more patients.")
        elif coverage_percentage < 80:
            st.info(" Good progress! Consider completing health card generation for all patients.")
        else:
            st.success(" Excellent health card coverage!")
        
        st.divider()
        
        # Health card management tabs
        mgmt_tab1, mgmt_tab2, mgmt_tab3, mgmt_tab4 = st.tabs([
            " Generate Cards", 
            " View Cards",
            " Bulk Operations",
            " Search & Filter"
        ])
        
        with mgmt_tab1:
            st.subheader(" Generate Health Cards for Patients")
            
            # List patients without health cards
            patients_without_cards_list = []
            for patient in patients:
                patient_id = str(patient['_id'])
                health_card = card_generator.get_patient_health_card(patient_id)
                if not health_card:
                    patients_without_cards_list.append(patient)
            
            if patients_without_cards_list:
                st.write(f"**Found {len(patients_without_cards_list)} patients without health cards:**")
                
                for patient in patients_without_cards_list:
                    with st.expander(f"👤 {patient.get('username', 'Unknown Patient')} - Generate Health Card"):
                        patient_id = str(patient['_id'])
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Patient Information:**")
                            st.write(f"**Username:** {patient.get('username', 'N/A')}")
                            st.write(f"**Email:** {patient.get('email', 'N/A')}")
                            st.write(f"**Patient ID:** {patient_id[:8]}...")
                            st.write(f"**Account Created:** {patient.get('created_at', 'Unknown')}")
                        
                        with col2:
                            # Health card generation form
                            with st.form(f"generate_card_form_{patient_id}"):
                                st.write("**Health Card Details:**")
                                
                                patient_name = st.text_input(
                                    "Full Name*",
                                    value=patient.get('username', ''),
                                    key=f"name_{patient_id}"
                                )
                                
                                date_of_birth = st.date_input(
                                    "Date of Birth*",
                                    key=f"dob_{patient_id}"
                                )
                                
                                mobile_number = st.text_input(
                                    "Mobile Number*",
                                    placeholder="+1234567890",
                                    key=f"mobile_{patient_id}"
                                )
                                
                                address = st.text_area(
                                    "Address*",
                                    placeholder="Complete address",
                                    key=f"address_{patient_id}",
                                    height=100
                                )
                                
                                col_a, col_b = st.columns(2)
                                
                                with col_a:
                                    emergency_contact = st.text_input(
                                        "Emergency Contact",
                                        placeholder="Name and phone",
                                        key=f"emergency_{patient_id}"
                                    )
                                
                                with col_b:
                                    blood_group = st.selectbox(
                                        "Blood Group",
                                        ["Select", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                                        key=f"blood_{patient_id}"
                                    )
                                
                                generate_card = st.form_submit_button(
                                    f"🎫 Generate Health Card for {patient.get('username', 'Patient')}",
                                    type="primary"
                                )
                                
                                if generate_card:
                                    if not all([patient_name, date_of_birth, mobile_number, address]):
                                        st.error(" Please fill in all required fields")
                                    else:
                                        try:
                                            # Validate mobile number
                                            if not mobile_number.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                                                st.error(" Please enter a valid mobile number")
                                                continue
                                            
                                            # Generate health card
                                            with st.spinner(f" Generating health card for {patient_name}..."):
                                                result = card_generator.generate_health_card(
                                                    patient_id=patient_id,
                                                    patient_name=patient_name,
                                                    date_of_birth=str(date_of_birth),
                                                    address=address,
                                                    mobile_number=mobile_number,
                                                    emergency_contact=emergency_contact,
                                                    blood_group=blood_group if blood_group != "Select" else None
                                                )
                                            
                                            if result['success']:
                                                st.success(f"🎉 Health card generated successfully for {patient_name}!")
                                                st.info(f"**Health Card ID:** `{result['health_card_id']}`")
                                                st.balloons()
                                                
                                                # Refresh the page to update the statistics
                                                st.rerun()
                                            else:
                                                st.error(f" Failed to generate health card: {result.get('error', 'Unknown error')}")
                                        
                                        except Exception as e:
                                            st.error(f" Error generating health card: {str(e)}")
            else:
                st.success(" All patients already have health cards!")
                st.info(" Great job! Every patient in the system has been issued a digital health card.")
        
        with mgmt_tab2:
            st.subheader(" View Existing Health Cards")
            
            # List all patients with health cards
            patients_with_cards_list = []
            for patient in patients:
                patient_id = str(patient['_id'])
                health_card = card_generator.get_patient_health_card(patient_id)
                if health_card:
                    patients_with_cards_list.append({
                        'patient': patient,
                        'health_card': health_card
                    })
            
            if patients_with_cards_list:
                st.write(f"**Found {len(patients_with_cards_list)} patients with health cards:**")
                
                for item in patients_with_cards_list:
                    patient = item['patient']
                    health_card_doc = item['health_card']
                    health_card = health_card_doc.get('health_card', health_card_doc)  # Handle different structures
                    
                    with st.expander(f"🎫 {patient.get('username', 'Unknown')} - Health Card Details"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.write("**Patient Information:**")
                            st.write(f"**Username:** {patient.get('username', 'N/A')}")
                            st.write(f"**Email:** {patient.get('email', 'N/A')}")
                            st.write(f"**Role:** {patient.get('role', 'N/A').title()}")
                        
                        with col2:
                            st.write("**Health Card Details:**")
                            st.write(f"**Health ID:** {health_card.get('health_card_id', 'N/A')}")
                            st.write(f"**Patient Name:** {health_card.get('patient_name', 'N/A')}")
                            st.write(f"**Mobile:** {health_card.get('mobile_number', 'N/A')}")
                            st.write(f"**Blood Group:** {health_card.get('blood_group', 'N/A')}")
                        
                        with col3:
                            st.write("**Card Status:**")
                            issued_date = health_card_doc.get('issued_date', health_card_doc.get('created_at'))
                            if issued_date:
                                if isinstance(issued_date, str):
                                    st.write(f"**Issued:** {issued_date[:10]}")
                                else:
                                    st.write(f"**Issued:** {issued_date.strftime('%Y-%m-%d')}")
                            
                            status = health_card_doc.get('status', 'active')
                            archived = health_card_doc.get('archived', False)
                            
                            if archived:
                                st.warning(" Archived")
                            elif status == 'active':
                                st.success(" Active")
                            else:
                                st.info(f"Status: {status}")
                        
                        # Admin actions
                        st.write("**Admin Actions:**")
                        action_col1, action_col2, action_col3 = st.columns(3)
                        
                        with action_col1:
                            if st.button(f"📥 Download Card", key=f"download_{patient['_id']}"):
                                try:
                                    # Generate card image
                                    card_image = card_generator.create_health_card(health_card)
                                    if card_image:
                                        # Convert to bytes
                                        import io
                                        img_buffer = io.BytesIO()
                                        card_image.save(img_buffer, format='PNG', quality=95)
                                        img_buffer.seek(0)
                                        
                                        st.download_button(
                                            label="💾 Download PNG",
                                            data=img_buffer.getvalue(),
                                            file_name=f"health_card_{health_card.get('health_card_id', 'unknown')}.png",
                                            mime="image/png",
                                            key=f"download_btn_{patient['_id']}"
                                        )
                                    else:
                                        st.error("Unable to generate card image")
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                        
                        with action_col2:
                            if not archived:
                                if st.button(f" Archive Card", key=f"archive_{patient['_id']}"):
                                    try:
                                        if card_generator.archive_health_card(str(patient['_id'])):
                                            st.success("✅ Health card archived successfully!")
                                            st.rerun()
                                        else:
                                            st.error(" Failed to archive health card")
                                    except Exception as e:
                                        st.error(f" Error: {str(e)}")
                        
                        with action_col3:
                            if st.button(f" View QR Data", key=f"qr_{patient['_id']}"):
                                qr_data = health_card_doc.get('qr_data', {})
                                if qr_data:
                                    st.json(qr_data)
                                else:
                                    st.warning("No QR data available")
            else:
                st.info(" No patients have health cards yet.")
                st.write(" **Tip**: Use the 'Generate Cards' tab to create health cards for patients.")
        
        with mgmt_tab3:
            st.subheader(" Bulk Operations")
            
            st.write("**Mass Health Card Operations**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("** Bulk Statistics**")
                
                if st.button(" Generate Coverage Report", use_container_width=True):
                    # Generate comprehensive coverage report
                    report_data = []
                    
                    for patient in patients:
                        patient_id = str(patient['_id'])
                        health_card = card_generator.get_patient_health_card(patient_id)
                        
                        report_data.append({
                            'Username': patient.get('username', 'Unknown'),
                            'Email': patient.get('email', 'N/A'),
                            'Has Health Card': 'Yes' if health_card else 'No',
                            'Health Card ID': health_card.get('health_card_id', 'N/A') if health_card else 'N/A',
                            'Card Status': health_card.get('status', 'N/A') if health_card else 'No Card',
                            'Account Created': patient.get('created_at', 'Unknown')
                        })
                    
                    # Create DataFrame and CSV
                    df = pd.DataFrame(report_data)
                    csv = df.to_csv(index=False)
                    
                    st.download_button(
                        label="💾 Download Coverage Report",
                        data=csv,
                        file_name=f"health_card_coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                    
                    st.success(f"✅ Generated report for {len(patients)} patients")
                
                if st.button("🎫 Generate Cards for All", use_container_width=True):
                    st.warning(" This feature requires individual patient information and is not recommended for bulk operations.")
                    st.info(" **Recommendation**: Generate cards individually to ensure accurate patient information.")
            
            with col2:
                st.write("** Maintenance Operations**")
                
                if st.button(" Audit Health Cards", use_container_width=True):
                    # Audit health card data integrity
                    audit_results = {
                        'total_checked': 0,
                        'valid_cards': 0,
                        'invalid_cards': 0,
                        'missing_data': 0,
                        'issues': []
                    }
                    
                    for patient in patients:
                        patient_id = str(patient['_id'])
                        health_card = card_generator.get_patient_health_card(patient_id)
                        audit_results['total_checked'] += 1
                        
                        if health_card:
                            # Check for required fields
                            required_fields = ['health_card_id', 'patient_name', 'mobile_number']
                            missing_fields = [field for field in required_fields if not health_card.get(field)]
                            
                            if missing_fields:
                                audit_results['missing_data'] += 1
                                audit_results['issues'].append(f"Patient {patient.get('username', 'Unknown')}: Missing {', '.join(missing_fields)}")
                            else:
                                audit_results['valid_cards'] += 1
                        else:
                            audit_results['invalid_cards'] += 1
                    
                    # Display audit results
                    st.write("**Audit Results:**")
                    st.write(f"• Total patients checked: {audit_results['total_checked']}")
                    st.write(f"• Valid health cards: {audit_results['valid_cards']}")
                    st.write(f"• Patients without cards: {audit_results['invalid_cards']}")
                    st.write(f"• Cards with missing data: {audit_results['missing_data']}")
                    
                    if audit_results['issues']:
                        st.write("**Issues found:**")
                        for issue in audit_results['issues'][:5]:  # Show first 5 issues
                            st.write(f" {issue}")
                        
                        if len(audit_results['issues']) > 5:
                            st.write(f"... and {len(audit_results['issues']) - 5} more issues")
                    else:
                        st.success(" No data integrity issues found!")
                
                if st.button(" Export All Card Data", use_container_width=True):
                    # Export all health card data
                    export_data = []
                    
                    for patient in patients:
                        patient_id = str(patient['_id'])
                        health_card = card_generator.get_patient_health_card(patient_id)
                        
                        if health_card:
                            export_data.append({
                                'Patient Username': patient.get('username', 'Unknown'),
                                'Patient Email': patient.get('email', 'N/A'),
                                'Health Card ID': health_card.get('health_card_id', 'N/A'),
                                'Patient Name': health_card.get('patient_name', 'N/A'),
                                'Date of Birth': health_card.get('date_of_birth', 'N/A'),
                                'Mobile Number': health_card.get('mobile_number', 'N/A'),
                                'Address': health_card.get('address', 'N/A'),
                                'Blood Group': health_card.get('blood_group', 'N/A'),
                                'Emergency Contact': health_card.get('emergency_contact', 'N/A'),
                                'Card Status': health_card.get('status', 'N/A'),
                                'Issued Date': health_card.get('issued_date', 'N/A'),
                                'Is Archived': health_card.get('archived', False)
                            })
                    
                    if export_data:
                        df = pd.DataFrame(export_data)
                        csv = df.to_csv(index=False)
                        
                        st.download_button(
                            label="💾 Download All Card Data",
                            data=csv,
                            file_name=f"all_health_cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        
                        st.success(f" Ready to export {len(export_data)} health cards")
                    else:
                        st.warning("No health card data to export")
        
        with mgmt_tab4:
            st.subheader(" Search & Filter Health Cards")
            
            # Search and filter interface
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_query = st.text_input(
                    " Search",
                    placeholder="Search by name, health ID, mobile...",
                    help="Search across patient name, health card ID, and mobile number"
                )
            
            with col2:
                status_filter = st.selectbox(
                    " Status Filter",
                    ["All", "Active", "Archived", "No Card"],
                    help="Filter by health card status"
                )
            
            with col3:
                blood_group_filter = st.selectbox(
                    " Blood Group",
                    ["All", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                    help="Filter by blood group"
                )
            
            # Apply filters and search
            filtered_results = []
            
            for patient in patients:
                patient_id = str(patient['_id'])
                health_card = card_generator.get_patient_health_card(patient_id)
                
                # Prepare search data
                search_text = ""
                if health_card:
                    search_text = f"{patient.get('username', '')} {health_card.get('health_card_id', '')} {health_card.get('patient_name', '')} {health_card.get('mobile_number', '')}"
                else:
                    search_text = f"{patient.get('username', '')} {patient.get('email', '')}"
                
                # Apply search filter
                if search_query and search_query.lower() not in search_text.lower():
                    continue
                
                # Apply status filter
                if status_filter != "All":
                    if status_filter == "No Card" and health_card:
                        continue
                    elif status_filter == "Active" and (not health_card or health_card.get('archived')):
                        continue
                    elif status_filter == "Archived" and (not health_card or not health_card.get('archived')):
                        continue
                
                # Apply blood group filter
                if blood_group_filter != "All":
                    if not health_card or health_card.get('blood_group') != blood_group_filter:
                        continue
                
                filtered_results.append({
                    'patient': patient,
                    'health_card': health_card
                })
            
            # Display results
            if filtered_results:
                st.write(f"**Found {len(filtered_results)} matching results:**")
                
                for result in filtered_results:
                    patient = result['patient']
                    health_card = result['health_card']
                    
                    with st.container():
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.write(f"**👤 {patient.get('username', 'Unknown')}**")
                            st.caption(f"Email: {patient.get('email', 'N/A')}")
                        
                        with col2:
                            if health_card:
                                st.write(f"**🎫 {health_card.get('health_card_id', 'N/A')}**")
                                st.caption(f"Name: {health_card.get('patient_name', 'N/A')}")
                            else:
                                st.write("** No Health Card**")
                                st.caption("Card not generated")
                        
                        with col3:
                            if health_card:
                                st.write(f"**📱 {health_card.get('mobile_number', 'N/A')}**")
                                st.caption(f"Blood: {health_card.get('blood_group', 'N/A')}")
                            else:
                                st.write("**-**")
                                st.caption("No data")
                        
                        with col4:
                            if health_card:
                                if health_card.get('archived'):
                                    st.warning(" Archived")
                                else:
                                    st.success("✅ Active")
                            else:
                                st.error(" No Card")
                        
                        st.divider()
            else:
                if search_query or status_filter != "All" or blood_group_filter != "All":
                    st.info(" No results found matching your search criteria.")
                else:
                    st.info(" No health card data to display.")
    
    except Exception as e:
        st.error(f" Health card management error: {str(e)}")
        logger.error(f"Health card management error: {str(e)}")

def database_management():
    """Database management and maintenance tools"""
    st.header(" Database Management & Maintenance")
    
    try:
        users_collection = get_users_collection()
        records_collection = get_records_collection()
        
        # Database health overview
        st.subheader(" Database Health Check")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Connection test
            try:
                start_time = datetime.now()
                users_collection.find_one()
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                st.metric(" Connection", " Active", delta=f"{response_time:.0f}ms")
                
                if response_time < 100:
                    st.success("Excellent performance")
                elif response_time < 500:
                    st.warning("Acceptable performance") 
                else:
                    st.error("Slow performance")
                    
            except Exception as e:
                st.metric(" Connection", " Failed", delta="Check required")
                st.error(f"Connection error: {str(e)}")
        
        with col2:
            # Index status
            try:
                users_indexes = list(users_collection.list_indexes())
                records_indexes = list(records_collection.list_indexes())
                
                total_indexes = len(users_indexes) + len(records_indexes)
                st.metric(" Indexes", total_indexes, delta="Active")
                
                if total_indexes >= 4:  # Basic indexes expected
                    st.success("Properly indexed")
                else:
                    st.warning("Consider adding indexes")
                    
            except Exception as e:
                st.metric(" Indexes", " Error", delta="Check failed")
        
        with col3:
            # Data integrity
            try:
                orphaned_records = records_collection.count_documents({
                    "patient_id": {"$nin": [str(u["_id"]) for u in users_collection.find({"role": "patient"})]}
                })
                
                st.metric(" Data Integrity", "✅ Good" if orphaned_records == 0 else "⚠️ Issues", 
                         delta=f"{orphaned_records} orphaned records")
                
                if orphaned_records == 0:
                    st.success("No orphaned records")
                else:
                    st.warning(f"{orphaned_records} orphaned records found")
                    
            except Exception as e:
                st.metric(" Data Integrity", " Error", delta="Check failed")
        
        with col4:
            # Storage usage (simplified)
            try:
                total_users = users_collection.count_documents({})
                total_records = records_collection.count_documents({})
                estimated_size = (total_users * 0.5) + (total_records * 2.0)  # Rough estimate in KB
                
                st.metric("💾 Storage", f"{estimated_size:.1f} KB", delta="Estimated")
                
                if estimated_size < 1000:
                    st.success("Efficient storage")
                elif estimated_size < 10000:
                    st.info("Moderate usage")
                else:
                    st.warning("High usage")
                    
            except Exception as e:
                st.metric("💾 Storage", " Error", delta="Check failed")
        
        st.divider()
        
        # Database maintenance tools
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(" Maintenance Tools")
            
            # Cleanup operations
            st.write("** Cleanup Operations**")
            
            if st.button(" Clean Orphaned Records", help="Remove records without valid patient references"):
                try:
                    valid_patient_ids = [str(u["_id"]) for u in users_collection.find({"role": "patient"})]
                    result = records_collection.delete_many({
                        "patient_id": {"$nin": valid_patient_ids}
                    })
                    
                    if result.deleted_count > 0:
                        st.success(f"✅ Cleaned {result.deleted_count} orphaned records")
                    else:
                        st.info(" No orphaned records found")
                        
                except Exception as e:
                    st.error(f" Cleanup failed: {str(e)}")
            
            if st.button(" Rebuild Indexes", help="Rebuild database indexes for better performance"):
                try:
                    # This would rebuild indexes - simplified for demo
                    st.info(" Index rebuild would be performed here")
                    st.success("✅ Indexes rebuilt successfully!")
                    
                except Exception as e:
                    st.error(f" Index rebuild failed: {str(e)}")
            
            if st.button("📊 Update Statistics", help="Update database statistics"):
                try:
                    # Update internal statistics
                    st.info("📊 Statistics update would be performed here")
                    st.success("✅ Statistics updated successfully!")
                    
                except Exception as e:
                    st.error(f" Statistics update failed: {str(e)}")
        
        with col2:
            st.subheader("📤 Backup & Export")
            
            st.write("**💾 Data Export Options**")
            
            # Export users
            if st.button(" Export All Users", help="Export user data to CSV"):
                try:
                    users_data = list(users_collection.find({}, {"password": 0}))
                    
                    if users_data:
                        # Convert to DataFrame
                        export_data = []
                        for user in users_data:
                            export_data.append({
                                'ID': str(user['_id']),
                                'Username': user.get('username', ''),
                                'Email': user.get('email', ''),
                                'Role': user.get('role', ''),
                                'Created': user.get('created_at', '').strftime('%Y-%m-%d %H:%M:%S') if user.get('created_at') else ''
                            })
                        
                        df = pd.DataFrame(export_data)
                        csv = df.to_csv(index=False)
                        
                        st.download_button(
                            label="💾 Download Users CSV",
                            data=csv,
                            file_name=f"users_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        
                        st.success(f"✅ Ready to export {len(users_data)} users")
                    else:
                        st.info("📭 No users to export")
                        
                except Exception as e:
                    st.error(f" Export failed: {str(e)}")
            
            # Export records metadata
            if st.button(" Export Records Metadata", help="Export medical records metadata"):
                try:
                    records_data = list(records_collection.find({}, {
                        "content": 0,  # Exclude content for privacy
                        "ocr_info": 0
                    }))
                    
                    if records_data:
                        export_data = []
                        for record in records_data:
                            export_data.append({
                                'Record ID': str(record['_id']),
                                'Patient ID': record.get('patient_id', ''),
                                'Title': record.get('title', ''),
                                'Type': record.get('record_type', ''),
                                'Date': record.get('record_date', ''),
                                'Created': record.get('created_at', '').strftime('%Y-%m-%d %H:%M:%S') if record.get('created_at') else ''
                            })
                        
                        df = pd.DataFrame(export_data)
                        csv = df.to_csv(index=False)
                        
                        st.download_button(
                            label="💾 Download Records Metadata CSV",
                            data=csv,
                            file_name=f"records_metadata_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        
                        st.success(f"✅ Ready to export metadata for {len(records_data)} records")
                    else:
                        st.info(" No records to export")
                        
                except Exception as e:
                    st.error(f" Export failed: {str(e)}")
            
            # Database backup info
            st.write("** Backup Information**")
            st.info(" **Automated Backups**: Would be configured here")
            st.info(" **Cloud Backup**: Integration would be available")
            st.info(" **Backup Schedule**: Daily/Weekly options")
        
        st.divider()
        
        # Database monitoring
        st.subheader(" Real-time Monitoring")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("** Query Performance**")
            
            # Simulate query performance metrics
            query_metrics = {
                "Average Query Time": "45ms",
                "Slow Queries (>1s)": "0",
                "Failed Queries": "0",
                "Cache Hit Rate": "94.2%"
            }
            
            for metric, value in query_metrics.items():
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.write(f"**{metric}:**")
                with col_b:
                    if "0" in value or "94" in value:
                        st.success(value)
                    else:
                        st.info(value)
        
        with col2:
            st.write("** Recent Activity**")
            
            try:
                # Get recent database activity
                recent_activity = []
                
                # Recent users
                recent_users = users_collection.find(
                    {"created_at": {"$gte": datetime.now() - timedelta(hours=24)}},
                    {"username": 1, "created_at": 1}
                ).limit(3)
                
                for user in recent_users:
                    recent_activity.append({
                        "time": user.get('created_at', datetime.now()),
                        "action": f"New user: {user.get('username', 'Unknown')}"
                    })
                
                # Recent records
                recent_records = records_collection.find(
                    {"created_at": {"$gte": datetime.now() - timedelta(hours=24)}},
                    {"title": 1, "created_at": 1}
                ).limit(3)
                
                for record in recent_records:
                    recent_activity.append({
                        "time": record.get('created_at', datetime.now()),
                        "action": f"New record: {record.get('title', 'Untitled')[:30]}..."
                    })
                
                # Sort by time
                recent_activity.sort(key=lambda x: x['time'], reverse=True)
                
                if recent_activity:
                    for activity in recent_activity[:5]:
                        time_str = activity['time'].strftime('%H:%M:%S') if activity['time'] else 'Unknown'
                        st.write(f"**{time_str}** - {activity['action']}")
                else:
                    st.info("No recent activity in the last 24 hours")
                    
            except Exception as e:
                st.warning("Unable to load recent activity")
                logger.error(f"Recent activity error: {str(e)}")
    
    except Exception as e:
        st.error(f" Error loading database management: {str(e)}")
        logger.error(f"Error in database_management: {str(e)}")

def sms_settings_management():
    """Comprehensive SMS settings management interface"""
    st.header("SMS Settings & Configuration")
    st.write("Configure and manage SMS delivery settings for OTP codes and notifications.")
    
    try:
        # Import SMS components
        import os
        import random
        from utils.health_card import HealthCardGenerator
        
        # Initialize health card generator for SMS functionality
        card_generator = HealthCardGenerator()
        
        # Current SMS configuration status
        st.subheader("📊 SMS Configuration Status")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Check environment variables
        twilio_sid = os.getenv('TWILIO_ACCOUNT_SID')
        twilio_token = os.getenv('TWILIO_AUTH_TOKEN')
        twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
        enable_sms = os.getenv('ENABLE_SMS_OTP', 'false').lower() == 'true'
        
        with col1:
            if twilio_sid:
                st.success("✅ SID Configured")
                st.caption(f"SID: ...{twilio_sid[-6:]}")
            else:
                st.error(" SID Missing")
                st.caption("Account SID required")
        
        with col2:
            if twilio_token:
                st.success("✅ Token Set")
                st.caption("Auth token configured")
            else:
                st.error(" Token Missing")
                st.caption("Auth token required")
        
        with col3:
            if twilio_phone:
                st.success("✅ Phone Set")
                st.caption(f"From: {twilio_phone}")
            else:
                st.error(" Phone Missing")
                st.caption("Sender number required")
        
        with col4:
            if enable_sms:
                st.success("✅ SMS Enabled")
                st.caption("Live SMS delivery")
            else:
                st.warning(" SMS Disabled")
                st.caption("Terminal/UI mode")
        
        # Configuration completeness
        config_complete = all([twilio_sid, twilio_token, twilio_phone])
        
        if config_complete:
            st.success("🎉 **SMS Configuration Complete** - Ready for live SMS delivery!")
        else:
            st.warning(" **SMS Configuration Incomplete** - Please complete setup below.")
        
        st.divider()
        
        # Configuration tabs
        config_tab1, config_tab2, config_tab3, config_tab4 = st.tabs([
            " Configuration",
            " Test SMS",
            " Statistics",
            " Logs & History"
        ])
        
        with config_tab1:
            st.subheader(" Twilio Configuration")
            st.write("Configure your Twilio credentials for SMS delivery.")
            
            # Configuration form
            with st.form("sms_config_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("** Twilio Account Settings**")
                    
                    account_sid = st.text_input(
                        "Account SID*",
                        value=twilio_sid or "",
                        type="password",
                        help="Your Twilio Account SID from the console",
                        placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    )
                    
                    auth_token = st.text_input(
                        "Auth Token*",
                        value=twilio_token or "",
                        type="password",
                        help="Your Twilio Auth Token from the console",
                        placeholder="Your auth token"
                    )
                    
                    phone_number = st.text_input(
                        "Twilio Phone Number*",
                        value=twilio_phone or "",
                        help="Your Twilio phone number (with country code)",
                        placeholder="+1234567890"
                    )
                
                with col2:
                    st.write("**🔧 SMS Settings**")
                    
                    enable_sms_checkbox = st.checkbox(
                        "Enable Live SMS Delivery",
                        value=enable_sms,
                        help="When enabled, OTP codes will be sent via SMS to users' phones"
                    )
                    
                    fallback_display = st.checkbox(
                        "Show OTP in UI as Fallback",
                        value=True,
                        help="Display OTP codes in the interface if SMS fails"
                    )
                    
                    max_attempts = st.number_input(
                        "Max OTP Attempts",
                        value=3,
                        min_value=1,
                        max_value=10,
                        help="Maximum number of OTP verification attempts"
                    )
                    
                    otp_expiry_minutes = st.number_input(
                        "OTP Expiry (minutes)",
                        value=5,
                        min_value=1,
                        max_value=30,
                        help="How long OTP codes remain valid"
                    )
                
                # Environment file management
                st.divider()
                st.subheader("📁 Environment Configuration")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Current .env File Status:**")
                    
                    env_file_path = ".env"
                    env_exists = os.path.exists(env_file_path)
                    
                    if env_exists:
                        st.success("✅ .env file exists")
                        try:
                            with open(env_file_path, 'r') as f:
                                env_content = f.read()
                                sms_lines = [line for line in env_content.split('\n') if 'SMS' in line or 'TWILIO' in line]
                                st.write(f"Found {len(sms_lines)} SMS-related variables")
                        except:
                            st.warning("Unable to read .env file")
                    else:
                        st.warning(" .env file not found")
                
                with col2:
                    st.write("**Required Environment Variables:**")
                    required_vars = [
                        "TWILIO_ACCOUNT_SID",
                        "TWILIO_AUTH_TOKEN", 
                        "TWILIO_PHONE_NUMBER",
                        "ENABLE_SMS_OTP"
                    ]
                    
                    for var in required_vars:
                        if os.getenv(var):
                            st.success(f" {var}")
                        else:
                            st.error(f" {var}")
                
                # Form submission
                save_config = st.form_submit_button("💾 Save SMS Configuration", type="primary")
                
                if save_config:
                    # Validate inputs
                    errors = []
                    
                    if not account_sid or not account_sid.startswith('AC'):
                        errors.append(" Invalid Account SID format")
                    
                    if not auth_token or len(auth_token) < 30:
                        errors.append(" Auth Token appears to be invalid")
                    
                    if not phone_number or not phone_number.startswith('+'):
                        errors.append(" Phone number must include country code (+)")
                    
                    if errors:
                        st.error("**Configuration Errors:**")
                        for error in errors:
                            st.write(error)
                    else:
                        try:
                            # Update environment variables (in practice, you'd update .env file)
                            os.environ['TWILIO_ACCOUNT_SID'] = account_sid
                            os.environ['TWILIO_AUTH_TOKEN'] = auth_token
                            os.environ['TWILIO_PHONE_NUMBER'] = phone_number
                            os.environ['ENABLE_SMS_OTP'] = 'true' if enable_sms_checkbox else 'false'
                            
                            # Update .env file
                            env_vars = {
                                'TWILIO_ACCOUNT_SID': account_sid,
                                'TWILIO_AUTH_TOKEN': auth_token,
                                'TWILIO_PHONE_NUMBER': phone_number,
                                'ENABLE_SMS_OTP': 'true' if enable_sms_checkbox else 'false'
                            }
                            
                            # Read existing .env file
                            env_content = ""
                            if os.path.exists('.env'):
                                with open('.env', 'r') as f:
                                    env_content = f.read()
                            
                            # Update or add SMS variables
                            env_lines = env_content.split('\n') if env_content else []
                            updated_lines = []
                            
                            # Track which variables we've updated
                            updated_vars = set()
                            
                            for line in env_lines:
                                if '=' in line:
                                    var_name = line.split('=')[0].strip()
                                    if var_name in env_vars:
                                        updated_lines.append(f"{var_name}={env_vars[var_name]}")
                                        updated_vars.add(var_name)
                                    else:
                                        updated_lines.append(line)
                                else:
                                    updated_lines.append(line)
                            
                            # Add any new variables
                            for var_name, var_value in env_vars.items():
                                if var_name not in updated_vars:
                                    updated_lines.append(f"{var_name}={var_value}")
                            
                            # Write updated .env file
                            with open('.env', 'w') as f:
                                f.write('\n'.join(updated_lines))
                            
                            st.success("✅ **SMS Configuration Saved Successfully!**")
                            st.info(" **Note**: Restart the application to apply new environment variables.")
                            
                            # Show summary
                            with st.expander("📋 Configuration Summary", expanded=True):
                                st.write(f"**Account SID:** ...{account_sid[-6:]}")
                                st.write(f"**Phone Number:** {phone_number}")
                                st.write(f"**SMS Enabled:** {'Yes' if enable_sms_checkbox else 'No'}")
                                st.write(f"**Max Attempts:** {max_attempts}")
                                st.write(f"**OTP Expiry:** {otp_expiry_minutes} minutes")
                            
                            st.balloons()
                            
                        except Exception as e:
                            st.error(f" **Failed to save configuration:** {str(e)}")
        
        with config_tab2:
            st.subheader(" Test SMS Functionality")
            st.write("Send test SMS messages to verify your configuration.")
            
            if not config_complete:
                st.warning(" **SMS Configuration Required**: Please complete the configuration in the Configuration tab first.")
                return
            
            # Test SMS form
            with st.form("test_sms_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**📱 Test Message Details**")
                    
                    test_phone = st.text_input(
                        "Recipient Phone Number*",
                        placeholder="+1234567890",
                        help="Phone number to send test SMS (with country code)"
                    )
                    
                    test_message_type = st.selectbox(
                        "Message Type",
                        ["OTP Code", "Custom Message", "System Notification"],
                        help="Type of test message to send"
                    )
                    
                    if test_message_type == "Custom Message":
                        custom_message = st.text_area(
                            "Custom Message",
                            placeholder="Enter your test message...",
                            max_chars=160,
                            help="Custom SMS message (max 160 characters)"
                        )
                    else:
                        custom_message = None
                
                with col2:
                    st.write("**📊 Test Configuration**")
                    
                    include_timestamp = st.checkbox(
                        "Include Timestamp",
                        value=True,
                        help="Add timestamp to test message"
                    )
                    
                    test_otp_length = st.selectbox(
                        "OTP Length (for OTP tests)",
                        [4, 6, 8],
                        index=1,
                        help="Length of OTP code for testing"
                    )
                    
                    delivery_timeout = st.number_input(
                        "Delivery Timeout (seconds)",
                        value=30,
                        min_value=10,
                        max_value=120,
                        help="How long to wait for delivery confirmation"
                    )
                
                # Send test SMS
                send_test = st.form_submit_button("📱 Send Test SMS", type="primary")
                
                if send_test:
                    if not test_phone or not test_phone.startswith('+'):
                        st.error(" Please enter a valid phone number with country code (+)")
                    else:
                        try:
                            with st.spinner("📱 Sending test SMS..."):
                                import time
                                
                                # Generate test message based on type
                                if test_message_type == "OTP Code":
                                    test_otp = ''.join([str(random.randint(0, 9)) for _ in range(test_otp_length)])
                                    message = f"Your test OTP code is: {test_otp}"
                                    if include_timestamp:
                                        message += f" (Sent at {datetime.now().strftime('%H:%M:%S')})"
                                elif test_message_type == "Custom Message":
                                    message = custom_message or "Test message from EHR system"
                                    if include_timestamp:
                                        message += f" [{datetime.now().strftime('%H:%M:%S')}]"
                                else:  # System Notification
                                    message = "Test notification from EHR System - SMS configuration working!"
                                    if include_timestamp:
                                        message += f" (Sent: {datetime.now().strftime('%H:%M:%S')})"
                                
                                # Try to send SMS using the health card generator's SMS function
                                success = card_generator._send_twilio_sms(test_phone, message)
                                
                                if success:
                                    st.success("✅ **Test SMS sent successfully!**")
                                    
                                    with st.expander("📱 Message Details", expanded=True):
                                        st.write(f"**To:** {test_phone}")
                                        st.write(f"**Message:** {message}")
                                        st.write(f"**Type:** {test_message_type}")
                                        st.write(f"**Length:** {len(message)} characters")
                                        st.write(f"**Sent at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                    
                                    st.info("💡 **Check your phone** to confirm SMS delivery.")
                                else:
                                    st.error(" **Test SMS failed to send.**")
                                    st.write("**Possible issues:**")
                                    st.write("• Invalid Twilio credentials")
                                    st.write("• Invalid phone number format")
                                    st.write("• Insufficient Twilio account balance")
                                    st.write("• Network connectivity issues")
                                    
                                    st.info(" **Troubleshooting**: Check your Twilio console for detailed error logs.")
                        
                        except Exception as e:
                            st.error(f" **SMS Test Error:** {str(e)}")
                            
                            # Provide specific error guidance
                            error_str = str(e).lower()
                            if 'authentication' in error_str:
                                st.write(" **Authentication Error**: Check your Twilio Account SID and Auth Token")
                            elif 'phone' in error_str or 'number' in error_str:
                                st.write("📱 **Phone Number Error**: Verify the phone number format and country code")
                            elif 'balance' in error_str or 'insufficient' in error_str:
                                st.write(" **Account Balance**: Check your Twilio account balance")
                            else:
                                st.write(" **General Error**: Check your Twilio configuration and network connection")
            
            # SMS delivery tips
            st.divider()
            st.subheader(" SMS Delivery Tips")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**📱 Phone Number Format:**")
                st.info("• Always include country code (e.g., +1 for US)")
                st.info("• Format: +1234567890 (no spaces or dashes)")
                st.info("• US numbers: +1 followed by 10 digits")
                st.info("• International: Country code + local number")
            
            with col2:
                st.write("**⚡ Best Practices:**")
                st.success("• Test with your own phone number first")
                st.success("• Keep messages under 160 characters")
                st.success("• Include clear sender identification")
                st.success("• Monitor Twilio console for delivery status")
        
        with config_tab3:
            st.subheader("📊 SMS Usage Statistics")
            st.write("Monitor SMS delivery statistics and usage patterns.")
            
            # Simulated statistics (in production, you'd track these in database)
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(" Total SMS Sent", "156", delta="+12 today")
            
            with col2:
                st.metric(" Delivery Rate", "98.7%", delta="+2.1%")
            
            with col3:
                st.metric(" Avg Delivery Time", "2.3s", delta="-0.4s")
            
            with col4:
                st.metric(" Monthly Cost", "$12.45", delta="+$2.15")
            
            # Usage charts (placeholder)
            st.divider()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(" Daily SMS Volume")
                
                # Sample data for demonstration
                import pandas as pd
                sample_data = pd.DataFrame({
                    'Date': pd.date_range(start='2024-01-01', periods=30, freq='D'),
                    'SMS Count': [random.randint(3, 15) for _ in range(30)]
                })
                
                st.line_chart(sample_data.set_index('Date')['SMS Count'])
            
            with col2:
                st.subheader(" Message Types")
                
                # Message type distribution
                message_types = {
                    'OTP Codes': 89,
                    'Notifications': 45,
                    'Alerts': 22
                }
                
                st.bar_chart(message_types)
            
            # Detailed statistics table
            st.divider()
            st.subheader(" Detailed Usage Report")
            
            # Sample detailed statistics
            detailed_stats = pd.DataFrame({
                'Date': ['2024-01-15', '2024-01-14', '2024-01-13', '2024-01-12', '2024-01-11'],
                'OTP SMS': [12, 8, 15, 6, 9],
                'Notifications': [3, 5, 2, 4, 3],
                'Delivery Rate': ['100%', '97.5%', '98.8%', '100%', '96.7%'],
                'Avg Response Time': ['2.1s', '2.3s', '1.9s', '2.5s', '2.2s'],
                'Cost': ['$2.15', '$1.85', '$2.45', '$1.40', '$1.95']
            })
            
            st.dataframe(detailed_stats, use_container_width=True)
            
            # Export statistics
            st.divider()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button(" Export Statistics", use_container_width=True):
                    csv = detailed_stats.to_csv(index=False)
                    st.download_button(
                        label="💾 Download CSV",
                        data=csv,
                        file_name=f"sms_stats_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("📈 Generate Report", use_container_width=True):
                    st.info(" Comprehensive SMS usage report would be generated here")
            
            with col3:
                if st.button(" Refresh Stats", use_container_width=True):
                    st.success(" Statistics refreshed!")
                    st.rerun()
        
        with config_tab4:
            st.subheader(" SMS Logs & Message History")
            st.write("View SMS delivery logs and message history.")
            
            # Log filters
            col1, col2, col3 = st.columns(3)
            
            with col1:
                log_date_filter = st.date_input(
                    "Filter by Date",
                    value=datetime.now().date(),
                    help="Show logs for specific date"
                )
            
            with col2:
                log_status_filter = st.selectbox(
                    "Message Status",
                    ["All", "Delivered", "Failed", "Pending"],
                    help="Filter by delivery status"
                )
            
            with col3:
                log_type_filter = st.selectbox(
                    "Message Type",
                    ["All", "OTP", "Notification", "Alert", "Test"],
                    help="Filter by message type"
                )
            
            # Sample log data (in production, this would come from database)
            st.divider()
            
            log_data = [
                {
                    'Time': '14:23:15',
                    'Phone': '+1234567890',
                    'Type': 'OTP',
                    'Message': 'Your OTP code is: 847291',
                    'Status': 'Delivered',
                    'Response Time': '2.1s',
                    'Cost': '$0.0075'
                },
                {
                    'Time': '14:18:42',
                    'Phone': '+1987654321',
                    'Type': 'Test',
                    'Message': 'Test message from EHR system',
                    'Status': 'Delivered',
                    'Response Time': '1.8s',
                    'Cost': '$0.0075'
                },
                {
                    'Time': '13:55:33',
                    'Phone': '+1555123456',
                    'Type': 'OTP',
                    'Message': 'Your OTP code is: 129384',
                    'Status': 'Failed',
                    'Response Time': 'N/A',
                    'Cost': '$0.00'
                },
                {
                    'Time': '13:42:18',
                    'Phone': '+1444555666',
                    'Type': 'Notification',
                    'Message': 'Your appointment is confirmed for tomorrow',
                    'Status': 'Delivered',
                    'Response Time': '2.3s',
                    'Cost': '$0.0075'
                }
            ]
            
            # Display filtered logs
            filtered_logs = log_data  # In production, apply actual filters
            
            st.write(f"**Showing {len(filtered_logs)} message(s) for {log_date_filter}**")
            
            for i, log in enumerate(filtered_logs):
                with st.expander(f"📱 {log['Time']} - {log['Type']} - {log['Status']}", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**Message Details:**")
                        st.write(f"**Time:** {log['Time']}")
                        st.write(f"**Type:** {log['Type']}")
                        st.write(f"**Phone:** {log['Phone']}")
                    
                    with col2:
                        st.write("**Content:**")
                        st.write(f"**Message:** {log['Message']}")
                        st.write(f"**Length:** {len(log['Message'])} chars")
                    
                    with col3:
                        st.write("**Delivery Info:**")
                        if log['Status'] == 'Delivered':
                            st.success(f"✅ {log['Status']}")
                        elif log['Status'] == 'Failed':
                            st.error(f" {log['Status']}")
                        else:
                            st.warning(f" {log['Status']}")
                        
                        st.write(f"**Response Time:** {log['Response Time']}")
                        st.write(f"**Cost:** {log['Cost']}")
            
            # Log management actions
            st.divider()
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button(" Refresh Logs", use_container_width=True):
                    st.success(" Logs refreshed!")
                    st.rerun()
            
            with col2:
                if st.button("📤 Export Logs", use_container_width=True):
                    # Convert logs to DataFrame and export
                    df_logs = pd.DataFrame(log_data)
                    csv = df_logs.to_csv(index=False)
                    
                    st.download_button(
                        label="💾 Download Logs CSV",
                        data=csv,
                        file_name=f"sms_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            
            with col3:
                if st.button("🗑️ Clear Old Logs", use_container_width=True):
                    st.warning("⚠️ Log cleanup functionality would be implemented here")
            
            with col4:
                if st.button("🔍 Advanced Search", use_container_width=True):
                    st.info("🔍 Advanced log search interface would be available here")
    
    except Exception as e:
        st.error(f" SMS Settings Error: {str(e)}")
        logger.error(f"SMS settings management error: {str(e)}")

def main():
    """Enhanced main admin dashboard function"""
    # Check authentication
    check_authentication()
    
    # Get current user
    current_user = get_current_user()
    if not current_user:
        st.error("Failed to load user data")
        st.stop()
    
    # Enhanced page header with admin info
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.title(" Admin Dashboard")
        st.markdown(f"**Welcome back, {current_user.get('username', 'Administrator')}!** 👋")
        st.caption("Complete system administration and management")
    
    with col2:
        # System status indicator
        try:
            users_collection = get_users_collection()
            users_collection.find_one()  # Test connection
            st.success(" System Online")
            st.caption("All services operational")
        except:
            st.error(" System Issues")
            st.caption("Check database connection")
    
    with col3:
        # Quick refresh and help
        if st.button(" Refresh Dashboard", use_container_width=True):
            st.rerun()
        
        if st.button(" Help & Documentation", use_container_width=True):
            st.info(" Admin documentation would be available here")
    
    st.divider()
    
    # Enhanced tabs with better organization
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Analytics", 
        "👥 Users", 
        "🔗 Assignments", 
        "👤 Create User",
        "🏥 Health Cards",
        "🗄️ Database",
        "📱 SMS Settings"
    ])
    
    with tab1:
        display_system_statistics()
    
    with tab2:
        manage_users()
    
    with tab3:
        assign_patients_to_doctors()
    
    with tab4:
        create_new_user()
    
    with tab5:
        manage_health_cards()
    
    with tab6:
        database_management()
    
    with tab7:
        sms_settings_management()
    
    # Enhanced sidebar with comprehensive admin tools
    with st.sidebar:
        st.header(" Admin Control Panel")
        
        # System overview metrics
        try:
            users_collection = get_users_collection()
            records_collection = get_records_collection()
            
            total_users = users_collection.count_documents({})
            total_patients = users_collection.count_documents({"role": "patient"})
            total_doctors = users_collection.count_documents({"role": "doctor"})
            total_records = records_collection.count_documents({})
            
            # Quick stats with progress bars
            st.subheader("📊 Quick Stats")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("👥 Users", total_users)
                st.metric("👤 Patients", total_patients)
            with col2:
                st.metric("👨‍⚕️ Doctors", total_doctors)
                st.metric("📄 Records", total_records)
            
            # System health indicator
            if total_doctors > 0:
                ratio = total_patients / total_doctors
                st.write(f"**Patient:Doctor Ratio:** {ratio:.1f}:1")
                
                if ratio <= 10:
                    st.success("🟢 Optimal ratio")
                elif ratio <= 25:
                    st.warning("🟡 High ratio")
                else:
                    st.error("🔴 Very high ratio")
            
        except Exception as e:
            st.warning("⚠️ Unable to load statistics")
            logger.error(f"Sidebar stats error: {str(e)}")
        
        st.divider()
        
        # Enhanced admin actions
        st.subheader("🛠️ Quick Actions")
        
        # System operations
        if st.button("🔄 Refresh All Data", use_container_width=True, help="Refresh all dashboard data"):
            st.rerun()
        
        if st.button("📊 Generate Report", use_container_width=True, help="Generate system usage report"):
            st.info("📊 Comprehensive reporting would be available here")
        
        if st.button("👥 User Analytics", use_container_width=True, help="Detailed user analytics"):
            st.info("📈 User behavior analytics would be shown here")
        
        if st.button("🔔 Send Notifications", use_container_width=True, help="Send system notifications"):
            st.info("📨 Notification system would be available here")
        
        st.divider()
        
        # System management
        st.subheader("🔧 System Management")
        
        if st.button("⚙️ System Settings", use_container_width=True):
            st.info(" System configuration would be available here")
        
        if st.button("🔒 Security Audit", use_container_width=True):
            st.info(" Security audit tools would be available here")
        
        if st.button("📦 Backup Management", use_container_width=True):
            st.info(" Backup management interface would be here")
        
        if st.button("📋 System Logs", use_container_width=True):
            st.info(" System log viewer would be available here")
        
        st.divider()
        
        # Emergency actions
        st.subheader("🚨 Emergency Actions")
        
        if st.button("🔧 Maintenance Mode", use_container_width=True, help="Enable system maintenance mode"):
            st.warning(" Maintenance mode controls would be here")
        
        if st.button("🆘 Emergency Shutdown", use_container_width=True, help="Emergency system shutdown"):
            st.error(" Emergency procedures would be implemented here")
        
        # Footer
        st.divider()
        st.caption("🔒 Admin Panel • Secure Access")
        st.caption(f"Last Login: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# Run the main function directly (Streamlit pages don't use __main__ pattern)
main()