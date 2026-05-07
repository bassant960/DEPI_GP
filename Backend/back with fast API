from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, MetaData, Table, select
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt
from pydantic import BaseModel, EmailStr
import datetime
import logging


# Database Configuration

DATABASE_FILE = "vwear.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///./{DATABASE_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

metadata = MetaData()


# Load Existing Tables

try:

    metadata.reflect(bind=engine)

    users_table = Table(
        'users',
        metadata,
        autoload_with=engine
    )

except Exception as e:

    logging.error(f"Database Error: {e}")

    raise Exception(
        "Could not connect to users table"
    )


# Security Configuration


SECRET_KEY = "CHANGE_THIS_SECRET_KEY"

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# FastAPI App

app = FastAPI(
    title="VWear Backend API"
)


# CORS
app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# Schemas
class UserSignup(BaseModel):

    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):

    email: EmailStr
    password: str

# Database Dependency

def get_db():

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Helper Functions

def hash_password(password: str):

    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
):

    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def create_access_token(email: str):

    payload = {
        "sub": email,

        "exp": datetime.datetime.utcnow() +
               datetime.timedelta(
                   hours=ACCESS_TOKEN_EXPIRE_HOURS
               )
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# Signup API
@app.post("/signup")
async def signup(
    user: UserSignup,
    db: Session = Depends(get_db)
):

    try:

        # Check existing email
        query = select(users_table).where(
            users_table.c.email == user.email
        )

        existing_user = db.execute(
            query
        ).fetchone()

        if existing_user:

            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )

        # Password validation
        if len(user.password) < 8:

            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters"
            )

        # Hash password
        hashed_pw = hash_password(
            user.password
        )

        # Insert user
        insert_stmt = users_table.insert().values(
            name=user.name,
            email=user.email,
            password=hashed_pw
        )

        db.execute(insert_stmt)

        db.commit()

        # Create token
        token = create_access_token(
            user.email
        )

        return {

            "message": "User created successfully",

            "token": token,

            "name": user.name,

            "email": user.email
        }

    except HTTPException as e:

        raise e

    except Exception as e:

        db.rollback()

        logging.error(f"Signup Error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )

# Login API
@app.post("/login")
async def login(
    user: UserLogin,
    db: Session = Depends(get_db)
):

    try:
        # Search user
        query = select(users_table).where(
            users_table.c.email == user.email
        )

        db_user = db.execute(
            query
        ).fetchone()

        # Validate user
        if not db_user:

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Verify password
        if not verify_password(
            user.password,
            db_user.password
        ):

            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )

        # Create token
        token = create_access_token(
            db_user.email
        )

        return {

            "message": "Login successful",

            "token": token,

            "name": db_user.name,

            "email": db_user.email
        }

    except HTTPException as e:

        raise e

    except Exception as e:

        logging.error(f"Login Error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )

# Home Route

@app.get("/")
def home():

    return {

        "message": "VWear Backend Running Successfully"
    }

# Run Server

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
