from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
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
import smtplib
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
    

def create_access_token(email: str):
    payload = {
        "sub": email,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)    }
    
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
    job = await job_queue.add_job(user_email=email, outfit_url=final_outfit_path_or_url)

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

"""
========================================================
الكود ده بيحل مشكلة الـ Frontend اللي بيستنى رد فوري
========================================================

المشكلة الأصلية:
- الفرونت يبعت request لـ /generate-tryon
- الباك يرجع {"job_id": "xxx"} فوراً
- الفرونت مش بيعمل polling → مش بيشوف النتيجة أبداً

الحل:
- ضيفنا endpoint مباشر /generate-tryon-sync بيستنى الموديل
- وضيفنا polling endpoint /queue/job/{job_id}/wait للـ async flow
- الفرونت يختار اللي يناسبه

========================================================
الكود ده بيتضاف في main.py بعد الـ imports الموجودة
========================================================
"""

# ============================================================
# OPTION A — Synchronous endpoint (الأبسط والمضمون للـ Frontend)
# بيستبدل /generate-tryon الموجود أو بيتضاف جنبه
# ============================================================

@app.post("/generate-tryon-sync")
async def generate_tryon_sync(
    person_image: UploadFile = File(...),
    outfit_url:   Optional[str]        = Form(None),
    outfit_file:  Optional[UploadFile] = File(None),
    user_data=Depends(verify_token),
):
    """
    ينتظر الموديل يخلص ويرجع النتيجة مباشرة.
    الفرونت بيستنى (max 3 دقايق) وبعدين يعرض الصورة.
    """
    email = user_data.get("sub")

    # 1. حفظ صورة الشخص
    ext      = os.path.splitext(person_image.filename)[1] if person_image.filename else ".jpg"
    filename = f"temp_{uuid.uuid4().hex}{ext}"
    local_path = os.path.join(UPLOAD_DIR, filename)

    with open(local_path, "wb") as buf:
        shutil.copyfileobj(person_image.file, buf)

    # 2. تحديد مصدر اللبس
    final_outfit = outfit_url

    if outfit_file and outfit_file.filename:
        o_ext      = os.path.splitext(outfit_file.filename)[1]
        o_filename = f"outfit_{uuid.uuid4().hex}{o_ext}"
        o_path     = os.path.join(UPLOAD_DIR, o_filename)
        with open(o_path, "wb") as buf:
            shutil.copyfileobj(outfit_file.file, buf)
        final_outfit = o_path
    print(f"DEBUG → person: {local_path}")
    print(f"DEBUG → outfit: {final_outfit}")
    if not final_outfit:
        raise HTTPException(400, "Please provide outfit_url or outfit_file")
    print(f"DEBUG → person: {local_path}")
    print(f"DEBUG → outfit: {final_outfit}")
    # 3. شغّل الموديل مباشرة (sync wait)
    try:
        result = await model.run(
            person_image_path=local_path,
            outfit_url=final_outfit,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 4. ارجع الـ URL للفرونت مباشرة
    return {
        "success":    True,
        "result_url": result["result_url"],
        "email":      email,
    }


# ============================================================
# OPTION B — الـ endpoint الأصلي Async + polling helper
# الفرونت بيتصل بـ /generate-tryon → يجيب job_id
# وبعدين بيعمل polling على /queue/job/{job_id}/wait
# ============================================================

@app.get("/queue/job/{job_id}/wait")
async def wait_for_job(job_id: str, user_data=Depends(verify_token)):
    """
    Long-polling: يستنى لحد ما الـ job يخلص (max 200 ثانية).
    الفرونت يتصل بيه مرة واحدة بعد /generate-tryon.
    """
    import asyncio

    max_wait = 200   # ثانية
    interval = 2     # فترة الاستطلاع

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
# Health check للـ Colab connection (بدون auth للتسهيل)
# ============================================================

@app.get("/model/health")
async def model_health():
    """
    بيتحقق إن الـ Colab server شغال.
    شغّله في المتصفح قبل ما تجرب الـ try-on.
    """
    import httpx
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

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)