# Prelude CRM Service

AI-powered Customer Relationship Management service with intelligent insights and automated features.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Environment
Set up the required environment variables:
```
SESSIONS_DB_HOST=localhost
SESSIONS_DB_PORT=5432
SESSIONS_DB_NAME=postgres
SESSIONS_DB_USER=postgres
SESSIONS_DB_PASSWORD=your_password
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
```

### 3. Run the Service
```bash
python run.py
```

### 4. Test the API
- **API Documentation**: http://localhost:8003/docs
- **Health Check**: http://localhost:8003/health

## 📋 Features

### Core Features
- ✅ **Customer Management** - Create, read, update, delete customers
- ✅ **AI-Powered Email Generation** - Generate personalized emails using Gemini AI
- ✅ **Analytics Insights** - AI-driven business analytics and reporting
- ✅ **Todo Generation** - Automatic task generation based on customer data
- ✅ **Interaction Summaries** - AI-powered interaction tracking and summaries
- ✅ **Database Operations** - Comprehensive customer data management

### API Endpoints

#### Customer Management (`/api/crm`)
- `GET /customers` - List customers
- `GET /customers/{id}` - Get customer details
- `POST /customers` - Create customer
- `PUT /customers/{id}` - Update customer

#### AI Features
- `POST /generate-email/{customer_id}` - Generate personalized email
- `POST /generate-analytics-insights` - Generate business insights
- `POST /generate-todos` - Generate tasks and todos
- `POST /interaction-summaries` - Generate interaction summaries

## 🔧 Configuration

The service runs on port 8003 by default. Frontend should connect to:
```
http://localhost:8003/api/crm/*
```

## 🏗️ Architecture

This service follows the microservice pattern:
- **Independent Service** - Runs separately from main backend
- **Direct Frontend Connection** - Frontend connects directly to CRM service
- **Database Integration** - Uses PostgreSQL for customer data
- **AI Integration** - Gemini and OpenAI for intelligent features 