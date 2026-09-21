# describes and creates the docker image required for this stack
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONNONBUFFERED=1

# Set working directory inside the container
WORKDIR /flight-app

# Install dependencies first (takes advantage of Docker layer caching)
COPY requirements.txt /flight-app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the Django project files
COPY . /flight-app/

# Expose port 8000 for the Django development server
EXPOSE 8000

# Default command to run Django's dev server
CMD ["python3", "manage.py", "runserver", "0.0.0.0:8000"]
