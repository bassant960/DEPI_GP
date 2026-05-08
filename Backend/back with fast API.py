from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, select
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from pydantic import BaseModel, EmailStr, Field
import datetime
import logging
import uvicorn

# 1. Database Configuration
DATABASE_FILE = "vwear.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///./{DATABASE_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# 2. Define Table Structure (لضمان مطابقة الـ SQL مع البريد الإلكتروني)
users_table = Table(
    'Users', metadata,
    Column('Id', Integer, primary_key=True),
    Column('Username', String(50), unique=True, nullable=False),
    Column('Email', String(100), unique=True, nullable=False), # إضافة حقل الميل
    Column('PasswordHash', String(255), nullable=False),
    Column('CreatedAt', DateTime, default=datetime.datetime.utcnow)
)

# إنشاء الجدول في vwear.db إذا لم يكن موجوداً
metadata.create_all(bind=engine)

# 3. Security Configuration
SECRET_KEY = "vwear_super_secret_key_2026_backend_project"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

app = FastAPI(title="VWear Backend API")

# 4. CORS (للسماح بالاتصال من الـ Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Schemas
class UserSignup(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# 6. Helper Functions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str):

    password = password.encode("utf-8")[:72].decode("utf-8", "ignore")

    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):

    plain_password = plain_password.encode("utf-8")[:72].decode("utf-8", "ignore")

    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# 7. API Endpoints

@app.post("/signup")
async def signup(user: UserSignup, db: Session = Depends(get_db)):

    # التأكد من عدم تكرار الإيميل أو اسم المستخدم
    query = select(users_table).where(
        (users_table.c.Email == user.email) |
        (users_table.c.Username == user.username)
    )

    existing_user = db.execute(query).fetchone()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Username or Email already registered"
        )

    try:

        hashed_pw = hash_password(user.password)

        insert_stmt = users_table.insert().values(
            Username=user.username,
            Email=user.email,
            PasswordHash=hashed_pw
        )

        db.execute(insert_stmt)

        db.commit()

        token = create_access_token(user.email)

        return {
            "message": "User created successfully",
            "token": token,
            "username": user.username
        }

    except Exception as e:

        db.rollback()

        print("SIGNUP ERROR =>", e)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    # البحث باستخدام الإيميل
    query = select(users_table).where(users_table.c.Email == user.email)
    db_user = db.execute(query).fetchone()

    if not db_user or not verify_password(user.password, db_user.PasswordHash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(db_user.Email)
    return {"message": "Login successful", "token": token, "username": db_user.Username}

@app.get("/profile")
def profile(user_data = Depends(verify_token)):
    return {"message": "Authorized", "user": user_data}

@app.get("/")
def home():
    return {"message": "VWear Backend Running Successfully"}

# 8. Run Server
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
