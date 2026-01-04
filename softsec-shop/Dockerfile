### Build and install packages
FROM python:3.10

# task 2.5 fix
# create new user to prevent root error.
ARG HOST_UID=1000
RUN useradd -u ${HOST_UID} -ms /bin/bash appuser

# Install Python dependencies
WORKDIR /home/appuser/app

# Install system packages (as root) needed for building some Python packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc \
 && rm -rf /var/lib/apt/lists/*
# Copy requirements and install Python packages (as root so console scripts are on system PATH)
COPY requirements.txt requirements.txt
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Change ownership of app folder to non-root user, then drop privileges
RUN chown -R appuser:appuser /home/appuser

# Copy application files
COPY plugin_example  plugin_example
COPY flaskshop  flaskshop
COPY app.py  app.py

# Switch to non-root user for running the app
ENV HOME=/home/appuser
WORKDIR /home/appuser/app 

# Expose port and run
EXPOSE 5000

# Make Flask CLI use your app module (app.py exposes app variable)
ENV FLASK_APP=app
ENV FLASK_ENV=development

#CMD ["flask", "run", "--host=0.0.0.0"]
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]
