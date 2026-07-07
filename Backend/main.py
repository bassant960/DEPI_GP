from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import BaseModel, EmailStr
from sqlalchemy import Text, create_engine, MetaData, Table, Column, Integer, Float, String, DateTime, select
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
import smtplib
import io
import cv2
import numpy as np
import httpx
from PIL import Image
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import bcrypt
from model import model
from job_queue import job_queue
from dotenv import load_dotenv
import os
import asyncio
from fastapi import BackgroundTasks 
base_dir = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(base_dir, ".env")

load_dotenv(dotenv_path)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = "vwear.db"
DATABASE_PATH = os.path.join(BASE_DIR, DATABASE_FILE)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
metadata = MetaData()


users_table = Table(
    'Users', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('Username', String(50), unique=True, nullable=False),
    Column('Email', String(100), unique=True, nullable=False),
    Column('PasswordHash', String(255), nullable=False),

    Column('Role', String(20), default="User"),
    Column('IsVerified', Integer, default=0),
    Column('VerificationToken', String(255), nullable=True),
    Column('ResetToken', String(255), nullable=True),
    Column("ResetTokenExpire",DateTime, nullable=True),
    Column('CreatedAt', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
)

user_images_table = Table(
    'UserImages', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('UserId', Integer, nullable=False),       
    Column('FrontImage', String(500), nullable=True),
    Column('BackImage', String(500), nullable=True),
    Column('LeftImage', String(500), nullable=True),
    Column('RightImage', String(500), nullable=True),
    Column('CreatedAt', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc)))

