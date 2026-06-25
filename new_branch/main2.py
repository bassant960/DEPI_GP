from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, DateTime, select
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr, Field
from services.file_storage import save_user_image
from services.image_validation import validate_image
from typing import Optional
import datetime
import shutil
import os
import uuid
import uvicorn
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from model import model
from job_queue import job_queue

DATABASE_FILE = "vwear.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///./{DATABASE_FILE}"

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
    Column('CreatedAt', DateTime, default=datetime.datetime.utcnow)
)

user_images_table = Table(
    'UserImages', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('UserId', Integer, nullable=False),       
    Column('FrontImage', String(500), nullable=True),
    Column('BackImage', String(500), nullable=True),
    Column('LeftImage', String(500), nullable=True),
    Column('RightImage', String(500), nullable=True),
    Column('CreatedAt', DateTime, default=datetime.datetime.utcnow)
)
blacklist_table = Table(
    'BlacklistedTokens', metadata,
    Column('Id', Integer, primary_key=True, autoincrement=True),
    Column('Token', String(1000), nullable=False)
)
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
    created_at: datetime.datetime

#  Image Model 
class UserImagesResponse(BaseModel):
    user_id: int
    front_image: Optional[str]
    back_image: Optional[str]
    left_image: Optional[str]
    right_image: Optional[str]

# ============================================================
# 7. Helper Functions
# ============================================================
# ============================================================
# Email Configurations
# ============================================================
SENDER_EMAIL = "vwear.authentication@gmail.com"
SENDER_PASSWORD = "tddf bxfv whup bgit"

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

# def hash_password(password: str):
#     password = password.encode("utf-8")[:72].decode("utf-8", "ignore")
#     return pwd_context.hash(password)

# def verify_password(plain_password: str, hashed_password: str):
#     plain_password = plain_password.encode("utf-8")[:72].decode("utf-8", "ignore")
#     return pwd_context.verify(plain_password, hashed_password)
def hash_password(password: str):
    return password

def verify_password(plain_password: str, hashed_password: str):
    # مقارنة نصية بسيطة مؤقتة
    return plain_password == hashed_password

def create_access_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
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
    
# def save_image(file: UploadFile) -> str:
#     """يحفظ الصورة على السيرفر ويرجع الـ path"""
#     # بنعالج الـ None المحتملة هنا عشان الـ Pylance والـ Type checker ميزعلوش
#     safe_filename = file.filename if file.filename else "image.jpg"
    
#     ext = os.path.splitext(safe_filename)[1]  
#     filename = f"{uuid.uuid4().hex}{ext}"
#     file_path = os.path.join(UPLOAD_DIR, filename)
#     with open(file_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)
#     return f"/uploads/{filename}"

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

    token = create_access_token(db_user.Email)
    return {"message": "Login successful", "token": token, "username": db_user.Username}


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

    db.execute(
        users_table.update()
        .where(users_table.c.Email == data.email)
        .values(ResetToken=token)
    )
    db.commit()

    reset_link = f"http://127.0.0.1:8000/reset-password?token={token}"
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
        raise HTTPException(400, "Invalid token")

    db.execute(
        users_table.update()
        .where(users_table.c.Id == user.Id)
        .values(
            PasswordHash=hash_password(data.new_password),
            ResetToken=None
        )
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
    # 1. جلب بيانات المستخدم والتحقق من وجوده
    email = user_data.get("sub")
    query = select(users_table).where(users_table.c.Email == email)
    db_user = db.execute(query).fetchone()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # تعديل: الوصول إلى الـ ID في SQLAlchemy Core يتم عبر مفتاح أو دالة _mapping
    user_id = db_user._mapping["Id"] 

    # 2. معالجة الصور المرفوعة والتحقق منها
    saved = {}
    images = {
        "FrontImage": front,
        "BackImage": back,
        "LeftImage": left,
        "RightImage": right
    }

    for image_name, image_file in images.items():
        if image_file:
            valid, msg = validate_image(image_file)
            if not valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"{image_name}: {msg}"
                )
            saved[image_name] = save_user_image(image_file)

    # التحقق من أنه تم رفع صورة واحدة على الأقل
    if not saved:
        raise HTTPException(
            status_code=400,
            detail="No images provided"
        )

    # 3. حفظ المسارات في قاعدة البيانات (تحديث أو إدخال جديد)
    try:
        # التحقق مما إذا كان للمستخدم سجل صور سابق
        existing = db.execute(
            select(user_images_table).where(user_images_table.c.UserId == user_id)
        ).fetchone()

        if existing:
            # تحديث الأعمدة المرفوعة فقط دون تصفير الأعمدة القديمة
            db.execute(
                user_images_table.update()
                .where(user_images_table.c.UserId == user_id)
                .values(**saved)
            )
        else:
            # إدخال سجل جديد لأول مرة
            db.execute(
                user_images_table.insert().values(UserId=user_id, **saved)
            )
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
    person_image: UploadFile = File(...),
    outfit_url: str = Form(...),
    user_data=Depends(verify_token)
):
    email = user_data.get("sub")
    job = await job_queue.add_job(user_email=email, outfit_url=outfit_url)
    completed_job = await job_queue.process_job(
        job_id=job.id,
        person_image=person_image,
        model=model
    )
    if completed_job.status == "failed":
        raise HTTPException(status_code=500, detail=completed_job.error)
    return {"result_url": completed_job.result_url, "job_id": completed_job.id}


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



if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
