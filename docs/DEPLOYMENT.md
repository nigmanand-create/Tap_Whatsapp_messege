# Deployment
- **VM Architecture:** Google Cloud Compute Engine running Ubuntu.
- **Bench Architecture:** Supervisor managing Gunicorn and rq workers.
- **Redis:** Ports 11000 (Queue), 12000 (SocketIO), 13000 (Cache).
- **PostgreSQL:** Port 5432.
- **Firewall:** Open Port 443. Internal ports restricted to localhost.
