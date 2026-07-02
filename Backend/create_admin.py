import sqlite3
import bcrypt
import os

# دوّر على vwear.db في كل المجلدات
db_path = None
for root, dirs, files in os.walk("D:\\DEPI\\Graduation_Project"):
    for f in files:
        if f == "vwear.db":
            db_path = os.path.join(root, f)
            print(f"Found database: {db_path}")
            break

if not db_path:
    print("ERROR: vwear.db not found! Run main.py first.")
    exit()

# عمل الـ Admin
password = "VW#Secure_84X!"
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# شوف لو admin موجود
cursor.execute("SELECT Email FROM Users WHERE Email = 'admin@vwear.com'")
if cursor.fetchone():
    # لو موجود، حوّله Admin بس
    cursor.execute("UPDATE Users SET Role='Admin', IsVerified=1 WHERE Email='admin@vwear.com'")
    print("Existing user updated to Admin!")
else:
    # لو مش موجود، اعمله
    cursor.execute("""
        INSERT INTO Users (Username, Email, PasswordHash, Role, IsVerified)
        VALUES (?, ?, ?, 'Admin', 1)
    """, ("admin", "admin@vwear.com", hashed))
    print("Admin user created!")

conn.commit()

# تأكيد
cursor.execute("SELECT Id, Username, Email, Role FROM Users")
print("\nAll users:", cursor.fetchall())

conn.close()
print("\nDone! Login with: admin@vwear.com / Admin123")
