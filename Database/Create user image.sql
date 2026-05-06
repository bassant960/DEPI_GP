CREATE TABLE UserImages (
    Id INT IDENTITY(1,1) PRIMARY KEY,
    UserId INT NOT NULL,

    FrontImage NVARCHAR(500),
    BackImage NVARCHAR(500),
    LeftImage NVARCHAR(500),
    RightImage NVARCHAR(500),

    CreatedAt DATETIME DEFAULT GETDATE(),

    FOREIGN KEY (UserId) REFERENCES Users(Id)
    ON DELETE CASCADE
);