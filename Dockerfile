# Prepare the base environment.
FROM ghcr.io/dbca-wa/docker-apps-dev:ubuntu_2604_base_python AS builder_base_spatial_layer_monitor

LABEL maintainer="asi@dbca.wa.gov.au"
LABEL org.opencontainers.image.source="https://github.com/dbca-wa/spatial-layer-monitor"

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Australia/Perth
ENV PRODUCTION_EMAIL=True
ENV SECRET_KEY="ThisisNotRealKey"
SHELL ["/bin/bash", "-c"]
# Use Australian Mirrors
RUN sed 's/archive.ubuntu.com/au.archive.ubuntu.com/g' /etc/apt/sources.list > /etc/apt/sourcesau.list
RUN mv /etc/apt/sourcesau.list /etc/apt/sources.list
# Use Australian Mirrors

# Key for Build purposes only
ENV FIELD_ENCRYPTION_KEY="Mv12YKHFm4WgTXMqvnoUUMZPpxx1ZnlFkfGzwactcdM="

# Key for Build purposes only
RUN apt-get clean && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install --no-install-recommends -y \
    binutils \
    build-essential \
    iputils-ping \
    libgdal-dev \
    p7zip-full \ 
    python3-gunicorn \
    software-properties-common \    
    ssh

# Install newer gdal version that is secure
# RUN add-apt-repository ppa:ubuntugis/ubuntugis-unstable 
# RUN apt-get update
RUN apt-get install --no-install-recommends -y gdal-bin python3-gdal

RUN groupadd -g 5000 oim 
RUN useradd -g 5000 -u 5000 oim -s /bin/bash -d /app
RUN mkdir /app 
RUN chown -R oim.oim /app 

RUN apt-get install --no-install-recommends -y python3-pil

ENV TZ=Australia/Perth
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

COPY startup.sh /
RUN chmod 755 /startup.sh

# Install Python libs from requirements.txt.
FROM builder_base_spatial_layer_monitor AS python_libs_spatial_layer_monitor
WORKDIR /app
USER oim 
RUN virtualenv /app/venv
ENV PATH=/app/venv/bin:$PATH
RUN git config --global --add safe.directory /app

COPY requirements.txt ./
COPY python-cron ./
RUN whoami

# --- GDAL SETUP START ---
# 1. Provide the compiler with explicit paths to the GDAL C++ header files.
# In newer Ubuntu 26.04 / Python 3.14+ environments, the build system often fails 
# to automatically locate 'gdal.h'. These environment variables ensure the Python 
# wrapper can find the underlying C++ headers required for compilation.
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# 2. Synchronize and pre-install the Python GDAL package with the system library version.
# GDAL's Python bindings are extremely sensitive to version mismatches with the 
# system's 'libgdal'. By detecting the version via 'gdal-config' and installing it 
# separately, we avoid the "Failed to build GDAL" errors that occur when pip tries 
# to compile an incompatible version from 'requirements.txt'.
RUN export GDAL_VERSION=$(gdal-config --version) && \
    pip install --upgrade pip setuptools wheel && \
    pip install "GDAL==${GDAL_VERSION}.*"
# --- GDAL SETUP END ---

RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt 

COPY --chown=oim:oim spatial_layer_monitor spatial_layer_monitor
#COPY --chown=oim:oim thermalimageprocessing thermalimageprocessing
COPY --chown=oim:oim manage.py ./
RUN python manage.py collectstatic --noinput

# Install the project (ensure that frontend projects have been built prior to this step).
FROM python_libs_spatial_layer_monitor
COPY timezone /etc/timezone
COPY gunicorn.ini ./

COPY .git ./.git

EXPOSE 8080
HEALTHCHECK --interval=1m --timeout=5s --start-period=10s --retries=3 CMD ["wget", "-q", "-O", "-", "http://localhost:8080/"]
CMD ["/startup.sh"]
