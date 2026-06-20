# Dockerfile

# Base image includes GDAL, Python 3.11, and core geospatial libraries
FROM ghcr.io/osgeo/gdal:ubuntu-small-latest

# Set working directory
WORKDIR /app

# Install Python pip and system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
# requirements-docker.txt excludes Windows-only packages (pywin32)
COPY requirements-docker.txt .
RUN pip3 install --break-system-packages --ignore-installed -r requirements-docker.txt

# Copy project source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY config/pipeline_config.yaml ./config/pipeline_config.yaml
COPY config/study_area.geojson ./config/study_area.geojson
COPY tests/ ./tests/

# Set Python path
ENV PYTHONPATH=/app

# Default command runs config validation to confirm environment is healthy
CMD ["python3", "scripts/validate_config.py"]