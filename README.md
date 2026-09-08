# 🏥 EHR Web App

A comprehensive Electronic Health Records (EHR) Web Application built with Streamlit, MongoDB, and Hugging Face LLM integration.

## 🚀 Features

### User Roles
- **Patients**: Upload medical records, get AI summaries, view history
- **Doctors**: Access patient records, add notes, manage assigned patients  
- **Admins**: User management, patient assignments, system statistics

### Core Functionality
- 🔐 Secure authentication with role-based access
- 📄 Medical record upload and management
- 🤖 AI-powered text summarization using Hugging Face models
- 👨‍⚕️ Doctor notes and patient assignment system
- 📊 Analytics and usage statistics
- 🔍 Search and filter capabilities

## 🛠️ Tech Stack

- **Frontend**: Streamlit (Python-based UI)
- **Backend**: MongoDB (document database)
- **AI/ML**: Hugging Face Transformers (BART model for summarization)
- **Authentication**: MongoDB-based with bcrypt password hashing
- **Deployment**: Streamlit Cloud / Hugging Face Spaces

## 📋 Prerequisites

- Python 3.8 or higher
- MongoDB Atlas account (or local MongoDB installation)
- Hugging Face account (optional, for API token)

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd ehr-web-app
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. MongoDB Atlas Setup

#### Create MongoDB Atlas Account:
1. Go to [MongoDB Atlas](https://www.mongodb.com/atlas)
2. Create a free account
3. Create a new cluster (use free M0 tier)

#### Get Connection String:
1. In Atlas dashboard, click "Connect" 
2. Choose "Connect your application"
3. Copy the connection string
4. Replace `<username>`, `<password>`, and `<cluster-url>` with your actual values

Example connection string:
```
mongodb+srv://myuser:mypassword@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

#### Configure Database Access:
1. In Atlas, go to "Database Access"
2. Add a database user with read/write permissions
3. In "Network Access", add your IP address (or 0.0.0.0/0 for development)

### 4. Environment Configuration

Create a `.env` file in the project root:
```bash
cp .env.example .env
```

Update `.env` with your actual values:
```env
MONGODB_CONNECTION_STRING=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=ehr_app
HUGGINGFACE_API_TOKEN=your_token_here
SECRET_KEY=your-super-secret-key
```

### 5. Run the Application
```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## 📁 Project Structure

```
ehr-web-app/
├── app.py                 # Main Streamlit application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .streamlit/
│   └── config.toml       # Streamlit configuration
├── config/
│   └── settings.py       # Application settings
├── utils/
│   ├── auth.py          # Authentication utilities
│   ├── database.py      # MongoDB connection and operations
│   ├── llm.py           # Hugging Face LLM integration
│   └── records.py       # Medical records management
└── pages/
    ├── 01_Patient_Dashboard.py    # Patient interface
    ├── 02_Doctor_Dashboard.py     # Doctor interface
    └── 03_Admin_Dashboard.py      # Admin interface
```

## 🗄️ Database Schema

### Users Collection
```json
{
  "_id": "ObjectId",
  "username": "string",
  "email": "string", 
  "password": "hashed_string",
  "role": "patient|doctor|admin",
  "created_at": "datetime",
  "assigned_patients": ["patient_ids"] // for doctors only
}
```

### Records Collection
```json
{
  "_id": "ObjectId",
  "patient_id": "user_id",
  "uploaded_at": "datetime",
  "original_text": "medical record text",
  "summary": "AI generated summary",
  "insights": "extracted medical insights",
  "doctor_notes": "doctor's notes",
  "file_name": "uploaded file name",
  "file_type": "file type"
}
```

## 🤖 AI Integration

The app uses Hugging Face's BART model for text summarization:
- **Model**: `facebook/bart-large-cnn`
- **Features**: Medical text preprocessing, chunking for long texts
- **Outputs**: Summaries, key medical insights, statistics

## 🚀 Deployment Options

### Option 1: Streamlit Cloud
1. Push code to GitHub
2. Connect repository to [Streamlit Cloud](https://streamlit.io/cloud)
3. Add environment variables in Streamlit Cloud settings
4. Deploy

### Option 2: Hugging Face Spaces
1. Create account on [Hugging Face](https://huggingface.co)
2. Create new Space with Streamlit SDK
3. Upload files and configure secrets
4. Deploy

### Option 3: Local/Server Deployment
```bash
# Install and run
pip install -r requirements.txt
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

## 👥 Usage

### For Patients:
1. Sign up with "patient" role
2. Login and navigate to Patient Dashboard
3. Upload medical records (PDF, text, images)
4. View AI-generated summaries and insights
5. Manage your medical history

### For Doctors:
1. Login with doctor credentials
2. Access assigned patients
3. Review patient medical histories
4. Add professional notes and observations
5. Search and filter patient records

### For Admins:
1. Login with admin credentials  
2. Manage user accounts
3. Assign patients to doctors
4. View system usage statistics
5. Perform administrative tasks

## 🔒 Security Features

- Password hashing with bcrypt
- Role-based access control
- Session management
- Input validation and sanitization
- Secure database connections

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Troubleshooting

### Common Issues:

**MongoDB Connection Issues:**
- Verify connection string format
- Check network access settings in Atlas
- Ensure database user has proper permissions

**Model Loading Issues:**
- Check internet connection for model download
- Verify Hugging Face token (if using private models)
- Ensure sufficient disk space for model cache

**Streamlit Issues:**
- Update Streamlit: `pip install --upgrade streamlit`
- Clear cache: Delete `.streamlit` folder and restart
- Check port availability

## 📞 Support

For support and questions:
- Create an issue in the GitHub repository
- Check the troubleshooting section
- Review Streamlit and MongoDB documentation

---

Built with ❤️ using Streamlit, MongoDB, and Hugging Face