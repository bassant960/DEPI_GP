-- =========================
-- USERS
-- =========================
CREATE TABLE IF NOT EXISTS Users (
    Id              INTEGER PRIMARY KEY AUTOINCREMENT,
    Username        TEXT(50) UNIQUE NOT NULL,
    Email           TEXT(100) UNIQUE NOT NULL,
    PasswordHash    TEXT(255) NOT NULL,
    CreatedAt       DATETIME DEFAULT (datetime('now'))
);

-- =========================
-- USER IMAGES
-- =========================
CREATE TABLE IF NOT EXISTS UserImages (
    Id              INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId          INTEGER NOT NULL UNIQUE,

    FrontImage      TEXT(500),
    BackImage       TEXT(500),
    LeftImage       TEXT(500),
    RightImage      TEXT(500),

    ImageFormat     TEXT(20),
    FileSizeKB      REAL,
    Width           INTEGER,
    Height          INTEGER,

    CreatedAt       DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (UserId)
        REFERENCES Users(Id)
        ON DELETE CASCADE
);

-- =========================
-- USER MEASUREMENTS
-- =========================
CREATE TABLE IF NOT EXISTS Measurements (
    Id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId                  INTEGER NOT NULL,

    Height                  REAL,
    Weight                  REAL,
    Chest                   REAL,
    Waist                   REAL,
    Hips                    REAL,
    ShoulderWidth           REAL,
    SleeveLength            REAL,
    InseamLength            REAL,

    RecommendedTopSize      TEXT(10),
    RecommendedBottomSize   TEXT(10),
    ConfidenceScore         REAL,

    CreatedAt               DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (UserId)
        REFERENCES Users(Id)
        ON DELETE CASCADE
);

-- =========================
-- CLOTHING CATALOG
-- =========================
CREATE TABLE IF NOT EXISTS ClothingCatalog (
    Id              INTEGER PRIMARY KEY AUTOINCREMENT,

    Name            TEXT(100) NOT NULL,
    Category        TEXT(50),
    Brand           TEXT(100),

    SizeXS          INTEGER DEFAULT 0,
    SizeS           INTEGER DEFAULT 0,
    SizeM           INTEGER DEFAULT 0,
    SizeL           INTEGER DEFAULT 0,
    SizeXL          INTEGER DEFAULT 0,
    SizeXXL         INTEGER DEFAULT 0,

    Price           REAL,
    ImageUrl        TEXT(500),

    CreatedAt       DATETIME DEFAULT (datetime('now'))
);

-- =========================
-- SUBSCRIPTION PLANS
-- =========================
CREATE TABLE IF NOT EXISTS SubscriptionPlans (
    Id              INTEGER PRIMARY KEY AUTOINCREMENT,

    PlanName        TEXT(100) NOT NULL,
    Description     TEXT,

    DurationMonths  INTEGER NOT NULL,
    Price           REAL NOT NULL,

    IsActive        INTEGER DEFAULT 1
);

-- =========================
-- USER SUBSCRIPTIONS
-- =========================
CREATE TABLE IF NOT EXISTS UserSubscriptions (
    Id              INTEGER PRIMARY KEY AUTOINCREMENT,

    UserId          INTEGER NOT NULL,
    PlanId          INTEGER NOT NULL,

    StartDate       DATETIME,
    EndDate         DATETIME,

    Status          TEXT(20) DEFAULT 'Active',

    FOREIGN KEY (UserId)
        REFERENCES Users(Id)
        ON DELETE CASCADE,

    FOREIGN KEY (PlanId)
        REFERENCES SubscriptionPlans(Id)
);

-- =========================
-- CONTACT MESSAGES
-- =========================
CREATE TABLE IF NOT EXISTS ContactMessages (
    Id              INTEGER PRIMARY KEY AUTOINCREMENT,

    UserId          INTEGER,
    Subject         TEXT(200),
    Message         TEXT NOT NULL,

    Status          TEXT(20) DEFAULT 'Pending',

    CreatedAt       DATETIME DEFAULT (datetime('now')),

    FOREIGN KEY (UserId)
        REFERENCES Users(Id)
        ON DELETE SET NULL
);