# stores every try-on result so history/count can be queried later
generated_images_table = Table(
    'GeneratedImages', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('UserId', Integer, nullable=False),
    Column('GeneratedImagePath', String(500), nullable=False),
    Column('ClothType', String(20), nullable=True),
    Column('CreatedAt', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
)

# body measurements + computed recommended sizes (recommendation only, not fed to CatVTON)
measurements_table = Table(
    'Measurements', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('UserId', Integer, nullable=False, unique=True),
    Column('Height', Float, nullable=True),
    Column('Weight', Float, nullable=True),
    Column('Chest', Float, nullable=True),
    Column('Waist', Float, nullable=True),
    Column('Hips', Float, nullable=True),
    Column('RecommendedTopSize', String(10), nullable=True),
    Column('RecommendedBottomSize', String(10), nullable=True),
    Column('CreatedAt', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
)

contact_messages_table = Table(
    "ContactMessages",metadata,

    Column("Id", Integer, primary_key=True, autoincrement=True),
    Column("Name", String(100)),
    Column("Email", String(100)),
    Column("Subject", String(200)),
    Column("Message", Text),

    Column("CreatedAt",DateTime,default=datetime.datetime.utcnow)
)

blacklist_table = Table(
    'BlacklistedTokens', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('Token', String(1000), nullable=False)
)
# admin-managed catalog of clothing items (was referenced but never defined originally)
clothing_table = Table(
    'ClothingCatalog', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('Name', String(100), nullable=False),
    Column('Category', String(50), nullable=True),
    Column('Brand', String(100), nullable=True),
    Column('SizeXS', Integer, default=0),
    Column('SizeS', Integer, default=0),
    Column('SizeM', Integer, default=0),
    Column('SizeL', Integer, default=0),
    Column('SizeXL', Integer, default=0),
    Column('SizeXXL', Integer, default=0),
    Column('Price', String(20), nullable=True),
    Column('ImageUrl', String(500), nullable=True),
    Column('CreatedAt', DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
)

metadata.create_all(bind=engine)

# ============================================================
# 3. Security
# ============================================================
SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_if_not_found")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
REMEMBER_ME_DAYS = 30
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("SENDER_EMAIL"),
    MAIL_PASSWORD=os.getenv("SENDER_PASSWORD"),
    MAIL_FROM=os.getenv("SENDER_EMAIL"),
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_FROM_NAME="VWEAR Support",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

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
# التعديل السحري: ضفنا ".." عشان نطلع برا فولدر Backend ونروح لـ Front-end
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "..", "Front-end")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # ← السطر ده مهم للتحميل

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
    remember_me: bool = False

class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    old_password: Optional[str] = None
    new_password: Optional[str] = None

class ForgotPassword(BaseModel):
    email: EmailStr

class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=6)

class ChangeRole(BaseModel):
    role: str

#  User Model 
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    created_at: Optional[datetime.datetime] = None 

#  Image Model 
class UserImagesResponse(BaseModel):
    user_id: int
    front_image: Optional[str]
    back_image: Optional[str]
    left_image: Optional[str]
    right_image: Optional[str]

class MeasurementsInput(BaseModel):
    height: float
    weight: float
    chest: float
    waist: float
    hips: float

# response shape for GET /clothes — was referenced but never defined originally
class ClothingResponse(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[str] = None
    image_url: Optional[str] = None
    size_xs: int = 0
    size_s: int = 0
    size_m: int = 0
    size_l: int = 0
    size_xl: int = 0
    size_xxl: int = 0

class ContactMessage(BaseModel):
    name: str = "VWear Guest"
    email: EmailStr
    subject: str
    message: str = Field(..., min_length=5, description="Message cannot be empty")

# ============================================================
# 7. Helper Functions
# ============================================================
# ============================================================
# Email Configurations
# ============================================================
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_email(receiver_email: str, subject: str, body: str):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        plain_bytes = plain_password.encode('utf-8')[:72]
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        return False
    

def create_access_token(email: str,remember_me: bool = False):
    if remember_me:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=REMEMBER_ME_DAYS)
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": email,
        "exp": expire
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    blacklisted = db.execute(
        select(blacklist_table)
        .where(blacklist_table.c.Token == token)
    ).fetchone()

    if blacklisted:
        raise HTTPException(
            status_code=401,
            detail="Token revoked"
        )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
    
def save_image(file: UploadFile) -> str:
    """يحفظ الصورة على السيرفر ويرجع الـ path"""
    # بنعالج الـ None المحتملة هنا عشان الـ Pylance والـ Type checker ميزعلوش
    safe_filename = file.filename if file.filename else "image.jpg"
    
    ext = os.path.splitext(safe_filename)[1]  
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return f"/uploads/{filename}"

def admin_required(
    user_data=Depends(verify_token),
    db: Session = Depends(get_db)
):
    user = db.execute(
        select(users_table)
        .where(users_table.c.Email == user_data["sub"])
    ).fetchone()

    # لازم نتأكد إن المستخدم موجود الأول
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # دلوقتي Pylance متأكد إن user مش بـ None
    if user.Role != "Admin":
        raise HTTPException(
            status_code=403,
            detail="Admins only"
        )

    return user

def pro_required(user_data=Depends(verify_token), db: Session = Depends(get_db)):
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if db_user.Role not in ["Pro", "Admin"]:
        raise HTTPException(
            status_code=403, 
            detail="Premium feature. Please upgrade to Pro Plan to access this."
        )
    return db_user
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
        verification_token = uuid.uuid4().hex
        
        insert_stmt = users_table.insert().values(
            Username=user.username,
            Email=user.email,
            PasswordHash=hashed_pw,
            Role="User",
            IsVerified=0,
            VerificationToken=verification_token
        )
        db.execute(insert_stmt)
        db.commit()
        token = create_access_token(user.email)
        
        # إرسال الإيميل الحقيقي للمستخدم
        verification_link = f"http://127.0.0.1:8000/verify-email/{verification_token}"
        email_body = f"""
        <h3>Welcome to VWear!</h3>
        <p>Please click the link below to verify your email:</p>
        <a href="{verification_link}">Verify My Account</a>
        """
        send_email(user.email, "VWear - Verify your account", email_body)

        return {
            "message": "User created successfully. Please check your email to verify your account.",
            "token": token,
            "username": user.username
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/verify-email/{token}")
def verify_email(token: str, db: Session = Depends(get_db)):

    user = db.execute(
        select(users_table).where(
            users_table.c.VerificationToken == token
        )
    ).fetchone()

    if not user:
        raise HTTPException(404, "Invalid token")

    db.execute(
        users_table.update()
        .where(users_table.c.Id == user.Id)
        .values(
            IsVerified=1,
            VerificationToken=None
        )
    )

    db.commit()

    return {"message": "Email verified successfully"}


@app.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    query = select(users_table).where(users_table.c.Email == user.email)
    db_user = db.execute(query).fetchone()
    if not db_user or not verify_password(user.password, db_user.PasswordHash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if db_user.IsVerified == 0:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email first"
        )

    token = create_access_token(db_user.Email, remember_me=user.remember_me)
    return {"message": "Login successful", "token": token, "username": db_user.Username, "remember_me": user.remember_me}


@app.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    token = credentials.credentials

    try:
        jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    db.execute(
        blacklist_table.insert().values(Token=token)
    )
    db.commit()

    return {"message": "Logged out successfully"}


@app.post("/forgot-password")
def forgot_password(
    data: ForgotPassword,
    db: Session = Depends(get_db)
):

    user = db.execute(
        select(users_table)
        .where(users_table.c.Email == data.email)
    ).fetchone()

    if not user:
        raise HTTPException(404, "Email not found")

    token = uuid.uuid4().hex

    expire_time = (
     datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=15)
    )

    db.execute(
    users_table.update()
    .where(users_table.c.Email == data.email)
    .values(
        ResetToken=token,
        ResetTokenExpire=expire_time
    )
 )
    db.commit()

    reset_link = reset_link = f"http://127.0.0.1:8000/static/reset_password.html?token={token}"
    email_body = f"""
    <h3>VWear Password Reset</h3>
    <p>You requested to reset your password. Please click the link below to set a new password:</p>
    <a href="{reset_link}">Reset My Password</a>
    <p>If you didn't request this, please ignore this email.</p>
    """
    send_email(data.email, "VWear - Password Reset Request", email_body)

    return {
        "message": "Password reset link has been sent to your email successfully."
    }
@app.post("/reset-password")
def reset_password(
    data: ResetPassword,
    db: Session = Depends(get_db)
):

    user = db.execute(
        select(users_table)
        .where(users_table.c.ResetToken == data.token)
    ).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail="Invalid reset token")

    # 🔥 التعديل الآمن والصحيح هنا:
    db_expire = user.ResetTokenExpire
    if db_expire and db_expire.tzinfo is None:
        db_expire = db_expire.replace(tzinfo=datetime.timezone.utc)

    # هنا بنقارن التوقيت المتعدل بالوقت الحالي المتظبط على الـ utc
    if (user.ResetTokenExpire is None or db_expire < datetime.datetime.now(datetime.timezone.utc)):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    db.execute(
        users_table.update()
        .where(users_table.c.Id == user.Id)
        .values(PasswordHash=hash_password(data.new_password), ResetToken=None, ResetTokenExpire=None)
    )

    db.commit()

    return {"message": "Password changed successfully"}
