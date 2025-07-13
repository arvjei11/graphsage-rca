FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY . .
# Pinning Werkzeug to a version compatible with Flask 2.1.2 to fix ImportError
RUN pip install Flask==2.1.2 "Werkzeug<3.0.0" kafka-python==2.0.2
 
# Command to run the application
CMD ["python", "app.py"]