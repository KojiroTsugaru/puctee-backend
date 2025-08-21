# Puctee Backend API

A FastAPI-powered backend service for lateness prevention iOS application. This project demonstrates modern backend development practices, complex database relationships, real-time notifications, and location-based services.

> 📱 **Frontend Repository**: The iOS app for this backend is on [puctee](https://github.com/KojiroTsugaru/puctee).

## 🚀 Project Overview

Puctee Backend is a comprehensive social planning API that helps friends coordinate meetups with built-in accountability features. Users can create plans, invite friends, set penalties for tardiness, and track attendance through location-based check-ins. The platform promotes punctuality and reliability through gamified trust scoring and social accountability.

## 🛠️ Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with SQLAlchemy (Async ORM)
- **Authentication**: JWT tokens with bcrypt password hashing
- **Notifications**: Apple Push Notification service (APNs)
- **Server**: Uvicorn (ASGI)
- **Testing**: pytest with FastAPI TestClient
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## 🏗️ Architecture

The Puctee backend follows a modern serverless architecture using AWS services and FastAPI.

```mermaid
flowchart LR
    user["iOS App (SwiftUI)"]
    
    subgraph AWS ["AWS"]
        APIG["API Gateway (HTTP API)"]
        
        subgraph VPC ["VPC"]
            L["Lambda (FastAPI)"]
            RDS["PostgreSQL"]
        end
        
        S3["S3 Bucket (object storage)"]
        SM["Secrets Manager (credentials)"]
        CW["CloudWatch Logs & Metrics"]
    end

    APNs["Apple Push Notification Service (APNs)"]

    %% Request flow
    user -- "HTTPS / JSON" --> APIG
    APIG -- "Invoke" --> L
    L -- "SQL (TCP)" --> RDS
    L -- "Fetch DB creds" --> SM
    L -- "Object Operations" --> S3
    user -- "Upload/Download" --> S3

    %% Notification flow
    L -- "Send Push Notification" --> APNs
    APNs -- "Push Message" --> user

    %% Monitoring
    APIG -. "Logs / Metrics" .-> CW
    L -. "Logs / Metrics" .-> CW
```

## ✨ Features

- **User Authentication**: JWT-based secure authentication and user management
- **Friend System**: Send/accept friend requests with bidirectional relationship management
- **Plan Management**: Create events, invite participants, track attendance status
- **Location Services**: GPS-based check-ins for plan verification
- **Accountability System**: Penalty management with proof submission for tardiness
- **Trust Scoring**: Gamified reliability tracking based on punctuality history
- **Real-time Notifications**: Push notifications with APNs for invitations, updates, and reminders
- **Complex Relationships**: Advanced SQLAlchemy patterns with eager loading optimization

## 📚 API Documentation

### Key Endpoints
- **Authentication**: `/auth/login`, `/auth/signup`, `/auth/refresh`
- **Users**: `/users/me`, `/users/me/trust-stats`
- **Friends**: `/friends/invite`, `/friends/accept/{invite_id}`, `/friends/{friend_id}`
- **Plans**: `/plans/`, `/plans/list`, `/plans/{plan_id}/checkin`

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 13+
- An AWS account with credentials configured (for S3 and other services)

### 1. Clone the Repository

```bash
git clone https://github.com/KojiroTsugaru/puctee-backend.git
cd puctee-backend
```

### 2. Create a Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the root directory and add the following variables. Replace the placeholder values with your actual credentials.

```env
# PostgreSQL Database
DATABASE_URL="postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE"

# JWT Authentication
SECRET_KEY="your_super_secret_key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AWS Credentials (if not using IAM roles)
AWS_ACCESS_KEY_ID="your_aws_access_key"
AWS_SECRET_ACCESS_KEY="your_aws_secret_key"
AWS_REGION="your_aws_region"
S3_BUCKET_NAME="your_s3_bucket_name"

# APNs Configuration
APNS_CERT_PATH="/path/to/your/apns/cert.pem"
```

### 5. Run Database Migrations

Apply the initial database schema using Alembic.

```bash
alembic upgrade head
```

### 6. Run the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

### 7. Running Tests

To run the test suite, use pytest.

```bash
pytest
```

## 📝 License

This project is part of a portfolio showcase. Feel free to use as reference for your own projects.

## 🤝 Contributing

This is a portfolio project demonstrating advanced FastAPI development patterns, complex database relationships, and real-time notification systems.

---

**Built with ❤️ using FastAPI, SQLAlchemy, and modern Python development practices**