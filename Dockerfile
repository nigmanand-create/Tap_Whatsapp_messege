FROM python:3.14-rc-slim-bookworm

# Prevent interactive prompts during package installations
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for Frappe and PostgreSQL
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    git \
    build-essential \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js v18 and Yarn (needed for Socket.io and frontend asset bundling)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install --no-install-recommends -y nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g yarn

# Install bench CLI globally
RUN pip3 install --no-cache-dir frappe-bench

# Create a non-root 'frappe' user to run our application safely
RUN groupadd -g 1000 frappe \
    && useradd -u 1000 -g frappe -m -s /bin/bash frappe

# Establish work directory
WORKDIR /home/frappe/frappe-bench
RUN chown -R frappe:frappe /home/frappe/frappe-bench

# Copy repository content (respects .dockerignore)
COPY --chown=frappe:frappe . .

# Make reauth and reproducer scripts executable
RUN chmod +x apps/tap_buddy/scripts/reauth_glific.py || true
RUN chmod +x apps/tap_buddy/scripts/trace_glific_reproducer.py || true

# Switch to the non-root user
USER frappe

# Setup virtual environment and install python dependencies
RUN python3 -m venv env \
    && ./env/bin/pip install --no-cache-dir --upgrade pip \
    && ./env/bin/pip install --no-cache-dir -e apps/frappe \
    && ./env/bin/pip install --no-cache-dir -r apps/tap_buddy/requirements.txt \
    && ./env/bin/pip install --no-cache-dir -e apps/tap_buddy

# Set bench to developer mode and compile assets
RUN yarn install --cwd apps/frappe \
    && bench build

# Expose web server (8000) and socket.io websockets (9000)
EXPOSE 8000 9000

# Make entrypoint executable (using root to ensure correct permissions)
USER root
RUN chmod +x entrypoint.sh
USER frappe

ENTRYPOINT ["./entrypoint.sh"]
CMD ["web"]
