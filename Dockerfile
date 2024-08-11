# ใช้ภาพพื้นฐาน Python
FROM python:3.9

# ตั้งค่า working directory
WORKDIR /app

# คัดลอกไฟล์ทั้งหมดไปยัง working directory
COPY . /app

# อัปเดต pip
RUN pip install --upgrade pip

# ติดตั้ง dependencies
RUN pip install -r requirements.txt

# กำหนดพอร์ตที่แอปพลิเคชันจะฟัง
EXPOSE 5000

# รันแอปพลิเคชัน
CMD ["python", "app.py"]
