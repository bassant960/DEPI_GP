-- =========================
-- CREATE DATABASE
-- =========================
IF DB_ID('vwear') IS NULL
BEGIN
    CREATE DATABASE vwear;
END
GO

USE vwear;
GO
-- =========================
-- USERS
-- =========================
IF OBJECT_ID('Users', 'U') IS NULL
BEGIN
    CREATE TABLE Users (
        Id INT IDENTITY(1,1) PRIMARY KEY,
        Username NVARCHAR(50) UNIQUE NOT NULL,
        Email NVARCHAR(100) UNIQUE NOT NULL,
        PasswordHash NVARCHAR(255) NOT NULL,

        Role NVARCHAR(20) DEFAULT 'User',
        IsVerified INT DEFAULT 0,
        VerificationToken NVARCHAR(255) NULL,
        ResetToken NVARCHAR(255) NULL,

        CreatedAt DATETIME DEFAULT GETDATE()
    );
END
GO

-- =========================
-- USER IMAGES
-- =========================
IF OBJECT_ID('UserImages', 'U') IS NULL
BEGIN
    CREATE TABLE UserImages (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        UserId INT NOT NULL UNIQUE,

        FrontImage NVARCHAR(500),
        BackImage NVARCHAR(500),
        LeftImage NVARCHAR(500),
        RightImage NVARCHAR(500),

        ImageFormat NVARCHAR(20),
        FileSizeKB FLOAT,
        Width INT,
        Height INT,

        CreatedAt DATETIME DEFAULT GETDATE(),

        CONSTRAINT FK_UserImages_Users
            FOREIGN KEY (UserId)
            REFERENCES Users(Id)
            ON DELETE CASCADE
    );
END
GO

-- =========================
-- GENERATED IMAGES
-- =========================
IF OBJECT_ID('GeneratedImages', 'U') IS NULL
BEGIN
    CREATE TABLE GeneratedImages (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        UserId INT NOT NULL,

        GeneratedImagePath NVARCHAR(500) NOT NULL,

        CreatedAt DATETIME DEFAULT GETDATE(),

        CONSTRAINT FK_GeneratedImages_Users
            FOREIGN KEY (UserId)
            REFERENCES Users(Id)
            ON DELETE CASCADE
    );
END
GO

-- =========================
-- USER MEASUREMENTS
-- =========================
IF OBJECT_ID('Measurements', 'U') IS NULL
BEGIN
    CREATE TABLE Measurements (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        UserId INT NOT NULL,

        Height FLOAT,
        Weight FLOAT,
        Chest FLOAT,
        Waist FLOAT,
        Hips FLOAT,
        ShoulderWidth FLOAT,
        SleeveLength FLOAT,
        InseamLength FLOAT,

        RecommendedTopSize NVARCHAR(10),
        RecommendedBottomSize NVARCHAR(10),
        ConfidenceScore FLOAT,

        CreatedAt DATETIME DEFAULT GETDATE(),

        CONSTRAINT FK_Measurements_Users
            FOREIGN KEY (UserId)
            REFERENCES Users(Id)
            ON DELETE CASCADE
    );
END
GO

-- =========================
-- CLOTHING CATALOG
-- =========================
IF OBJECT_ID('ClothingCatalog', 'U') IS NULL
BEGIN
    CREATE TABLE ClothingCatalog (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        Name NVARCHAR(100) NOT NULL,
        Category NVARCHAR(50),
        Brand NVARCHAR(100),

        SizeXS INT DEFAULT 0,
        SizeS INT DEFAULT 0,
        SizeM INT DEFAULT 0,
        SizeL INT DEFAULT 0,
        SizeXL INT DEFAULT 0,
        SizeXXL INT DEFAULT 0,

        Price DECIMAL(10,2),
        ImageUrl NVARCHAR(500),

        CreatedAt DATETIME DEFAULT GETDATE()
    );
END
GO

-- =========================
-- SUBSCRIPTION PLANS
-- =========================
IF OBJECT_ID('SubscriptionPlans', 'U') IS NULL
BEGIN
    CREATE TABLE SubscriptionPlans (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        PlanName NVARCHAR(100) NOT NULL,
        Description NVARCHAR(MAX),

        DurationMonths INT NOT NULL,
        Price DECIMAL(10,2) NOT NULL,

        IsActive BIT DEFAULT 1
    );
END
GO

-- =========================
-- USER SUBSCRIPTIONS
-- =========================
IF OBJECT_ID('UserSubscriptions', 'U') IS NULL
BEGIN
    CREATE TABLE UserSubscriptions (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        UserId INT NOT NULL,
        PlanId INT NOT NULL,

        StartDate DATETIME,
        EndDate DATETIME,

        Status NVARCHAR(20) DEFAULT 'Active',

        CONSTRAINT FK_UserSubscriptions_Users
            FOREIGN KEY (UserId)
            REFERENCES Users(Id)
            ON DELETE CASCADE,

        CONSTRAINT FK_UserSubscriptions_Plans
            FOREIGN KEY (PlanId)
            REFERENCES SubscriptionPlans(Id)
    );
END
GO

-- =========================
-- CONTACT MESSAGES
-- =========================
IF OBJECT_ID('ContactMessages', 'U') IS NULL
BEGIN
    CREATE TABLE ContactMessages (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        UserId INT NULL,
        Subject NVARCHAR(200),
        Message NVARCHAR(MAX) NOT NULL,

        Status NVARCHAR(20) DEFAULT 'Pending',

        CreatedAt DATETIME DEFAULT GETDATE(),

        CONSTRAINT FK_ContactMessages_Users
            FOREIGN KEY (UserId)
            REFERENCES Users(Id)
            ON DELETE SET NULL
    );
END
GO

-- =========================
-- BLACKLISTED TOKENS
-- =========================
IF OBJECT_ID('BlacklistedTokens', 'U') IS NULL
BEGIN
    CREATE TABLE BlacklistedTokens (
        Id INT IDENTITY(1,1) PRIMARY KEY,

        Token NVARCHAR(1000) NOT NULL,

        CreatedAt DATETIME DEFAULT GETDATE()
    );
END
GO

