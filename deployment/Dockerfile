# Custom Frappe App Dockerfile
# Based on frappe/erpnext standard custom app containerization

ARG FRAPPE_VERSION=version-16
ARG PYTHON_VERSION=3.11.9
ARG NODE_VERSION=18.20.2

FROM frappe/frappe-worker:${FRAPPE_VERSION} AS builder

USER frappe

# Copy the tap_buddy source code into the builder
# Assumes context is the root of apps/tap_buddy
COPY --chown=frappe:frappe . /home/frappe/frappe-bench/apps/tap_buddy

# Install the app into the python virtual environment
RUN bench get-app tap_buddy --branch feature/whatsapp-group-integration --resolve-deps

# Compile assets if needed
RUN bench build --app tap_buddy

# -------------------------------------------------------------
# Final Worker Image (Web & Background Jobs)
# -------------------------------------------------------------
FROM frappe/frappe-worker:${FRAPPE_VERSION}

USER frappe

# Copy compiled apps and virtual environment from builder
COPY --from=builder --chown=frappe:frappe /home/frappe/frappe-bench/apps/tap_buddy /home/frappe/frappe-bench/apps/tap_buddy
COPY --from=builder --chown=frappe:frappe /home/frappe/frappe-bench/env /home/frappe/frappe-bench/env
COPY --from=builder --chown=frappe:frappe /home/frappe/frappe-bench/sites/apps.txt /home/frappe/frappe-bench/sites/apps.txt

# Ensure permissions
RUN chmod +x /home/frappe/frappe-bench/env/bin/gunicorn

# Expose Gunicorn port
EXPOSE 8000

# The default entrypoint from frappe-worker handles booting gunicorn or rq workers based on command
