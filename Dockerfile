# Use Python 3.11.5 base image
FROM python:3.11.5-slim

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory inside the container
WORKDIR /app

# Copy the requirements.txt file into the container
COPY requirements.txt .

# Install Python dependencies and system tools for healthcheck
RUN apt-get update && apt-get install -y curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt

# Copy all scripts and binaries into the container
COPY run.py .
COPY app.py .
COPY prompttemplates/ prompttemplates/
COPY assets/ assets/

# Create and set permissions for output directory
RUN mkdir -p /app/articles && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose the port
EXPOSE 8001

# Set healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8001/healthcheck || exit 1

# Set the entry point for the container
ENTRYPOINT ["python", "run.py"]