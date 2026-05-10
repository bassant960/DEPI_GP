
CREATE TABLE IF NOT EXISTS Users (
    Id          INTEGER PRIMARY KEY AUTOINCREMENT,
    Username    TEXT(50)  UNIQUE NOT NULL,
    Email       TEXT(100) UNIQUE NOT NULL,   
    PasswordHash TEXT(255) NOT NULL,
    CreatedAt   DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS UserImages (
    Id          INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId      INTEGER NOT NULL UNIQUE,   

    FrontImage  TEXT(500),
    BackImage   TEXT(500),
    LeftImage   TEXT(500),
    RightImage  TEXT(500),
    CreatedAt   DATETIME DEFAULT (datetime('now')),
    FOREIGN KEY (UserId) REFERENCES Users(Id) ON DELETE CASCADE
);

