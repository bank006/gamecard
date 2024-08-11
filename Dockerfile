FROM python:3.9

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install eventlet

EXPOSE 8080

CMD ["gunicorn", "-k", "eventlet", "-b", "0.0.0.0:8080", "app:app"]
