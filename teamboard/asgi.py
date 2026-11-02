"""
ASGI config for teamboard project.

================================================================================
INTERVIEW PERSPECTIVE: ASGI (ASYNCHRONOUS SERVER GATEWAY INTERFACE)
================================================================================
1. What is ASGI?
   - The asynchronous successor to WSGI, designed to handle long-lived connections,
     WebSockets, Server-Sent Events (SSE), and asynchronous HTTP request handling
     via Python's `asyncio` event loop.
   - Servers: Uvicorn, Daphne, Hypercorn.

2. When to choose ASGI vs WSGI?
   - WSGI is standard and battle-tested for traditional synchronous REST APIs.
   - ASGI is necessary when building real-time collaboration, streaming LLM tokens,
     chat applications, or high-concurrency I/O-bound microservices.
================================================================================
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teamboard.settings')

application = get_asgi_application()
