"""
Gunicorn configuration file for deployment.
"""

# Server socket
bind = "0.0.0.0:10000"
backlog = 2048

# Worker processes
workers = 2
worker_class = 'sync'
timeout = 120
keepalive = 2

# Process naming
proc_name = 'shipex-tracking'

# Server mechanics
daemon = False
pidfile = None
umask = 0o002
user = None
group = None
tmp_upload_dir = None

# Logging
errorlog = '-'
loglevel = 'info'
accesslog = '-'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# App module - this is the Flask app to run
wsgi_app = 'app:app'

# Server hooks
def on_starting(server):
    print("Gunicorn server is starting...")

def on_exit(server):
    print("Gunicorn server is exiting...")

# App preloading
preload_app = True
max_requests = 1000
max_requests_jitter = 50 