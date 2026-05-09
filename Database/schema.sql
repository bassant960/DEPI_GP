-- ============================================================
-- VWear Database Schema — SQLite Compatible
-- ============================================================
-- ملاحظة: الـ Backend بيستخدم SQLAlchemy اللي بيعمل الجداول
-- تلقائياً. الـ SQL ده للتوثيق أو لو عايز تشغله يدوياً.
-- ============================================================

-- جدول المستخدمين
CREATE TABLE IF NOT EXISTS Users (
    Id          INTEGER PRIMARY KEY AUTOINCREMENT,
    Username    TEXT(50)  UNIQUE NOT NULL,
    Email       TEXT(100) UNIQUE NOT NULL,   -- كان ناقص في النسخة القديمة
    PasswordHash TEXT(255) NOT NULL,
    CreatedAt   DATETIME DEFAULT (datetime('now'))
);

-- جدول صور المستخدمين
CREATE TABLE IF NOT EXISTS UserImages (
    Id          INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId      INTEGER NOT NULL UNIQUE,     -- UNIQUE: كل يوزر صف واحد بس
    FrontImage  TEXT(500),
    BackImage   TEXT(500),
    LeftImage   TEXT(500),
    RightImage  TEXT(500),
    CreatedAt   DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (UserId) REFERENCES Users(Id) ON DELETE CASCADE
);

-- ============================================================
-- الفرق عن النسخة القديمة:
-- ❌ IDENTITY(1,1)     → ✅ AUTOINCREMENT
-- ❌ NVARCHAR          → ✅ TEXT
-- ❌ GETDATE()         → ✅ datetime('now')
-- ❌ GO                → مش موجود في SQLite
-- ❌ Email مش موجود في Users  → ✅ متضاف
-- ============================================================
