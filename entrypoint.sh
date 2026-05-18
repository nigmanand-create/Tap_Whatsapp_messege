#!/bin/bash
set -e

# Define defaults
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}
REDIS_CACHE=${REDIS_CACHE:-redis-cache}
REDIS_QUEUE=${REDIS_QUEUE:-redis-queue}
SITE_NAME=${SITE_NAME:-tapbuddy.local}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin}

echo "========================================= Starting Entrypoint script ========================================="

# Function to wait for a service port
wait_for_port() {
  local service_name=$1
  local host=$2
  local port=$3
  echo "Waiting for ${service_name} at ${host}:${port}..."
  python3 -c "
import socket
import time
import sys

host = '${host}'
port = ${port}
service_name = '${service_name}'

for _ in range(30):
    try:
        with socket.create_connection((host, port), timeout=1):
            print(f'  ✓ {service_name} is up and running!')
            sys.exit(0)
    except OSError:
        time.sleep(1)

print(f'  ✗ Timeout: Could not connect to {service_name} at {host}:{port}')
sys.exit(1)
"
}

# Wait for PostgreSQL and Redis
wait_for_port "PostgreSQL" "$DB_HOST" "$DB_PORT"
wait_for_port "Redis Cache" "$REDIS_CACHE" 6379
wait_for_port "Redis Queue" "$REDIS_QUEUE" 6379

# Configure common site config in container
echo "Configuring common_site_config.json..."
python3 -c "
import json
import os

config_path = 'sites/common_site_config.json'
try:
    with open(config_path, 'r') as f:
        config = json.load(f)
except Exception:
    config = {}

config.update({
    'redis_cache': f'redis://{os.environ.get(\"REDIS_CACHE\", \"redis-cache\")}:6379',
    'redis_queue': f'redis://{os.environ.get(\"REDIS_QUEUE\", \"redis-queue\")}:6379',
    'redis_socketio': f'redis://{os.environ.get(\"REDIS_CACHE\", \"redis-cache\")}:6379',
    'socketio_port': 9000,
    'webserver_port': 8000,
    'serve_default_site': True,
    'use_redis_auth': False
})

with open(config_path, 'w') as f:
    json.dump(config, f, indent=1)
"

# Handle site-specific settings
SITE_CONFIG_PATH="sites/${SITE_NAME}/site_config.json"

if [ ! -f "$SITE_CONFIG_PATH" ]; then
  echo "Site ${SITE_NAME} config does not exist. Creating new site..."
  
  # Ensure site directory exists
  mkdir -p "sites/${SITE_NAME}"
  
  # Create new site with specified database parameters
  bench new-site "$SITE_NAME" \
    --db-type postgres \
    --db-host "$DB_HOST" \
    --db-port "$DB_PORT" \
    --db-name "${DB_NAME:-tapbuddy}" \
    --db-user "${DB_USER:-tapbuddy}" \
    --db-password "${DB_PASSWORD:-frappe}" \
    --admin-password "$ADMIN_PASSWORD" \
    --force
    
  echo "Installing tap_buddy application..."
  bench --site "$SITE_NAME" install-app tap_buddy
  
  echo "Enabling developer mode for testing..."
  bench --site "$SITE_NAME" set-config developer_mode 1
else
  echo "Site ${SITE_NAME} already exists. Updating configurations..."
  
  # Update database configuration to make sure it matches environment
  python3 -c "
import json
import os

config_path = 'sites/' + os.environ.get('SITE_NAME', 'tapbuddy.local') + '/site_config.json'
with open(config_path, 'r') as f:
    config = json.load(f)

config.update({
    'db_host': os.environ.get('DB_HOST', 'db'),
    'db_port': int(os.environ.get('DB_PORT', 5432)),
    'db_name': os.environ.get('DB_NAME', 'tapbuddy'),
    'db_user': os.environ.get('DB_USER', 'tapbuddy'),
    'db_password': os.environ.get('DB_PASSWORD', 'frappe')
})

with open(config_path, 'w') as f:
    json.dump(config, f, indent=1)
"
  
  echo "Running database migrations..."
  bench --site "$SITE_NAME" migrate
fi

# Execute process depending on container role
ROLE=$1
echo "Starting container with role: ${ROLE:-default}..."

if [ "$ROLE" = "web" ]; then
  exec bench serve --port 8000
elif [ "$ROLE" = "socketio" ]; then
  exec node apps/frappe/socketio.js
elif [ "$ROLE" = "worker" ]; then
  exec bench worker
elif [ "$ROLE" = "scheduler" ]; then
  exec bench schedule
else
  # If any custom command is passed, run it
  exec "$@"
fi
