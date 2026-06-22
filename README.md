# 👗 Virtual Clothes Try-On System

A web-based virtual try-on application that allows users to visualize clothing items on a human image. The system provides an interactive and user-friendly experience for exploring outfit combinations digitally.

---

## 📌 Project Overview

The Virtual Clothes Try-On System enables users to upload an image and visually test how different clothes appear on their body. The project includes a full authentication system, image upload pipeline, and an interactive frontend that simulates a virtual fitting room.

---

## 🚀 Features

- User registration and login with JWT authentication
- Secure password hashing with bcrypt
- Upload and save user images (front, back, left, right views)
- Select and preview clothing items
- Real-time visual overlay experience
- Clean and responsive user interface
- Organized and reusable frontend components

---

## 🛠️ Technologies Used

**Frontend**
- HTML5
- CSS3
- JavaScript
- Tailwind CSS

**Backend**
- Python
- FastAPI
- SQLAlchemy
- SQLite
- JWT (python-jose)
- bcrypt / passlib

**AI / ML**
- PyTorch
- OpenCV
- Deep Learning models

---

## 📁 Project Structure

```
DEPI_GP/
├── Backend/
│   ├── main.py               # FastAPI server — all endpoints
│   ├── vwear.db              # SQLite database (auto-created)
│   ├── uploads/              # Saved user images (auto-created)
│   ├── login.html
│   └── vwear_signup.html
│
├── Database/
│   └── schema.sql            # SQLite-compatible schema reference
│
├── Front-end/
│   ├── VWearHomeP.html       # Home page
│   ├── TryOnPageDemo.html    # Virtual try-on page
│   ├── about.html
│   ├── vwear.html
│   ├── vwear_signup.html
│   ├── script.js
│   ├── about.js
│   └── tailwind_confg*.js
│
└── README.md
```

---

## ⚙️ Setup & Run

**1. Install dependencies**
```bash
pip install fastapi uvicorn sqlalchemy passlib python-jose python-multipart bcrypt email-validator
```

**2. Run the server**
```bash
cd Backend
python main.py
```

**3. Server runs at**
```
http://127.0.0.1:8000
```

**4. Interactive API docs (Swagger UI)**
```
http://127.0.0.1:8000/docs
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/` | Health check | ❌ |
| POST | `/signup` | Register new user | ❌ |
| POST | `/login` | Login and get JWT token | ❌ |
| GET | `/profile` | Get current user data | ✅ |
| POST | `/upload-image` | Upload front/back/left/right images | ✅ |
| GET | `/my-images` | Get saved images for current user | ✅ |

---

## 🗄️ Database Schema

**Users**
| Column | Type | Notes |
|--------|------|-------|
| Id | INTEGER | Primary key, auto increment |
| Username | TEXT | Unique |
| Email | TEXT | Unique |
| PasswordHash | TEXT | bcrypt hashed |
| CreatedAt | DATETIME | Auto set on insert |

**UserImages**
| Column | Type | Notes |
|--------|------|-------|
| Id | INTEGER | Primary key, auto increment |
| UserId | INTEGER | FK → Users.Id, unique per user |
| FrontImage | TEXT | File path on server |
| BackImage | TEXT | File path on server |
| LeftImage | TEXT | File path on server |
| RightImage | TEXT | File path on server |
| CreatedAt | DATETIME | Auto set on insert |

---

## 🧪 Model Approach

The system follows these steps:

- Image preprocessing
- Body / pose detection
- Clothes alignment
- Image synthesis (overlay or generation)

## Testing Branches
Testing Git Branches by Abdelrhman