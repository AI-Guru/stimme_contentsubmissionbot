# Use Python 3.11.5 base image
FROM python:3.11.5

# Set working directory inside the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all scripts and binaries into the container
COPY run.py .
COPY app.py .
COPY prompttemplates/ prompttemplates/
COPY assets/ assets/

# Set the entry point for the container
ENTRYPOINT ["gradio", "run.py"]