# ============================================================
# 9. User Profile Endpoint  (User Model)
# ============================================================

# ── GET PROFILE (تعديل بسيط لإرجاع الـ Role للـ Frontend) ──
@app.get("/profile", response_model=UserResponse)
def get_profile(user_data=Depends(verify_token), db: Session = Depends(get_db)):
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # بنرجع البيانات بالإضافة للـ Role عشان الفرونت اند يعرف خطة المستخدم (Free أو Pro)
    return UserResponse(
        id=db_user.Id,
        username=db_user.Username,
        email=db_user.Email,
        role=db_user.Role,
        created_at=db_user.CreatedAt
    )

# ── UPDATE PROFILE (النسخة المطورة لدعم تغيير الباسوورد) ──
@app.put("/profile")
def update_profile(
    data: ProfileUpdate, 
    user_data=Depends(verify_token), 
    db: Session = Depends(get_db)
):
    email = user_data["sub"]
    query = select(users_table).where(users_table.c.Email == email)
    user = db.execute(query).fetchone()

    if not user:
        raise HTTPException(404, "User not found")

    updated_values = {}
    
    # تحديث اسم المستخدم لو مبعوث
    if data.username:
        updated_values["Username"] = data.username

    # لو المستخدم طالب يغير الباسوورد
    if data.new_password:
        if not data.old_password:
            raise HTTPException(400, "Old password is required to set a new password")
        
        # التأكد من صحة الباسوورد القديم قبل التحديث
        if not verify_password(data.old_password, user.PasswordHash):
            raise HTTPException(401, "Incorrect old password")
            
        updated_values["PasswordHash"] = hash_password(data.new_password)

    if not updated_values:
        return {"message": "No changes provided"}

    db.execute(
        users_table.update()
        .where(users_table.c.Email == email)
        .values(**updated_values)
    )
    db.commit()

    return {"message": "Profile updated successfully"}

# ── DELETE PROFILE (سليم وممتاز كما هو) ──
@app.delete("/profile")
def delete_profile(
    user_data=Depends(verify_token), 
    db: Session = Depends(get_db)
):
    email = user_data["sub"]

    user = db.execute(
        select(users_table)
        .where(users_table.c.Email == email)
    ).fetchone()

    if not user:
        raise HTTPException(404, "User not found")

    # مسح الصور أولاً لمنع الأخطاء في الداتابيز
    db.execute(
        user_images_table.delete()
        .where(user_images_table.c.UserId == user.Id)
    )

    db.execute(
        users_table.delete()
        .where(users_table.c.Id == user.Id)
    )
    db.commit()

    return {"message": "Account deleted successfully"}

