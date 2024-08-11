FROM python:3.9

WORKDIR /app

COPY . /app

# อัปเดต pip
RUN pip install --upgrade pip

# ติดตั้ง dependencies
RUN pip install -r requirements.txt

# กำหนดพอร์ตที่แอปพลิเคชันจะฟัง
EXPOSE 5000

CMD ["gunicorn", "--bind", "127.0.0.1:5000", "app:app"]

