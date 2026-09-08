"""
EHR Web App - Main Application
Streamlit-based Electronic Health Records system with MongoDB and LLM integration
"""

import streamlit as st
import sys
import os
from utils.auth import authenticate_user, check_user_role, logout_user
from utils.database import init_db
from config.settings import APP_CONFIG

# Set page config
st.set_page_config(
    page_title="EHR Web App",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize database connection
@st.cache_resource
def initialize_database():
    """Initialize database connection"""
    return init_db()

# Initialize session state
def init_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_role' not in st.session_state:
        st.session_state.user_role = None
    if 'username' not in st.session_state:
        st.session_state.username = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

def show_login_page():
    """Display login page with improved UI"""
    # Hide sidebar on login page
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            [data-testid="collapsedControl"] {display: none;}
            .main {
                padding-top: 2rem;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 2rem;
                justify-content: center;
            }
            .stTabs [data-baseweb="tab"] {
                height: 50px;
                padding-left: 2rem;
                padding-right: 2rem;
                font-size: 1.1rem;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Center aligned header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏥 EHR Web App</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; color: #666;'>Electronic Health Records Management System</h3>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
    
    # Create tabs for login and signup
    login_tab, signup_tab = st.tabs(["Login", "Sign Up"])
    
    with login_tab:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Login to Your Account")
            st.markdown("<br>", unsafe_allow_html=True)
            
            with st.form("login_form"):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit_button = st.form_submit_button("Login", use_container_width=True, type="primary")
                
                if submit_button:
                    if username and password:
                        user_data = authenticate_user(username, password)
                        if user_data:
                            st.session_state.authenticated = True
                            st.session_state.user_role = user_data['role']
                            st.session_state.username = user_data['username']
                            st.session_state.user_id = str(user_data['id'])
                            st.session_state.user_data = user_data
                            st.success(f"Welcome, {username}!")
                            st.rerun()
                        else:
                            st.error("Invalid username or password")
                    else:
                        st.error("Please enter both username and password")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.info("Demo: Use 'patient1' or 'doctor1' with password 'password123'")
            
    with signup_tab:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### Create New Account")
            st.markdown("<br>", unsafe_allow_html=True)
            
            with st.form("signup_form"):
                new_username = st.text_input("Choose Username", placeholder="Enter username")
                new_email = st.text_input("Email Address", placeholder="Enter email address")
                new_password = st.text_input("Choose Password", type="password", placeholder="Create password")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Re-enter password")
                role = st.selectbox("Select Role", ["patient", "doctor"])
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit_signup = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                
                if submit_signup:
                    from utils.auth import create_user
                    if new_password == confirm_password:
                        if create_user(new_username, new_email, new_password, role):
                            st.success("Account created successfully! Please login.")
                        else:
                            st.error("Username already exists")
                    else:
                        st.error("Passwords do not match")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.info("Choose 'patient' to manage medical records or 'doctor' to access patient information.")

def show_navigation():
    """Display navigation sidebar"""
    with st.sidebar:
        st.title(f"Welcome, {st.session_state.username}")
        st.write(f"Role: {st.session_state.user_role.title()}")
        
        # Navigation based on role
        if st.session_state.user_role == 'patient':
            st.page_link("pages/01_Patient_Dashboard.py", label="Patient Dashboard")
        elif st.session_state.user_role == 'doctor':
            st.page_link("pages/02_Doctor_Dashboard.py", label="Doctor Dashboard")
        elif st.session_state.user_role == 'admin':
            st.page_link("pages/03_Admin_Dashboard.py", label="Admin Dashboard")
        
        st.divider()
        
        if st.button("Logout"):
            logout_user()
            st.rerun()

def main():
    """Main application logic"""
    # Initialize database and session state
    db = initialize_database()
    init_session_state()
    
    # Check authentication
    if not st.session_state.authenticated:
        show_login_page()
    else:
        # Show sidebar for authenticated users
        st.markdown("""
            <style>
                [data-testid="stSidebar"] {display: block !important;}
                [data-testid="collapsedControl"] {display: block !important;}
            </style>
        """, unsafe_allow_html=True)
        
        # Show navigation
        show_navigation()
        
        # Main content area
        st.title("🏥 EHR Web App Dashboard")
        
        # Role-specific welcome message
        if st.session_state.user_role == 'patient':
            st.info("Upload and manage your medical records. Navigate to Patient Dashboard to get started.")
            st.markdown("""
            ### Available Features:
            - Upload medical documents with automatic OCR processing
            - Get AI-powered summaries
            - View your medical history
            - Share access with doctors
            - Extract text from handwritten documents
            """)
            
        elif st.session_state.user_role == 'doctor':
            st.info("Access patient records and add medical notes. Navigate to Doctor Dashboard to get started.")
            st.markdown("""
            ### Available Features:
            - View assigned patients
            - Access patient medical history
            - Add doctor's notes
            - Search and filter patients
            - Process handwritten prescriptions with OCR
            """)
            
        elif st.session_state.user_role == 'admin':
            st.info("Manage users and system settings. Navigate to Admin Dashboard to get started.")
            st.markdown("""
            ### Available Features:
            - Manage all users
            - Assign patients to doctors
            - View usage statistics
            - System administration
            - Convert documents to digital records with OCR
            """)

if __name__ == "__main__":
    main()