# ── ADMIN: CHANGE ROLE (سليم وممتاز كما هو) ──
@app.put("/admin/change-role/{user_id}")
def change_role(
    user_id: int,
    data: ChangeRole,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    db.execute(
        users_table.update()
        .where(users_table.c.Id == user_id)
        .values(Role=data.role)
    )
    db.commit()

    return {
        "message": f"Role changed to {data.role} successfully"
    }
# ============================================================
# 10. Image Upload Endpoints  (Image Upload System)
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
   
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    user_id = db_user.Id

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



# ============================================================
# 12. Virtual Try-On Endpoints (AI Integration)
# ============================================================
@app.post("/generate-tryon")
async def generate_tryon(
    background_tasks: BackgroundTasks,
    person_image: UploadFile = File(...),
    outfit_url: Optional[str] = Form(None), # خليناه اختياري
    outfit_file: Optional[UploadFile] = File(None), # ضيفنا إمكانية استقبال ملف اللبس
    cloth_type: str = Form("upper"),
    user_data=Depends(verify_token)
):
    email = user_data.get("sub")

    # 1. حفظ صورة الشخص مؤقتاً
    ext = os.path.splitext(person_image.filename)[1] if person_image.filename else ".jpg"
    filename = f"temp_{uuid.uuid4().hex}{ext}"
    local_path = os.path.join("uploads", filename)

    with open(local_path, "wb") as buffer:
        import shutil
        shutil.copyfileobj(person_image.file, buffer)

    # 2. التعامل مع اللبس: هل هو ملف مرفوع أم لينك جاهز؟
    final_outfit_path_or_url = outfit_url

    if outfit_file and outfit_file.filename:
        # لو اليوزر رفع ملف من جهازه، بنحفظه في فولدر uploads فوراً
        outfit_ext = os.path.splitext(outfit_file.filename)[1]
        outfit_filename = f"outfit_{uuid.uuid4().hex}{outfit_ext}"
        local_outfit_path = os.path.join("uploads", outfit_filename)

        with open(local_outfit_path, "wb") as buffer:
            shutil.copyfileobj(outfit_file.file, buffer)
        
        # بنخلي الـ Queue يتعامل مع مسار الملف المحلي كأنه هو الـ url
        final_outfit_path_or_url = local_outfit_path

    if not final_outfit_path_or_url:
        raise HTTPException(status_code=400, detail="Please select an outfit or upload one!")

    # 3. نضيف المهمة للـ Queue بالمسار المحدث
    job = await job_queue.add_job(user_email=email, outfit_url=final_outfit_path_or_url,cloth_type=cloth_type)

    # 4. نبعت المهمة تشتغل في الخلفية
    background_tasks.add_task(job_queue.process_job, job.id, local_path, model)

    return {"message": "Job is processing", "job_id": job.id}

@app.get("/queue/stats")
def queue_stats(user_data=Depends(verify_token)):
    return job_queue.stats()


@app.get("/queue/my-jobs")
def my_jobs(user_data=Depends(verify_token)):
    email = user_data.get("sub")
    jobs = job_queue.get_user_jobs(email)
    return {"jobs": [j.dict() for j in jobs]}


@app.get("/queue/job/{job_id}")
def get_job(job_id: str, user_data=Depends(verify_token)):
    job = job_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.dict()


@app.get("/model/status")
def model_status(user_data=Depends(verify_token)):
    return model.status()

# ============================================================
# Try-On generation (sync) — waits for the model, returns the
# result directly, and logs the result so /history has data
# ============================================================

@app.post("/generate-tryon-sync")
async def generate_tryon_sync(
    person_image: UploadFile = File(...),
    outfit_url:   Optional[str]        = Form(None),
    outfit_file:  Optional[UploadFile] = File(None),
    cloth_type:   str                  = Form("upper"), 
    user_data=Depends(verify_token),
    db: Session = Depends(get_db),
):
    email = user_data.get("sub")

    # save the uploaded person photo
    ext      = os.path.splitext(person_image.filename)[1] if person_image.filename else ".jpg"
    filename = f"temp_{uuid.uuid4().hex}{ext}"
    local_path = os.path.join(UPLOAD_DIR, filename)

    with open(local_path, "wb") as buf:
        shutil.copyfileobj(person_image.file, buf)

    # resolve garment source: either an uploaded file or a URL
    final_outfit = outfit_url

    if outfit_file and outfit_file.filename:
        o_ext      = os.path.splitext(outfit_file.filename)[1]
        o_filename = f"outfit_{uuid.uuid4().hex}{o_ext}"
        o_path     = os.path.join(UPLOAD_DIR, o_filename)
        with open(o_path, "wb") as buf:
            shutil.copyfileobj(outfit_file.file, buf)
        final_outfit = o_path

    if not final_outfit:
        raise HTTPException(400, "Please provide outfit_url or outfit_file")

    # run CatVTON and wait for the result
    try:
        result = await model.run(
            person_image_path=local_path,
            outfit_url=final_outfit,
            cloth_type=cloth_type
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # log this generation so it shows up in /history and in the try count
    db_user = db.execute(
        select(users_table).where(users_table.c.Email == email)
    ).fetchone()

    if db_user:
        db.execute(
            generated_images_table.insert().values(
                UserId=db_user.Id,
                GeneratedImagePath=result["result_url"],
                ClothType=cloth_type,
            )
        )
        db.commit()

    return {
        "success":    True,
        "result_url": result["result_url"],
        "email":      email,
    }


# ============================================================
# Async flow: /generate-tryon returns a job_id, frontend polls
# this endpoint until the job is done
# ============================================================

@app.get("/queue/job/{job_id}/wait")
async def wait_for_job(job_id: str, user_data=Depends(verify_token)):
    """Long-polls a queued job until done/failed or 200s timeout."""
    import asyncio

    max_wait = 200
    interval = 2

    for _ in range(max_wait // interval):
        job = job_queue.get_job(job_id)

        if not job:
            raise HTTPException(404, "Job not found")

        if job.status == "done":
            return {
                "status":     "done",
                "result_url": job.result_url,
            }

        if job.status == "failed":
            raise HTTPException(500, f"Job failed: {job.error}")

        await asyncio.sleep(interval)

    raise HTTPException(504, "Job timeout — Colab is taking too long")


# ============================================================
# Try-on history — everything a user has generated, newest first.
# Powers both "View All" and the tries counter on the dashboard.
# ============================================================

@app.get("/history")
def get_history(user_data=Depends(verify_token), db: Session = Depends(get_db)):
    email = user_data.get("sub")
    db_user = db.execute(
        select(users_table).where(users_table.c.Email == email)
    ).fetchone()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    rows = db.execute(
        select(generated_images_table)
        .where(generated_images_table.c.UserId == db_user.Id)
        .order_by(generated_images_table.c.CreatedAt.desc())
    ).fetchall()

    return {
        "count": len(rows),
        "items": [
            {
                "id":         r.Id,
                "url":        r.GeneratedImagePath,
                "cloth_type": r.ClothType,
                "created_at": str(r.CreatedAt) if r.CreatedAt else None,
            }
            for r in rows
        ],
    }


# ============================================================
# Garment type auto-detect: filename keywords first (free, instant),
# then an OpenCV shape heuristic as a fallback
# ============================================================

@app.post("/detect-garment")
async def detect_garment(
    cloth_image: Optional[UploadFile] = File(None),
    cloth_url:   Optional[str]        = Form(None),
    user_data=Depends(verify_token),
):
    """
    يكتشف نوع اللبس تلقائياً (upper / lower / overall).
    مجاناً — بيستخدم keyword + (Edge/Contour Heuristics) by OpenCV.
    """
 

    # ── 1. Keyword classifier من اسم الملف ──────────────
    UPPER_KW   = {'shirt','top','blouse','hoodie','jacket','coat','sweater',
                  'tshirt','t-shirt','tee','pullover','vest','cardigan','crop',
                  'polo','sweatshirt','upper'}
    LOWER_KW   = {'pant','trouser','jean','skirt','short','legging',
                  'bottom','lower','chino'}
    OVERALL_KW = {'dress','jumpsuit','overall','romper','suit',
                  'gown','bodysuit'}

    filename = ""
    if cloth_image and cloth_image.filename:
        filename = cloth_image.filename.lower()
    elif cloth_url:
        filename = cloth_url.split("/")[-1].lower()

    name_lower = filename.replace("-", " ").replace("_", " ")
    for kw in UPPER_KW:
        if kw in name_lower:
            return {"cloth_type": "upper", "method": "keyword"}
    for kw in LOWER_KW:
        if kw in name_lower:
            return {"cloth_type": "lower", "method": "keyword"}
    for kw in OVERALL_KW:
        if kw in name_lower:
            return {"cloth_type": "overall", "method": "keyword"}

    # ── 2. Edge & Contour Heuristic باستخدام OpenCV ─────
    try:
        if cloth_image:
            img_bytes = await cloth_image.read()
        elif cloth_url:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(cloth_url)
                img_bytes = r.content
        else:
            raise HTTPException(400, "No image provided")

       # نفتح الصورة ونصغرها
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB").resize((128, 128))
        img_cv = np.array(img)
        
        # تحويل لرمادي
        gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
        
        # Blur خفيف لتنعيم الأطراف
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # garment is assumed darker than a light background
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # remove small noise specks inside/outside the garment mask
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = cnts[0] if len(cnts) == 2 else cnts[1] 
        
        # fill the largest contour into a solid mask
        mask_img = np.zeros_like(gray)
        if contours:
            cv2.drawContours(mask_img, contours, -1, (255), thickness=cv2.FILLED)

        mask = mask_img > 0

        if not contours or len(contours) == 0:
            return {"cloth_type": "upper", "method": "fallback_no_contours"}

        c = max(contours, key=cv2.contourArea)
        x, y, w, h_box = cv2.boundingRect(c)
        
        if w == 0 or h_box == 0:
            return {"cloth_type": "upper", "method": "fallback_zero_size"}
            
        roi_mask = mask[y:y+h_box, x:x+w]
        h_roi, w_roi = roi_mask.shape[0], roi_mask.shape[1]
        
        if h_roi == 0 or w_roi == 0:
            return {"cloth_type": "upper", "method": "fallback_zero_roi"}

        # fabric density in the top/middle/bottom thirds of the bounding box
        top_pct  = roi_mask[:h_roi//3,    :].mean()
        mid_pct  = roi_mask[h_roi//3:2*h_roi//3, :].mean()
        bot_pct  = roi_mask[2*h_roi//3:,  :].mean()
        
        aspect_ratio = h_box / float(w)

        # ── Leg-split check ──────────────────────────────────
        # Pants/shorts/skirts almost always show a visible gap between
        # the two legs near the hem. A t-shirt (even a wide, short one
        # with sleeves spread out) stays a single solid blob top-to-
        # bottom. Counting how many separate filled segments each row
        # has is a much more reliable "is this a lower-body garment?"
        # signal than density-ratio alone, which was flagging wide-
        # shouldered t-shirts as "lower".
        def _segments_in_row(row: np.ndarray) -> int:
            if not row.any():
                return 0
            edges = np.diff(row.astype(int))
            count = int(np.sum(edges == 1))
            if row[0]:
                count += 1
            return count

        bottom_band = roi_mask[int(h_roi * 0.65):, :]
        split_rows, checked_rows = 0, 0
        for row in bottom_band:
            if row.any():
                checked_rows += 1
                if _segments_in_row(row) >= 2:
                    split_rows += 1
        has_leg_split = checked_rows > 0 and (split_rows / checked_rows) > 0.25

        print(f"DEBUG ROI → AR: {aspect_ratio:.2f} | Top: {top_pct:.2f} | Mid: {mid_pct:.2f} | Bot: {bot_pct:.2f} | LegSplit: {has_leg_split}")

        # a tall garment on its own (e.g. a long/oversized t-shirt) still has
        # AR > 1.4 with full top/bottom density, so aspect ratio alone used to
        # misclassify it as "overall". Real one-piece outfits (dresses,
        # jumpsuits) also pinch in at the waist, so require a narrower middle
        # band as well before calling it "overall".
        waist_pinch = mid_pct < (top_pct + bot_pct) / 2 * 0.85

        if has_leg_split and not (aspect_ratio > 2.0 and waist_pinch):
            # clear two-leg gap → pants/shorts/skirt, unless it's actually
            # a pinched-waist one-piece (dress/jumpsuit split by the hem)
            cloth_type = "lower"

        elif aspect_ratio > 2.0 and bot_pct > 0.20 and top_pct > 0.20 and waist_pinch:
            cloth_type = "overall"

        # fallback for lower garments with no clean leg gap detected
        # (e.g. tight leggings, or a pencil skirt): density drops toward
        # the bottom on a long lower
        elif aspect_ratio > 1.2 and bot_pct < mid_pct * 0.95 and top_pct < 0.40:
            cloth_type = "lower"

        else:
            cloth_type = "upper"

        return {"cloth_type": cloth_type, "method": "cv2_otsu_bbox"}
    except Exception as e:
        print(f"Detect Error: {e}")
        return {"cloth_type": "upper", "method": "default_fallback", "error": str(e)}


# ============================================================
# Size recommendation — purely informational for the user.
# CatVTON never receives a "size" input, so this never touches
# the generation flow in /generate-tryon-sync.
# ============================================================

def compute_recommended_sizes(chest: float, waist: float, hips: float):
    """Simple chest/waist -> size chart. Tune the cm breakpoints as needed."""
    def band(value: float) -> str:
        if value < 86:  return "XS"
        if value < 94:  return "S"
        if value < 102: return "M"
        if value < 110: return "L"
        if value < 118: return "XL"
        return "XXL"

    top_size    = band(chest)
    bottom_size = band(waist if waist else hips)
    return top_size, bottom_size


@app.post("/measurements")
def save_measurements(
    data: MeasurementsInput,
    user_data=Depends(verify_token),
    db: Session = Depends(get_db),
):
    email = user_data.get("sub")
    db_user = db.execute(
        select(users_table).where(users_table.c.Email == email)
    ).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    top_size, bottom_size = compute_recommended_sizes(data.chest, data.waist, data.hips)

    existing = db.execute(
        select(measurements_table).where(measurements_table.c.UserId == db_user.Id)
    ).fetchone()

    values = dict(
        Height=data.height,
        Weight=data.weight,
        Chest=data.chest,
        Waist=data.waist,
        Hips=data.hips,
        RecommendedTopSize=top_size,
        RecommendedBottomSize=bottom_size,
    )

    if existing:
        db.execute(
            measurements_table.update()
            .where(measurements_table.c.UserId == db_user.Id)
            .values(**values)
        )
    else:
        db.execute(
            measurements_table.insert().values(UserId=db_user.Id, **values)
        )
    db.commit()

    return {"recommended_top_size": top_size, "recommended_bottom_size": bottom_size}


@app.get("/measurements")
def get_measurements(user_data=Depends(verify_token), db: Session = Depends(get_db)):
    email = user_data.get("sub")
    db_user = db.execute(
        select(users_table).where(users_table.c.Email == email)
    ).fetchone()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    row = db.execute(
        select(measurements_table).where(measurements_table.c.UserId == db_user.Id)
    ).fetchone()

    if not row:
        return {"has_measurements": False}

    return {
        "has_measurements": True,
        "recommended_top_size": row.RecommendedTopSize,
        "recommended_bottom_size": row.RecommendedBottomSize,
    }


# ============================================================
# Colab model health check (no auth, so it's easy to ping)
# ============================================================

@app.get("/model/health")
async def model_health():
    """Checks the Colab tunnel is reachable before running a try-on."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(model.health_url)
        return {
            "backend": "ok",
            "colab":   r.json(),
            "tunnel":  model.base_url,
        }
    except Exception as e:
        return {
            "backend": "ok",
            "colab":   "unreachable",
            "error":   str(e),
            "hint":    "شغّل الـ Colab notebook وحدّث MODEL_API_URL في .env",
        }
@app.post("/contact")
async def contact(
    data: ContactMessage,
    db: Session = Depends(get_db)
):

    db.execute(
        contact_messages_table.insert().values(
            Name=data.name,
            Email=data.email,
            Subject=data.subject,
            Message=data.message
        )
    )

    db.commit()

    html = f"""
    <h2>New Contact Message</h2>

    <p><b>Name:</b> {data.name}</p>

    <p><b>Email:</b> {data.email}</p>

    <p><b>Subject:</b> {data.subject}</p>

    <p><b>Message:</b></p>

    <p>{data.message}</p>
    """

    message = MessageSchema(
        subject=f"Contact Us - {data.subject}",
        recipients=["vwear.authentication@gmail.com"],
        body=html,
        subtype="html"
    )

    fm = FastMail(conf)

    await fm.send_message(message)
    

    return {
        "message": "Message sent successfully."
    }


# ============================================================
# ADMIN — Users
# ============================================================
 
@app.get("/admin/users")
def get_all_users(
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """جلب كل المستخدمين — Admin only"""
    users = db.execute(select(users_table)).fetchall()
    return [
        {
            "id":          u.Id,
            "username":    u.Username,
            "email":       u.Email,
            "role":        u.Role,
            "is_verified": u.IsVerified,
            "created_at":  str(u.CreatedAt) if u.CreatedAt else None
        }
        for u in users
    ]
 
 
@app.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """مسح مستخدم بالـ ID — Admin only"""
    user = db.execute(
        select(users_table).where(users_table.c.Id == user_id)
    ).fetchone()
 
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
 
    # مسح صور المستخدم أولاً لتجنب FK error
    db.execute(
        user_images_table.delete()
        .where(user_images_table.c.UserId == user_id)
    )
    db.execute(
        users_table.delete()
        .where(users_table.c.Id == user_id)
    )
    db.commit()
    return {"message": "User deleted successfully"}
 
 
# ============================================================
# ADMIN — Contact Messages
# ============================================================
 
@app.get("/admin/contact-messages")
def get_all_contact_messages(
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """جلب كل رسائل التواصل — Admin only"""
    messages = db.execute(select(contact_messages_table)).fetchall()
    return [
        {
            "id":         m.Id,
            "name":       m.Name,
            "email":      m.Email,
            "subject":    m.Subject,
            "message":    m.Message,
            "created_at": str(m.CreatedAt) if m.CreatedAt else None
        }
        for m in messages
    ]
 
 
@app.delete("/admin/contact-messages/{msg_id}")
def delete_contact_message(
    msg_id: int,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """مسح رسالة تواصل — Admin only"""
    msg = db.execute(
        select(contact_messages_table)
        .where(contact_messages_table.c.Id == msg_id)
    ).fetchone()
 
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
 
    db.execute(
        contact_messages_table.delete()
        .where(contact_messages_table.c.Id == msg_id)
    )
    db.commit()
    return {"message": "Message deleted successfully"}
 
 
# ============================================================
# Clothes — Public + Admin
# ============================================================
 
@app.get("/clothes", response_model=list[ClothingResponse])
def get_clothes(db: Session = Depends(get_db)):
    """جلب كل الملابس — Public"""
    clothes = db.execute(select(clothing_table)).fetchall()
    return [
        ClothingResponse(
            id=item.Id,
            name=item.Name,
            category=item.Category,
            brand=item.Brand,
            price=str(item.Price) if item.Price else None,
            image_url=item.ImageUrl,
            size_xs=item.SizeXS or 0,
            size_s=item.SizeS or 0,
            size_m=item.SizeM or 0,
            size_l=item.SizeL or 0,
            size_xl=item.SizeXL or 0,
            size_xxl=item.SizeXXL or 0
        )
        for item in clothes
    ]
 
 
@app.post("/admin/clothes")
async def add_clothing(
    name:     str = Form(...),
    category: str = Form(...),
    brand:    str = Form(""),
    price:    str = Form("0"),
    size_xs:  int = Form(0),
    size_s:   int = Form(0),
    size_m:   int = Form(0),
    size_l:   int = Form(0),
    size_xl:  int = Form(0),
    size_xxl: int = Form(0),
    file: UploadFile = File(...),
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """إضافة قطعة ملابس جديدة — Admin only"""
    image_path = save_image(file)
 
    db.execute(
        clothing_table.insert().values(
            Name=name,
            Category=category,
            Brand=brand,
            Price=price,
            ImageUrl=image_path,
            SizeXS=size_xs,
            SizeS=size_s,
            SizeM=size_m,
            SizeL=size_l,
            SizeXL=size_xl,
            SizeXXL=size_xxl
        )
    )
    db.commit()
    return {"message": "Clothing added successfully"}
 
 
@app.delete("/admin/clothes/{cloth_id}")
def delete_clothing(
    cloth_id: int,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """مسح قطعة ملابس — Admin only"""
    cloth = db.execute(
        select(clothing_table)
        .where(clothing_table.c.Id == cloth_id)
    ).fetchone()
 
    if not cloth:
        raise HTTPException(status_code=404, detail="Clothing not found")
 
    # مسح الصورة من uploads
    if cloth.ImageUrl:
        image_file = cloth.ImageUrl.replace("/uploads/", "")
        full_path  = os.path.join(UPLOAD_DIR, image_file)
        if os.path.exists(full_path):
            os.remove(full_path)
 
    db.execute(
        clothing_table.delete()
        .where(clothing_table.c.Id == cloth_id)
    )
    db.commit()
    return {"message": "Clothing deleted successfully"}
 
 
@app.put("/admin/clothes/{cloth_id}")
async def edit_clothing(
    cloth_id: int,
    name:     str = Form(...),
    category: str = Form(...),
    brand:    str = Form(""),
    price:    str = Form("0"),
    size_xs:  int = Form(0),
    size_s:   int = Form(0),
    size_m:   int = Form(0),
    size_l:   int = Form(0),
    size_xl:  int = Form(0),
    size_xxl: int = Form(0),
    file: Optional[UploadFile] = File(None),
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """تعديل قطعة ملابس — Admin only"""
    cloth = db.execute(
        select(clothing_table)
        .where(clothing_table.c.Id == cloth_id)
    ).fetchone()
 
    if not cloth:
        raise HTTPException(404, "Clothing not found")
 
    image_path = cloth.ImageUrl
 
    # لو في صورة جديدة، احذف القديمة واحفظ الجديدة
    if file and file.filename:
        if image_path:
            old_file  = image_path.replace("/uploads/", "")
            full_path = os.path.join(UPLOAD_DIR, old_file)
            if os.path.exists(full_path):
                os.remove(full_path)
        image_path = save_image(file)
 
    db.execute(
        clothing_table.update()
        .where(clothing_table.c.Id == cloth_id)
        .values(
            Name=name,
            Category=category,
            Brand=brand,
            Price=price,
            ImageUrl=image_path,
            SizeXS=size_xs,
            SizeS=size_s,
            SizeM=size_m,
            SizeL=size_l,
            SizeXL=size_xl,
            SizeXXL=size_xxl
        )
    )
    db.commit()
    return {"message": "Clothing updated successfully"}
 
 
# ============================================================
# ADMIN — Change User Role
# ============================================================
 
@app.put("/admin/change-role/{user_id}")
def change_role(
    user_id: int,
    data: ChangeRole,
    admin=Depends(admin_required),
    db: Session = Depends(get_db)
):
    """تغيير Role لأي مستخدم — Admin only"""
    db.execute(
        users_table.update()
        .where(users_table.c.Id == user_id)
        .values(Role=data.role)
    )
    db.commit()
    return {"message": f"Role changed to {data.role} successfully"}
 
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)