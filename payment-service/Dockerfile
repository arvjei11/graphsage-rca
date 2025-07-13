FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install Flask==2.1.2 "Werkzeug<3.0.0" kafka-python==2.0.2 requests==2.28.1
CMD ["python", "app.py"]