"""
WSGI config for teamboard project.

================================================================================
INTERVIEW PERSPECTIVE: WSGI (WEB SERVER GATEWAY INTERFACE)
================================================================================
1. What is WSGI (PEP 3333)?
   - A synchronous specification for communication between Python web applications
     and web servers (Gunicorn, uWSGI, Nginx, Apache mod_wsgi).
   - WSGI is synchronous and request/response-oriented. Each concurrent request
     typically requires a dedicated thread or process.

2. Production Deployment Pattern:
   - Client -> Reverse Proxy (Nginx) -> WSGI Application Server (Gunicorn) -> WSGI callable (application)
   - Nginx handles TLS termination, static asset offloading, buffering slow clients,
     and reverse proxies HTTP requests over a UNIX socket or local TCP port to Gunicorn.
================================================================================
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teamboard.settings')

application = get_wsgi_application()
