import os

# ใช้พอร์ตที่กำหนดในตัวแปรสภาพแวดล้อม PORT หรือใช้พอร์ต 8080
bind = "0.0.0.0:" + os.getenv("PORT", "8080")
workers = 2
