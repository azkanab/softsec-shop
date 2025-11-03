### Build and install packages
FROM python:3.10

# task 2.5 fix
# create new user to prevent root error.
RUN useradd -ms /bin/bash appuser

# Install Python dependencies
WORKDIR /home/appuser/app
RUN chown -R appuser:appuser /home/appuser

USER appuser
COPY requirements.txt requirements.txt
COPY plugin_example  plugin_example
COPY flaskshop  flaskshop
COPY app.py  app.py

# change flag into '--no-cache-dir' to avoid bloating the image size.
RUN pip install --no-cache-dir -r requirements.txt

CMD ["flask", "run", "--host=0.0.0.0"]
