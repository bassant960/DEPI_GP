from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, select
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import datetime
import shutil
import os
import uuid
import uvicorn

# ============================================================
# 1. Database Configuration — SQLite (مش SQL Server)
# ============================================================
DATABASE_FILE = "vwear.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///./{DATABASE_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()

# ============================================================
# 2. Tables — مكتوبة بـ SQLAlchemy مش SQL Server syntax
# ============================================================
users_table = Table(
    'Users', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('Username', String(50), unique=True, nullable=False),
    Column('Email', String(100), unique=True, nullable=False),
    Column('PasswordHash', String(255), nullable=False),
    Column('CreatedAt', DateTime, default=datetime.datetime.utcnow)
)

# جدول الصور — كل يوزر ليه صف واحد بس (UNIQUE على UserId)
user_images_table = Table(
    'UserImages', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('UserId', Integer, nullable=False),        # FK للـ Users
    Column('FrontImage', String(500), nullable=True),
    Column('BackImage', String(500), nullable=True),
    Column('LeftImage', String(500), nullable=True),
    Column('RightImage', String(500), nullable=True),
    Column('CreatedAt', DateTime, default=datetime.datetime.utcnow)
)

# إنشاء الجداول لو مش موجودة
metadata.create_all(bind=engine)

# ============================================================
# 3. Security
# ============================================================
SECRET_KEY = "vwear_super_secret_key_2026_backend_project"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ============================================================
# 4. Uploads Folder
# ============================================================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# 5. FastAPI App
# ============================================================
app = FastAPI(title="VWear Backend API")

# Serve uploaded images as static files — الـ frontend يقدر يعرضها
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 6. Pydantic Schemas
# ============================================================

class UserSignup(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# ✅ User Model — بيرجع بيانات اليوزر بشكل نظيف (من غير password)
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: datetime.datetime

# ✅ Image Model — بيرجع الصور المحفوظة للـ user
class UserImagesResponse(BaseModel):
    user_id: int
    front_image: Optional[str]
    back_image: Optional[str]
    left_image: Optional[str]
    right_image: Optional[str]

# ============================================================
# 7. Helper Functions
# ============================================================

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

def save_image(file: UploadFile) -> str:
    """يحفظ الصورة على السيرفر ويرجع الـ path"""
    ext = os.path.splitext(file.filename)[1]  # .jpg / .png إلخ
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"/uploads/{filename}"  # الـ URL اللي الـ frontend هيستخدمه

# ============================================================
# 8. Auth Endpoints
# ============================================================

@app.post("/signup")
async def signup(user: UserSignup, db: Session = Depends(get_db)):
    query = select(users_table).where(
        (users_table.c.Email == user.email) |
        (users_table.c.Username == user.username)
    )
    existing_user = db.execute(query).fetchone()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or Email already registered")

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
        return {"message": "User created successfully", "token": token, "username": user.username}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    query = select(users_table).where(users_table.c.Email == user.email)
    db_user = db.execute(query).fetchone()
    if not db_user or not verify_password(user.password, db_user.PasswordHash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(db_user.Email)
    return {"message": "Login successful", "token": token, "username": db_user.Username}

# ============================================================
# 9. User Profile Endpoint ✅ (User Model)
# ============================================================

@app.get("/profile", response_model=UserResponse)
def get_profile(user_data=Depends(verify_token), db: Session = Depends(get_db)):
    """يرجع بيانات اليوزر الحالي من الـ token"""
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        id=db_user.Id,
        username=db_user.Username,
        email=db_user.Email,
        created_at=db_user.CreatedAt
    )

# ============================================================
# 10. Image Upload Endpoints ✅ (Image Upload System)
# ============================================================

@app.post("/upload-image")
async def upload_image(
    front: Optional[UploadFile] = File(None),
    back: Optional[UploadFile] = File(None),
    left: Optional[UploadFile] = File(None),
    right: Optional[UploadFile] = File(None),
    user_data=Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    يستقبل صور المستخدم (front, back, left, right) ويحفظها.
    ممكن ترفع صورة واحدة أو أكتر في نفس الوقت.
    """
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = db_user.Id

    # حفظ الصور اللي اتبعتوا
    saved = {}
    if front:
        saved["FrontImage"] = save_image(front)
    if back:
        saved["BackImage"] = save_image(back)
    if left:
        saved["LeftImage"] = save_image(left)
    if right:
        saved["RightImage"] = save_image(right)

    if not saved:
        raise HTTPException(status_code=400, detail="No images provided")

    # لو اليوزر عنده صور قبل كده → Update، لو لأ → Insert
    existing = db.execute(
        select(user_images_table).where(user_images_table.c.UserId == user_id)
    ).fetchone()

    try:
        if existing:
            db.execute(
                user_images_table.update()
                .where(user_images_table.c.UserId == user_id)
                .values(**saved)
            )
        else:
            db.execute(
                user_images_table.insert().values(UserId=user_id, **saved)
            )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Images uploaded successfully", "paths": saved}


@app.get("/my-images", response_model=UserImagesResponse)
def get_my_images(user_data=Depends(verify_token), db: Session = Depends(get_db)):
    """يرجع الصور المحفوظة للـ user الحالي"""
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    images = db.execute(
        select(user_images_table).where(user_images_table.c.UserId == db_user.Id)
    ).fetchone()

    if not images:
        return UserImagesResponse(
            user_id=db_user.Id,
            front_image=None, back_image=None,
            left_image=None, right_image=None
        )

    return UserImagesResponse(
        user_id=db_user.Id,
        front_image=images.FrontImage,
        back_image=images.BackImage,
        left_image=images.LeftImage,
        right_image=images.RightImage
    )

# ============================================================
# 11. Health Check
# ============================================================

@app.get("/")
def home():
    return {"message": "VWear Backend Running Successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
