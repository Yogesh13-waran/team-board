# TeamBoard: The Complete Backend & Full-Stack System Design Master Guide

> **Target Audience**: Backend Engineers, Full-Stack Engineers, Tech Leads, and Software Architects preparing for technical interviews or seeking deep, uncompromising mastery of Django, Django REST Framework, PostgreSQL, Docker, Database Internals, and Enterprise API Security.

---

## Complete Table of Contents

1. [Stack Overview & Architectural Topology](#1-stack-overview--architectural-topology)
2. [Operating System, Python Runtime & Execution Model](#2-operating-system-python-runtime--execution-model)
3. [PostgreSQL 16 & Relational Database Internals](#3-postgresql-16--relational-database-internals)
4. [Docker Containerization & Infrastructure Networking](#4-docker-containerization--infrastructure-networking)
5. [Django Web Framework & Request/Response Lifecycle](#5-django-web-framework--requestresponse-lifecycle)
6. [Django ORM Deep Dive: SQL Compilation & Query Tuning](#6-django-orm-deep-dive-sql-compilation--query-tuning)
7. [Database Transactions, ACID & Concurrency Controls](#7-database-transactions-acid--concurrency-controls)
8. [Django Signals vs Alternative Architectural Patterns](#8-django-signals-vs-alternative-architectural-patterns)
9. [Django REST Framework (DRF) Internals & Lifecycle](#9-django-rest-framework-drf-internals--lifecycle)
10. [Authentication, Cryptography & Token Security](#10-authentication-cryptography--token-security)
11. [Testing Methodology & Postman Automation](#11-testing-methodology--postman-automation)
12. [System Design: Scaling to 50,000+ Queries Per Second](#12-system-design-scaling-to-50000-queries-per-second)
13. [Step-by-Step Code Analysis (File-by-File Breakdown)](#13-step-by-step-code-analysis-file-by-file-breakdown)
14. [Master Interview Question & Answer Bank (30+ Scenarios)](#14-master-interview-question--answer-bank-30-scenarios)

---

## 1. Stack Overview & Architectural Topology

### The Problem Domain: B2B Multi-Tenant Knowledge Base
TeamBoard is a B2B SaaS platform providing a curated technical Q&A database. Customers (client companies) integrate TeamBoard directly into their helpdesks, internal developer documentation, and customer chatbots.

```
+───────────────────────────────────────────────────────────────────────────────────+
|                                  CLIENT LAYER                                     |
|     Customer Internal Helpdesk / Developer Portal / Slack Bot / Onboarding Bot    |
+───────────────────────────────────────────────────────────────────────────────────+
                                         │
                        HTTPS / JSON + Bearer <JWT Token>
                        POST /api/kb/query/ {"search": "select_related"}
                                         ▼
+───────────────────────────────────────────────────────────────────────────────────+
|                       REVERSE PROXY & APPLICATION GATEWAY                         |
|   Nginx (TLS Termination, Rate Limiting, Static Asset Offload, Slow-Loris Buffer) |
+───────────────────────────────────────────────────────────────────────────────────+
                                         │ UNIX Domain Socket / TCP Port 8000
                                         ▼
+───────────────────────────────────────────────────────────────────────────────────+
|                       TEAMBOARD BACKEND (WSGI / ASGI)                             |
|                                                                                   |
|  [Middleware Pipeline]                                                            |
|    SecurityMiddleware ──► SessionMiddleware ──► CommonMiddleware                 |
|    ──► CsrfViewMiddleware ──► AuthenticationMiddleware                            |
|                                                                                   |
|  [Django REST Framework Engine]                                                   |
|    1. Authenticate Request via SimpleJWT (Validates Signature against SECRET_KEY) |
|    2. Extract Tenant Identity from request.user.company (IDOR Prevention)         |
|    3. Permission Gate: IsAdminUser / IsAuthenticated                              |
|    4. Atomic Search & Metering:                                                   |
|       - Filter: Q(question__icontains) | Q(answer__icontains)                     |
|       - Audit Logging: QueryLog.objects.create(company, search_term, count)       |
|    5. Serializer Pipeline: Deserialization, Validation, JSON Serialization        |
+───────────────────────────────────────────────────────────────────────────────────+
                                         │ TCP Port 5432 (psycopg v3 Connection)
                                         ▼
+───────────────────────────────────────────────────────────────────────────────────+
|                   POSTGRESQL 16 ALPINE (DOCKER CONTAINER)                         |
|                                                                                   |
|  - Storage Engine: Heap files, 8KB Disk Pages, Write-Ahead Logging (WAL)          |
|  - Tables:                                                                        |
|      * auth_user    : Django built-in credentials & password hashes (PBKDF2)      |
|      * api_company  : Tenant profile, Role (client/admin), Unique API Key         |
|      * api_kbentry  : Knowledge base questions, answers, and category tags        |
|      * api_querylog : Immutable append-only audit trail for billing analytics     |
|  - Volume Persistence: postgres_data (Managed Docker Named Volume)                |
+───────────────────────────────────────────────────────────────────────────────────+
```

### Why B2B Identity Binding Eliminates IDOR
*Interview Question: "Why shouldn't you allow a client to specify their company_id in the request payload?"*
- **Vulnerability**: Insecure Direct Object Reference (IDOR). If the API allowed `{"company_id": 42, "search": "query"}`, any client could manipulate the ID to impersonate a competitor (`company_id: 1`).
- **Consequence**: Fraudulent usage-based billing, analytics poisoning, and unauthorized access to restricted features.
- **Remediation**: The backend resolves the tenant strictly from the server-validated credential:
  `tenant = request.user.company`
  The client has zero control over this resolution.

---

## 2. Operating System, Python Runtime & Execution Model

### 1. Python 3.14 Features & Execution Internals
- **Bytecode Compilation**: Python source code (`.py`) is compiled into bytecode instructions (`.pyc`), cached inside `__pycache__`.
- **Evaluation Loop (`ceval.c`)**: Python’s virtual machine reads opcodes sequentially. In Python 3.11–3.14, the **Specializing Adaptive Interpreter (PEP 659)** detects hot bytecode and optimizes types inline.
- **Global Interpreter Lock (GIL) & Free-Threading (PEP 703)**:
  - In traditional CPython, the GIL ensures only one native OS thread executes Python bytecode at any given moment, preventing race conditions on internal C structures.
  - In Python 3.13/3.14, experimental free-threading builds allow CPU-bound multithreaded execution across multiple physical cores without GIL contention.

### 2. Memory Management & Garbage Collection (GC)
- **Primary Mechanism: Reference Counting**:
  Every Python object (`PyObject`) maintains an `ob_refcnt` counter. When a variable goes out of scope or is reassigned, `ob_refcnt` decrements. When it hits zero, memory is freed immediately.
- **Secondary Mechanism: Generational Cyclic GC**:
  Reference counting cannot reclaim circular references (e.g., Object A references Object B, and Object B references Object A). CPython employs a generational garbage collector with 3 generations (Gen 0, Gen 1, Gen 2). Young objects are inspected frequently; long-lived objects are promoted to older generations.

### 3. Cryptographic Randomness: CSPRNG vs PRNG
- **`random` (PRNG)**: Uses the **Mersenne Twister algorithm** with a period of $2^{19937}-1$. It is completely deterministic. An attacker observing 624 consecutive 32-bit outputs can reconstruct the internal state and predict all future tokens.
- **`secrets` (CSPRNG)**: Uses the operating system's entropy pool:
  - Linux / POSIX: `/dev/urandom` / `getrandom()` system call (hardware noise, keyboard timings, interrupt jitter).
  - Windows: `BCryptGenRandom` / `CryptGenRandom`.
  - Used in TeamBoard for API keys via `secrets.token_urlsafe(32)` (256 bits of cryptographic entropy).

---

## 3. PostgreSQL 16 & Relational Database Internals

### 1. PostgreSQL Process Architecture
Unlike multi-threaded database engines (such as MySQL InnoDB), PostgreSQL uses a **multi-process architecture**:
- **Postmaster Process**: The parent process listening on port 5432.
- **Backend Worker Processes**: For every incoming TCP client connection, the Postmaster calls `fork()` to spawn an independent OS process. Each worker process consumes 5–10 MB of memory plus query workspace (`work_mem`).
- **Shared Memory**: All worker processes communicate through a shared memory buffer pool (`shared_buffers`) for caching disk pages.

```
                             Client Application (Django Backend)
                                             │ TCP Connection
                                             ▼
                             Postgres Postmaster (Parent)
                                             │ fork()
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
         Backend Worker Process 1                        Backend Worker Process 2
         (Own work_mem, private state)                   (Own work_mem, private state)
                     │                                               │
                     └───────────────────────┬───────────────────────┘
                                             │ Reads / Writes
                                             ▼
                                  [Shared Buffers (RAM)]
                                             │ Flushes
                                             ▼
                                 [Write-Ahead Log (WAL)]
                                             │ Checkpoints
                                             ▼
                                  [Data Files / Heap (Disk)]
```

### 2. Connection Pooling & PgBouncer
Because `fork()` is expensive and 1,000 concurrent processes degrade performance through CPU context-switching, production PostgreSQL deployments utilize a **connection pooler** (e.g., **PgBouncer**).
- **Session Pooling**: Connection assigned to client for the entire connection lifespan.
- **Transaction Pooling**: Connection assigned only for the duration of a transaction block. Once committed, the connection returns to the pool immediately.
- **Statement Pooling**: Connection assigned per SQL query (breaks multi-statement transactions).

### 3. Multi-Version Concurrency Control (MVCC)
PostgreSQL implements MVCC so that **reads never block writes, and writes never block reads**:
- When a row is updated, PostgreSQL does not overwrite the existing disk record. Instead, it inserts a new tuple with an updated `xmin` (creation transaction ID) and sets the `xmax` (expiry transaction ID) on the old tuple.
- **VACUUM & Autovacuum**: Dead tuples left behind by updates/deletions must be cleaned up by the `VACUUM` process to prevent table bloat and reclaim disk space.

### 4. Indexing Strategies
- **B-Tree (Balanced Tree)**: Default index. $O(\log N)$ lookups for equality (`=`) and range queries (`<`, `<=`, `>`, `>=`). Used on `Company.api_key` (`unique=True`) and primary keys.
- **GIN (Generalized Inverted Index)**: Essential for full-text search, arrays, and JSONB.
- **Case-Insensitive Wildcard Caveat (`ILIKE '%term%'`)**:
  A standard B-Tree index cannot be traversed for leading wildcards (`%search`). In high-volume systems, use **PostgreSQL Trigram Extension (`pg_trgm`)** with a GIN index:
  ```sql
  CREATE EXTENSION pg_trgm;
  CREATE INDEX kb_question_trgm_idx ON api_kbentry USING gin (question gin_trgm_ops);
  ```

---

## 4. Docker Containerization & Infrastructure Networking

### 1. Containers vs Virtual Machines
- **Virtual Machine**: Hypervisor virtualizes physical hardware. Each VM runs a full guest OS with its own kernel, consuming gigabytes of memory and requiring minutes to boot.
- **Docker Container**: Virtualizes the OS kernel. Containers share the host Linux kernel via:
  - **Namespaces**: Provide process isolation (PID, NET, IPC, MNT, UTS).
  - **Cgroups (Control Groups)**: Enforce hardware resource limits (CPU quotas, memory bounds).

```
   VIRTUAL MACHINES (Hardware Virtualization)        DOCKER CONTAINERS (Kernel Virtualization)
  +-----------------------------------------+       +-----------------------------------------+
  | App 1 | App 2 | App 3                   |       | App 1 | App 2 | App 3                   |
  | Guest OS 1 | Guest OS 2 | Guest OS 3    |       | Bins / Libs                             |
  | Hypervisor (Type 1 / Type 2)            |       | Docker Engine (containerd / runc)       |
  | Host Operating System                   |       | Host Linux Kernel (Namespaces / Cgroups)|
  | Physical Server Hardware                |       | Physical Server Hardware                |
  +-----------------------------------------+       +-----------------------------------------+
```

### 2. Docker Storage Drivers & Named Volumes
- Container writable layers use **OverlayFS2** (Copy-on-Write). When a container is deleted (`docker rm`), any data written to its local layer is destroyed.
- **Named Volume (`postgres_data:/var/lib/postgresql/data`)**: Bypasses the container storage driver and writes directly to host filesystem blocks managed by Docker, surviving container restarts and image updates.

### 3. Container Networking & Port Forwarding
- `ports: ["5432:5432"]`: Binds host port 5432 to container port 5432 via Docker’s userland proxy and iptables NAT rules.
- **Loopback Gotcha**: Inside a container, `localhost` (127.0.0.1) refers to the container itself. To communicate between containers on the same Docker bridge network, services resolve one another by **service name** (e.g., `db:5432`) through Docker’s embedded DNS server (`127.0.0.11`).

---

## 5. Django Web Framework & Request/Response Lifecycle

### 1. WSGI vs ASGI
- **WSGI (`teamboard/wsgi.py`, PEP 3333)**: Synchronous, request/response standard. A worker thread is blocked during database I/O.
- **ASGI (`teamboard/asgi.py`)**: Asynchronous standard powered by Python’s `asyncio` event loop. Allows non-blocking concurrency for WebSockets, SSE, and streaming responses.

### 2. The 12-Factor App Methodology
- **Factor III: Config in the Environment**: Secrets (`SECRET_KEY`, database passwords) must never reside in source control. TeamBoard loads them via `python-dotenv` from `.env`.
- **Factor VI: Stateless Processes**: Web worker processes share zero memory; state resides entirely in PostgreSQL.
- **Factor X: Dev/Prod Parity**: PostgreSQL is used across development (via Docker) and production, eliminating SQLite vs Postgres dialect discrepancies.

### 3. Complete Django Request Flow

```
1. Client HTTP Request arrives at port 8000
   │
2. WSGI Handler initializes Django environment
   │
3. Middleware Pipeline (Executed in top-to-bottom order):
   - SecurityMiddleware ──► SessionMiddleware ──► CommonMiddleware
   - CsrfViewMiddleware ──► AuthenticationMiddleware (attaches user to request)
   │
4. URL Dispatcher (teamboard.urls ──► api.urls)
   Matches URL path to View class (e.g. KBQueryView.as_view())
   │
5. DRF APIView Pipeline:
   - initialize_request() ──► wraps Django request into DRF Request
   - perform_authentication() ──► SimpleJWT decodes Bearer token
   - check_permissions() ──► IsAuthenticated / IsAdminUser evaluated
   - check_throttles() ──► evaluates rate limits
   │
6. View Method Handler:
   - Serializer deserialization and validation
   - ORM execution inside transaction.atomic()
   │
7. Content Negotiation & Renderer:
   - JSONRenderer serializes response data dictionary to JSON bytes
   │
8. Middleware Pipeline returns in reverse order (bottom-to-top)
   │
9. HTTP 200/201/400/401/403 delivered to Client
```

---

## 6. Django ORM Deep Dive: SQL Compilation & Query Tuning

### 1. QuerySet Lazy Evaluation Triggers
Creating a QuerySet (`entries = KBEntry.objects.filter(...)`) performs **zero database operations**.
The SQL query is only executed when the QuerySet is evaluated:
1. `list(queryset)`: Forces evaluation and populates the cache.
2. `for item in queryset:`: Iterates through cursor rows.
3. `len(queryset)`: Loads all rows into memory and measures count.
4. `queryset.count()`: Executes `SELECT COUNT(*)` without fetching rows.
5. `queryset.exists()`: Executes `SELECT 1 ... LIMIT 1` (fastest existence check).

### 2. Eliminating the N+1 Query Problem

| Technique | Method | SQL Strategy | Suitable Relations |
| :--- | :--- | :--- | :--- |
| **`select_related`** | SQL JOIN | Single SQL query using `INNER JOIN` or `LEFT OUTER JOIN` | `ForeignKey`, `OneToOneField` |
| **`prefetch_related`** | Multi-Query `IN` | Executes 1 initial query + 1 query per relation with `WHERE id IN (...)` | `ManyToManyField`, reverse `ForeignKey` |

```python
# N+1 Bad Practice:
logs = QueryLog.objects.all()
for log in logs:
    print(log.company.company_name)  # Triggers 1 separate SQL query per row!

# Optimized via select_related:
logs = QueryLog.objects.select_related('company')
for log in logs:
    print(log.company.company_name)  # 0 additional queries; fetched in initial JOIN!
```

### 3. Q Objects & Bitwise Operator Overloading
Django filter keyword arguments are chained via SQL `AND`. To generate SQL `OR` or `NOT`, Django provides `django.db.models.Q`:
```python
from django.db.models import Q

# SQL: WHERE question ILIKE '%term%' OR answer ILIKE '%term%'
query = Q(question__icontains=search_term) | Q(answer__icontains=search_term)
results = KBEntry.objects.filter(query)
```

### 4. Database Aggregations: `aggregate()` vs `annotate()`
- **`aggregate()`**: Scalar table reduction. Compiles to `SELECT COUNT(id) FROM api_querylog;`
- **`annotate()`**: Group-by computation. When preceded by `.values('search_term')`, it compiles to:
  ```sql
  SELECT search_term, COUNT(id) AS count
  FROM api_querylog
  GROUP BY search_term
  ORDER BY count DESC
  LIMIT 5;
  ```

---

## 7. Database Transactions, ACID & Concurrency Controls

### 1. The 4 ACID Properties in TeamBoard
1. **Atomicity**: In `KBQueryView`, searching the knowledge base and recording the `QueryLog` happen inside a single `with transaction.atomic():` block. Both succeed together, or both roll back.
2. **Consistency**: Database constraints (e.g. `api_key` `UNIQUE`, foreign key references) are never violated.
3. **Isolation**: Concurrent queries from other companies cannot see partially committed query logs.
4. **Durability**: Committed transactions are written to PostgreSQL’s Write-Ahead Log (WAL) on disk.

### 2. Savepoints & Nested Atomic Blocks
When nesting `transaction.atomic()` blocks, Django utilizes **SQL Savepoints**:
```sql
BEGIN;                         -- Outer block starts
  INSERT INTO api_querylog ...;
  SAVEPOINT svpt_1;            -- Inner block starts
    UPDATE api_company ...;
    -- If error occurs inside inner block:
    ROLLBACK TO SAVEPOINT svpt_1;
    RELEASE SAVEPOINT svpt_1;
COMMIT;                        -- Outer block completes
```

### 3. ANSI SQL Isolation Levels & Concurrency Anomalies

| Isolation Level | Dirty Reads | Non-Repeatable Reads | Phantom Reads | Serialization Anomalies |
| :--- | :---: | :---: | :---: | :---: |
| **Read Uncommitted** | Allowed | Allowed | Allowed | Allowed |
| **Read Committed** *(PostgreSQL Default)* | Prevented | Allowed | Allowed | Allowed |
| **Repeatable Read** | Prevented | Prevented | Prevented (Postgres MVCC) | Allowed |
| **Serializable** | Prevented | Prevented | Prevented | Prevented |

- **Row-Level Locking (`select_for_update`)**:
  ```python
  # Acquires exclusive row-level lock (SELECT ... FOR UPDATE) until transaction commits
  company = Company.objects.select_for_update().get(id=1)
  ```

---

## 8. Django Signals vs Alternative Architectural Patterns

### 1. Observer Pattern Implementation
- **Sender**: `User` model.
- **Signal**: `django.db.models.signals.post_save`.
- **Receiver**: `create_company_profile` callback decorated with `@receiver`.

### 2. Detection of First Creation: `created` vs `instance._state.adding`
Inside `Model.save_base()`:
1. Python sets `instance._state.adding = True` on newly instantiated objects.
2. Django checks `_state.adding` to choose between SQL `INSERT` and SQL `UPDATE`.
3. Following a successful `INSERT`, Django fires `post_save` with `created = True`.
4. Django then resets `instance._state.adding = False`.

### 3. Signal Traps & Caveats
1. **Bulk Operations Bypass Signals**:
   `User.objects.bulk_create([...])` and `QuerySet.update(...)` execute direct SQL and **do not fire `post_save` or `pre_save` signals**.
2. **Transaction Rollback Desynchronization**:
   If a signal triggers external side effects (e.g. sending an email or webhook) and the surrounding database transaction rolls back, the email was still sent.
   - *Fix*: Use `transaction.on_commit(callback)` to defer side effects until database commit.

---

## 9. Django REST Framework (DRF) Internals & Lifecycle

### 1. Serializer Pipeline & Mass-Assignment Protection
```
Client JSON Payload ──► Serializer(data=payload)
                             │
                             ▼
                    to_internal_value()  (Type coercion & field validation)
                             │
                             ▼
                    validate_<field>()   (Field-level custom rules)
                             │
                             ▼
                    validate()           (Cross-field validation)
                             │
             ┌───────────────┴───────────────┐
             ▼                               ▼
    is_valid() == True              is_valid() == False
    Populates .validated_data       Populates .errors ──► HTTP 400
```
- **Mass Assignment Defense**: Serializers define explicit writeable fields. Extra payload fields (like `role: admin`) are ignored, preventing privilege escalation.

### 2. Permissions Architecture & RBAC
- **`has_permission(self, request, view)`**: Evaluates global access for the endpoint.
- **`has_object_permission(self, request, view, obj)`**: Evaluates access to a specific instance.
- **HTTP 401 vs HTTP 403**:
  - `401 Unauthorized`: Request lacks valid authentication credentials.
  - `403 Forbidden`: Authenticated identity lacks permission (`IsAdminUser` rejects `role == client`).

---

## 10. Authentication, Cryptography & Token Security

### 1. JWT Cryptographic Anatomy

```
   HEADER: Algorithm & Token Type            PAYLOAD: Claims & Expiration               SIGNATURE: HMAC Verification
+─────────────────────────────────+    +──────────────────────────────────────+    +─────────────────────────────────────+
| {"alg": "HS256", "typ": "JWT"}  |    | {"token_type": "access",             |    | HMACSHA256(                         |
|                                 |    |  "exp": 1762097249,                  |    |   base64Url(header) + "." +         |
|                                 |    |  "user_id": 1}                       |    |   base64Url(payload),               |
|                                 |    |                                      |    |   SECRET_KEY)                       |
+─────────────────────────────────+    +──────────────────────────────────────+    +─────────────────────────────────────+
                 │                                         │                                          │
                 ▼ Base64URL                               ▼ Base64URL                                ▼ Base64URL
      eyJhbGciOiJIUzI1NiIsIn...      .         eyJ0b2tlbl90eXBlIjoiYW...       .          vL_2R2728BwhxY2lE0c3o-dJ...
```

- **Tamper Resistance**: If an attacker changes `user_id: 1` to `user_id: 2`, the cryptographic signature will not match when recomputed with `SECRET_KEY`, causing immediate rejection.

### 2. Token Invalidation & Blacklisting
Because stateless JWTs cannot be revoked natively prior to `exp` expiration:
1. **Short-lived access tokens** (e.g. 15–60 minutes).
2. **Refresh Token Rotation**: Each token refresh issues a new refresh token and blacklists the previous one.
3. **Redis Blacklist**: Store revoked token `jti` (JWT ID) claims in Redis with a TTL matching token lifetime.

---

## 11. Testing Methodology & Postman Automation

### 1. Test Isolation via `APITestCase`
- Django runs tests inside a database transaction and executes a `ROLLBACK` after each test method, ensuring tests cannot pollute shared state.
- In `test_api.py`, 15 comprehensive unit and integration tests cover all 11 required scenarios:
  - User registration & duplicate detection
  - Missing payload handling & role tampering rejection
  - Login authentication & bad credential handling
  - Search queries with matches & zero matches
  - Usage metering verification
  - Role-based admin access control (403 for client, 200 for admin)

### 2. Postman Collection Architecture
In `postman/TeamBoard_API.postman_collection.json`:
- **Dynamic Variables**: `base_url`, `client_token`, `admin_token`, `api_key`.
- **Test Scripts**: Automatically parse JSON responses and store credentials via:
  ```javascript
  pm.collectionVariables.set("client_token", pm.response.json().access);
  ```

---

## 12. System Design: Scaling to 50,000+ Queries Per Second

```
                                  [Route53 / Global DNS]
                                             │
                                             ▼
                             [Cloudflare CDN / WAF Shield]
                                             │
                                             ▼
                             [Application Load Balancers]
                                             │
                     ┌───────────────────────┴───────────────────────┐
                     ▼                                               ▼
         [Django Gunicorn Pod 1]                         [Django Gunicorn Pod 2]
                     │                                               │
           ┌─────────┴─────────┐                           ┌─────────┴─────────┐
           ▼                   ▼                           ▼                   ▼
     [Redis Cache]       [Apache Kafka]              [Redis Cache]       [Apache Kafka]
    (Cache-Aside Q&A)  (Async Usage Meter)          (Cache-Aside Q&A)  (Async Usage Meter)
           │                   │                           │                   │
           │                   ▼                           │                   ▼
           │          [Consumer Service]                   │          [Consumer Service]
           │                   │                           │                   │
           ▼                   ▼                           ▼                   ▼
    [Postgres Read]    [ClickHouse Logs]            [Postgres Read]    [ClickHouse Logs]
       Replica            (Analytics)                  Replica            (Analytics)
```

1. **Cache-Aside Layer (Redis)**:
   Cache popular search queries (`kb:query:<hash>`). Lookups complete in under 2ms without querying PostgreSQL.
2. **Read-Replicas**:
   Split reads and writes using Django multi-db routers (`db_for_read` directed to read replicas; `db_for_write` directed to primary).
3. **Asynchronous Audit Logging**:
   Replace synchronous SQL `QueryLog.objects.create()` with an event pushed to **Apache Kafka** or **AWS SQS**. Dedicated stream consumers batch-insert millions of audit rows into **ClickHouse** or **TimescaleDB** without slowing down search queries.

---

## 13. Step-by-Step Code Analysis (File-by-File Breakdown)

### 1. `manage.py`
- Sets `DJANGO_SETTINGS_MODULE = 'teamboard.settings'`.
- Invokes `execute_from_command_line(sys.argv)`.
- Discovers installed apps and boots the administrative runner.

### 2. `teamboard/settings.py`
- Uses `python-dotenv` to load `.env` variables (12-Factor App methodology).
- Connects to PostgreSQL via `django.db.backends.postgresql` with `psycopg` (v3).
- Implements global Zero Trust authentication via `REST_FRAMEWORK` defaults:
  `JWTAuthentication` and `IsAuthenticated`.
- Configures `SIMPLE_JWT` token lifetimes.

### 3. `teamboard/urls.py` & `api/urls.py`
- Root router maps `/api/` to `api.urls`.
- Declares endpoints:
  - `/api/auth/register/` -> `RegisterView`
  - `/api/auth/login/` -> `LoginView`
  - `/api/kb/query/` -> `KBQueryView`
  - `/api/admin/usage-summary/` -> `AdminUsageSummaryView`

### 4. `api/models.py`
- **`Company`**: Linked to `User` via `OneToOneField`. Fields: `company_name`, `api_key` (`unique=True`), `role` (`Role.choices`), `created_at`.
- **`KBEntry`**: Fields: `question`, `answer`, `category` (`Category.choices`), `created_at`.
- **`QueryLog`**: Fields: `company` (`ForeignKey`), `search_term`, `results_count`, `queried_at`.

### 5. `api/signals.py` & `api/apps.py`
- `@receiver(post_save, sender=User)` auto-creates `Company` with `secrets.token_urlsafe(32)`.
- Wired inside `ApiConfig.ready()` in `apps.py` to ensure safe, idempotent signal registration.

### 6. `api/permissions.py`
- `IsAdminUser` overrides `has_permission()`.
- Validates `request.user.company.role == Company.Role.ADMIN`.
- Rejects non-admin requests with `403 Forbidden`.

### 7. `api/serializers.py`
- `RegisterSerializer`: Validates uniqueness of `username`, enforces non-blank fields.
- `LoginSerializer`: Deserializes credentials.
- `KBQueryRequestSerializer`: Rejects empty or whitespace-only search strings.
- `KBEntrySerializer` & `UsageSummarySerializer`: Formats outbound JSON.

### 8. `api/views.py`
- `RegisterView`: Public (`authentication_classes = []`, `permission_classes = []`). Creates `User`, retrieves signal-generated company, updates `company_name`, returns JWT + credentials (`201 Created`).
- `LoginView`: Public. Validates credentials via `authenticate()`, returns JWT + company info (`200 OK`).
- `KBQueryView`: Protected. Extracts `request.user.company`, searches via `Q(question__icontains) | Q(answer__icontains)`, logs `QueryLog` inside `transaction.atomic()`, returns results (`200 OK`).
- `AdminUsageSummaryView`: Protected by `IsAdminUser`. Computes `aggregate(Count('id'))`, `distinct().count()`, and grouped `annotate(count=Count('id'))[:5]`.

### 9. `api/management/commands/seed_kb.py`
- Seeds 15+ curated technical entries across all 5 categories.
- Supports `--with-admin` flag to configure platform admin credentials.

---

## 14. Master Interview Question & Answer Bank (30+ Scenarios)

### General & Architecture

#### Q1: What is the architectural difference between authentication and authorization?
**Answer**: Authentication verifies identity (*"Who are you?"*), handled via JWT validation. Authorization verifies permissions (*"What are you allowed to do?"*), handled via `IsAdminUser`.

#### Q2: What is an Insecure Direct Object Reference (IDOR) vulnerability?
**Answer**: An IDOR occurs when an application exposes a reference to an internal object (e.g., `company_id`) and trusts client input without server-side validation. TeamBoard eliminates IDOR by resolving the tenant directly from the authenticated token via `request.user.company`.

#### Q3: Why is 12-Factor Factor III ("Config in Environment") critical for backend systems?
**Answer**: Storing configuration in environment variables keeps credentials out of version control and allows identical codebases to run in development, testing, staging, and production environments simply by changing environment variables.

---

### Python & Runtime

#### Q4: How does Python's memory manager clean up circular references?
**Answer**: Reference counting handles immediate deallocation when references hit zero. Circular references (where two objects point to each other) are detected and collected by Python's generational cyclic garbage collector, which tracks container objects in Gen 0, 1, and 2.

#### Q5: Why must API keys be generated using `secrets` rather than `random`?
**Answer**: The `random` module uses the Mersenne Twister PRNG, whose internal state can be deduced after observing 624 outputs. The `secrets` module accesses operating system CSPRNG system calls (`/dev/urandom` or `BCryptGenRandom`), providing unpredictable cryptographic entropy.

---

### Database & PostgreSQL

#### Q6: How does PostgreSQL MVCC handle updates?
**Answer**: PostgreSQL does not update rows in place. It marks the old row version expired by writing the current transaction ID to its `xmax`, and inserts a new row version with `xmin` equal to the transaction ID. Dead row versions are later collected by `VACUUM`.

#### Q7: What causes PostgreSQL table bloat, and how is it resolved?
**Answer**: Frequent updates and deletions generate dead tuples that consume disk pages. If the autovacuum daemon is misconfigured or cannot keep up, table files expand unnecessarily. Running `VACUUM` reclaims dead space for future rows; `VACUUM FULL` rewrites the table to shrink disk usage (requires an exclusive table lock).

#### Q8: When does PostgreSQL choose an Index Scan vs a Sequential Scan?
**Answer**: If a query filters for a small percentage of rows (e.g. < 5%), an Index Scan is faster. If the planner estimates that a large percentage of disk pages will need to be read anyway, a Sequential Scan is preferred because sequential disk I/O avoids random disk seek overhead.

---

### Django ORM

#### Q9: What is the exact difference between `select_related` and `prefetch_related`?
**Answer**:
- `select_related`: Performs a SQL `JOIN` in a single query. Used for single-valued relationships (`ForeignKey`, `OneToOneField`).
- `prefetch_related`: Performs separate queries using `WHERE id IN (...)` and joins records in Python memory. Used for multi-valued relationships (`ManyToManyField`, reverse `ForeignKey`).

#### Q10: What does `QueryLog.objects.values('search_term').annotate(count=Count('id'))` compile to in SQL?
**Answer**:
```sql
SELECT search_term, COUNT(id) AS count
FROM api_querylog
GROUP BY search_term;
```

#### Q11: What is the difference between `F` expressions and standard Python variable updates?
**Answer**: Standard updates read a value into Python memory, modify it, and write it back, introducing race conditions in concurrent requests. An `F` expression generates SQL that updates the column directly in the database (`SET count = count + 1`), avoiding memory round-trips and race conditions.

---

### Transactions & Concurrency

#### Q12: How do nested `transaction.atomic()` blocks work in Django?
**Answer**: Because PostgreSQL does not support nested `BEGIN` statements, Django creates a SQL transaction on the outermost block and generates **SQL Savepoints** (`SAVEPOINT svpt_name`) for each inner block.

#### Q13: What is the difference between a Phantom Read and a Non-Repeatable Read?
**Answer**:
- **Non-Repeatable Read**: Transaction A reads a row, Transaction B updates that row and commits, and Transaction A reads it again, observing altered values.
- **Phantom Read**: Transaction A queries rows matching a filter, Transaction B inserts a new row matching that filter and commits, and Transaction A re-runs the query, observing a new "phantom" row.

---

### Django Signals

#### Q14: Why is `created` checked in `post_save` rather than inspecting `instance._state.adding`?
**Answer**: `instance._state.adding` is set to `True` during object instantiation to indicate an `INSERT` is needed. Once `Model.save_base()` successfully executes the SQL `INSERT`, it sets `created = True` for the `post_save` signal before resetting `_state.adding = False`. Therefore, `created` is the canonical argument signaling row creation in `post_save`.

#### Q15: Why does `bulk_create()` fail to trigger `post_save` signals?
**Answer**: `bulk_create()` executes an optimized multi-row SQL `INSERT` statement for efficiency. To preserve throughput and avoid instantiating hundreds of thousands of model instances, Django bypasses `Model.save()` and does not dispatch model signals.

---

### DRF & API Architecture

#### Q16: What is the difference between HTTP 401 Unauthorized and HTTP 403 Forbidden?
**Answer**:
- **401 Unauthorized**: Authentication failure. The request lacks valid credentials.
- **403 Forbidden**: Authorization failure. The user is authenticated, but their role/permissions do not grant access to the resource.

#### Q17: Why should API search endpoints return HTTP 200 with `[]` instead of HTTP 404 when no records match?
**Answer**: HTTP 404 denotes that the endpoint or resource does not exist. An empty search result is a valid and successful execution of the search operation that returned zero items. Returning 200 with `{"count": 0, "results": []}` provides predictable contract semantics for client applications.

#### Q18: How do serializers prevent mass-assignment vulnerabilities?
**Answer**: Serializers explicitly define writeable fields. Any extraneous fields submitted in client payloads that are not declared in the serializer are ignored or rejected during deserialization.

---

### Full-Stack & System Design

#### Q19: What is the Cache-Aside pattern, and how would it apply to TeamBoard?
**Answer**: The application checks Redis for cached query results (`kb:query:<hash>`). If found (cache hit), the cached data is returned immediately. If missing (cache miss), the database is queried, the response is written to Redis with a TTL, and then returned to the user.

#### Q20: How would you prevent usage logging from degrading search response latency under high traffic?
**Answer**: Decouple query logging by publishing an audit event to a message broker (Kafka / RabbitMQ / AWS SQS) asynchronously. An asynchronous consumer service ingests and batches logs into an analytical database (e.g. ClickHouse), keeping search query response times minimal.

---

### Final Preparation Checklist

- [x] **Architecture**: Mastered B2B tenancy and IDOR prevention via `request.user.company`.
- [x] **Python Runtime**: Understood bytecode, GIL, memory management, and CSPRNG.
- [x] **PostgreSQL**: Understood process architecture, MVCC, WAL, connection pooling, and B-Tree/GIN indexing.
- [x] **Docker**: Understood kernel virtualization, named volumes, port forwarding, and container networking.
- [x] **Django Core**: Mastered WSGI/ASGI, middleware execution, 12-Factor config, and AppConfig lifecycle.
- [x] **Django ORM**: Mastered lazy evaluation, `select_related` vs `prefetch_related`, `Q` objects, and `GROUP BY` aggregations.
- [x] **Transactions**: Understood ACID properties, `transaction.atomic()`, savepoints, and isolation levels.
- [x] **Signals**: Understood observer pattern, `created` flag semantics, and rollback desynchronization.
- [x] **DRF**: Mastered APIView lifecycle, serializer validation, mass-assignment defense, and RBAC permissions.
- [x] **Security**: Mastered JWT structure, symmetric vs asymmetric signing, token blacklisting, and secret hygiene.
- [x] **System Design**: Prepared to discuss Redis caching, database read-replicas, and asynchronous Kafka log streaming.
