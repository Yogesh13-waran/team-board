# TeamBoard: The Complete Backend & System Design Interview Master Guide

> **Target Audience**: Backend Engineers, Full-Stack Engineers, Tech Leads, and Software Architects preparing for technical interviews or seeking deep mastery of Django, Django REST Framework, PostgreSQL, Docker, System Design, and Enterprise API Security.

---

## Table of Contents

1. [System Context & The Problem Domain](#1-system-context--the-problem-domain)
2. [Python 3.14 & Web Runtime Architecture](#2-python-314--web-runtime-architecture)
3. [PostgreSQL & Docker Container Internals](#3-postgresql--docker-container-internals)
4. [Django Framework & Request Lifecycle](#4-django-framework--request-lifecycle)
5. [Django ORM Deep Dive: SQL Compilation & Query Optimization](#5-django-orm-deep-dive-sql-compilation--query-optimization)
6. [Database Transactions & ACID Guarantees](#6-database-transactions--acid-guarantees)
7. [Django Signals: Mechanism, Benefits & Anti-Patterns](#7-django-signals-mechanism-benefits--anti-patterns)
8. [Django REST Framework (DRF) Pipeline](#8-django-rest-framework-drf-pipeline)
9. [Authentication & Cryptography: JWT vs API Keys](#9-authentication--cryptography-jwt-vs-api-keys)
10. [Step-by-Step Code Analysis (File-by-File Breakdown)](#10-step-by-step-code-analysis-file-by-file-breakdown)
11. [Master Interview Question & Answer Bank (25+ Scenarios)](#11-master-interview-question--answer-bank-25-scenarios)

---

## 1. System Context & The Problem Domain

### The TeamBoard Scenario
TeamBoard provides an **AI-powered Knowledge Base as a B2B API service**.
- **Customers**: B2B client companies (e.g. Acme Corp, Beta LLC).
- **Integration**: Customers embed TeamBoard's search API directly into their internal developer portals, helpdesks, and customer chatbots.
- **Value Proposition**: Fast, curated technical Q&A across common engineering topics (APIs, databases, cloud, frameworks, architecture).

```
+-----------------------------------------------------------------------------------+
|                                  CLIENT SYSTEM                                    |
|   (Customer Helpdesk / Developer Portal / Slack Bot / Onboarding Tool)             |
+-----------------------------------------------------------------------------------+
                                         │
                        HTTPS + Bearer <JWT Token>
                        POST /api/kb/query/ {"search": "select_related"}
                                         ▼
+-----------------------------------------------------------------------------------+
|                              TEAMBOARD BACKEND                                    |
|                                                                                   |
|  1. Authenticate Request via SimpleJWT (Validates Signature against SECRET_KEY)   |
|  2. Resolve Tenant Identity from request.user.company (Prevents IDOR Spoofing)    |
|  3. Run atomic transaction:                                                       |
|     - Case-insensitive search: Q(question__icontains) | Q(answer__icontains)      |
|     - Usage Metering: QueryLog.objects.create(company, search_term, results_count)|
|  4. Return Results: {"search": "...", "count": 2, "results": [...]}               |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
|                         POSTGRESQL 16 (DOCKER CONTAINER)                          |
|   - api_company  (Tenant identity & API key)                                      |
|   - api_kbentry  (Curated Q&A data)                                               |
|   - api_querylog (Immutable audit trail for usage billing & admin analytics)      |
+-----------------------------------------------------------------------------------+
```

### Why Can't Companies Send Their Company ID in the Request Body?
*Interview Question: "Why shouldn't you allow a multi-tenant client to specify tenant_id or company_id in the request body?"*

**The Vulnerability: Insecure Direct Object Reference (IDOR) & Identity Spoofing**
If the API endpoint accepted:
```json
{
  "company_id": 42,
  "search": "how to use select_related"
}
```
Any malicious client or compromised developer key could send `company_id: 1` (a competitor's ID). This would:
1. Impersonate the competitor.
2. Incur billing costs on the competitor's account.
3. Poison the competitor's analytics.
4. Potentially access private data or quota allowances.

**The Solution: Cryptographic Identity Binding**
The client must authenticate using a credential issued by the server:
- The server verifies the token signature (`Bearer <JWT>`).
- The user identity is extracted from the cryptographic payload (`user_id`).
- The company is resolved via the trusted database relation: `request.user.company`.
- The client has zero ability to tamper with or forge this identity.

---

## 2. Python 3.14 & Web Runtime Architecture

### WSGI vs ASGI (PEP 3333 vs Asynchronous Specification)

```
             WSGI ARCHITECTURE (Synchronous)
             --------------------------------
             Request ──► [Worker Thread 1] ──► Block on DB Query ──► Response
             Request ──► [Worker Thread 2] ──► Block on I/O      ──► Response
             (Worker count limits concurrent concurrency: 2-4 workers x CPU cores)

             ASGI ARCHITECTURE (Asynchronous)
             --------------------------------
             Request 1 ──┐
             Request 2 ──┼──► [Asyncio Event Loop] ──► Non-blocking I/O (await)
             Request 3 ──┘   (Handles thousands of concurrent idle/I/O connections)
```

| Dimension | WSGI (`wsgi.py`) | ASGI (`asgi.py`) |
| :--- | :--- | :--- |
| **Specification** | PEP 3333 (Synchronous) | ASGI Specification (Asynchronous) |
| **Execution Model** | Thread/Process per connection | Single-threaded Event Loop (`asyncio`) |
| **Standard Servers** | Gunicorn, uWSGI, Apache mod_wsgi | Uvicorn, Daphne, Hypercorn |
| **Best For** | Standard CPU/database REST APIs | WebSockets, Long-Polling, Server-Sent Events (SSE), Streaming LLM output |
| **TeamBoard Choice** | WSGI / standard DRF sync handlers | Ready in `teamboard/asgi.py` for future streaming |

---

## 3. PostgreSQL & Docker Container Internals

### Container Architecture & Volumes

```
+---------------------------------------------------------------------------+
|                              DOCKER HOST                                  |
|                                                                           |
|   Host Port: 5432                                                         |
|         │                                                                 |
|         ▼ (Port Binding)                                                  |
|   +──────────────────────────────────+                                    |
|   | Container: teamboard_postgres    |                                    |
|   | Image: postgres:16-alpine        |                                    |
|   | Container Port: 5432             |                                    |
|   |                                  |                                    |
|   | Storage: /var/lib/postgresql/data|                                    |
|   +─────────────────┬────────────────+                                    |
|                     │                                                     |
|                     ▼ (Docker Named Volume)                               |
|   +──────────────────────────────────+                                    |
|   | Volume: postgres_data            | ◄── Survives container restarts     |
|   | Persists tables, WAL, indexes    |     and image upgrades!            |
|   +──────────────────────────────────+                                    |
+---------------------------------------------------------------------------+
```

### Docker Volume Persistence vs Ephemeral Containers
*Interview Question: "What happens to the database if the PostgreSQL container is stopped or removed?"*
- Containers are **ephemeral** by default: any file written to the container's writable layer is erased when the container is deleted (`docker rm`).
- By mounting a Docker **named volume** (`postgres_data:/var/lib/postgresql/data`), database files, Write-Ahead Logs (WAL), and indexes reside on the host filesystem managed by the Docker storage driver.
- Running `docker compose down` stops and deletes the container, but leaves `postgres_data` intact. Running `docker compose up -d` attaches the new container to the existing volume with zero data loss.

### PostgreSQL Process Architecture & Connection Pooling
- PostgreSQL uses a **process-based model** (not multi-threaded). For every incoming TCP client connection, the Postgres postmaster process calls `fork()` to create a dedicated backend worker process.
- Each worker process consumes 5-10 MB of RAM plus query work memory (`work_mem`).
- **Connection Spikes**: If 1,000 clients connect simultaneously, Postgres attempts to fork 1,000 processes, leading to context-switching degradation and memory exhaustion.
- **Production Solution**: A connection pooler such as **PgBouncer** is placed in front of PostgreSQL. PgBouncer maintains a pool of e.g. 50 persistent connections to PostgreSQL and serves thousands of client requests in `transaction` pooling mode.

---

## 4. Django Framework & Request Lifecycle

### The Complete Request-to-Response Pipeline

```
1. HTTP Request arrives from Client (e.g. Postman, Frontend)
   │
2. Web Server (Nginx) terminates TLS and forwards to WSGI Server (Gunicorn)
   │
3. Gunicorn invokes WSGI Handler -> Django BaseHandler
   │
4. Middleware Pipeline (Executed in top-to-bottom order):
   ├─► SecurityMiddleware (SSL redirects, HSTS, X-Content-Type-Options)
   ├─► SessionMiddleware (Reads session cookie if used)
   ├─► CommonMiddleware (APPEND_SLASH normalization, User-Agent filtering)
   ├─► CsrfViewMiddleware (CSRF token verification for unsafe HTTP verbs)
   ├─► AuthenticationMiddleware (Attaches LazyUser to request.user)
   └─► MessageMiddleware / XFrameOptionsMiddleware
   │
5. URL Routing (ROOT_URLCONF -> teamboard/urls.py -> api/urls.py)
   - Matches regex/path to target View class (e.g. KBQueryView.as_view())
   │
6. Django REST Framework APIView.dispatch():
   ├─► initialize_request(): Wraps Django HttpRequest into DRF Request
   ├─► perform_authentication(): Evaluates DEFAULT_AUTHENTICATION_CLASSES (SimpleJWT)
   │   - Extracts 'Bearer <token>' from HTTP_AUTHORIZATION
   │   - Validates signature, expiration, and loads User instance
   ├─► check_permissions(): Evaluates DEFAULT_PERMISSION_CLASSES
   │   - Runs IsAuthenticated / Custom IsAdminUser
   │   - Raises 401 if unauthenticated, 403 if permission denied
   ├─► check_throttles(): Checks rate limits (if configured)
   │
7. View Handler Execution (e.g. KBQueryView.post()):
   ├─► Serializer Validation: serializer.is_valid(raise_exception=True)
   ├─► Business Logic: Database query + QueryLog within transaction.atomic()
   └─► Returns DRF Response(data, status=200)
   │
8. Response Pipeline:
   ├─► Content Negotiation & Renderer: JSONRenderer converts dict to JSON bytes
   ├─► Middleware Pipeline executed in reverse order (bottom-to-top)
   └─► WSGI server returns HTTP 200 payload to client
```

---

## 5. Django ORM Deep Dive: SQL Compilation & Query Optimization

### 1. Lazy Evaluation: When Does Django ORM Hit the Database?
*Interview Question: "Does `entries = KBEntry.objects.filter(category='api')` execute a SQL query?"*
**Answer**: **NO.** Django QuerySets are lazy. Creating a QuerySet involves zero database activity.
Django only executes the SQL query when the QuerySet is **evaluated**:
1. **Iteration**: `for entry in entries:`
2. **Slicing with step**: `entries[0:10:2]`
3. **Pickling / Caching**: Saving to cache.
4. **repr() or str()**: Printing in console.
5. **len()**: `len(entries)` (Loads all rows into memory!).
6. **list()**: `list(entries)` (Explicit list coercion).
7. **bool()**: `if entries:` (Executes query; use `entries.exists()` instead for performance).

### 2. Solving the N+1 Query Problem: `select_related` vs `prefetch_related`

| Feature | `select_related` | `prefetch_related` |
| :--- | :--- | :--- |
| **Relationship Type** | Single-valued (`ForeignKey`, `OneToOneField`) | Multi-valued (`ManyToManyField`, reverse `ForeignKey`) |
| **SQL Strategy** | Single SQL query using **SQL JOIN** (INNER / LEFT JOIN) | Multiple SQL queries using **WHERE IN (...)** |
| **Where Join Occurs**| In the **Database Engine** | In **Python memory** |
| **Example** | `QueryLog.objects.select_related('company')` | `Company.objects.prefetch_related('query_logs')` |

```sql
-- select_related('company') generates:
SELECT api_querylog.id, api_querylog.search_term, api_company.company_name
FROM api_querylog
INNER JOIN api_company ON (api_querylog.company_id = api_company.id);

-- prefetch_related('query_logs') generates:
-- Query 1:
SELECT id, company_name FROM api_company;
-- Query 2:
SELECT id, company_id, search_term FROM api_querylog WHERE company_id IN (1, 2, 3...);
```

### 3. Q Objects: Logical OR & NOT Queries
Standard Django filter kwargs are always joined via SQL `AND`:
```python
# Generates: WHERE question ILIKE '%term%' AND answer ILIKE '%term%'
KBEntry.objects.filter(question__icontains=term, answer__icontains=term)
```
To implement a logical `OR`, Django provides `django.db.models.Q` objects:
```python
from django.db.models import Q

# Generates: WHERE question ILIKE '%term%' OR answer ILIKE '%term%'
query = Q(question__icontains=term) | Q(answer__icontains=term)
KBEntry.objects.filter(query)
```
- Bitwise operators:
  - `|`: SQL `OR`
  - `&`: SQL `AND`
  - `~`: SQL `NOT` (e.g. `~Q(category='general')` -> `WHERE NOT (category = 'general')`)

### 4. Database Aggregations: `aggregate()` vs `annotate()`

#### `aggregate()` (Scalar Reduction across Entire Table)
Computes a summary over the entire QuerySet. Returns a Python dictionary.
```python
from django.db.models import Count

QueryLog.objects.aggregate(total=Count('id'))
# Returns: {'total': 284}
```
**Compiled SQL**:
```sql
SELECT COUNT(api_querylog.id) AS total FROM api_querylog;
```

#### `annotate()` (Per-Group Calculation / SQL `GROUP BY`)
Attaches calculated values to each item in a grouped QuerySet.
```python
# Group by search_term, count occurrences, sort descending, limit 5
top_terms = (
    QueryLog.objects.values('search_term')
    .annotate(count=Count('id'))
    .order_by('-count')[:5]
)
```
**Compiled SQL**:
```sql
SELECT api_querylog.search_term, COUNT(api_querylog.id) AS count
FROM api_querylog
GROUP BY api_querylog.search_term
ORDER BY count DESC
LIMIT 5;
```

---

## 6. Database Transactions & ACID Guarantees

### What is ACID?
1. **Atomicity**: All operations in a block succeed, or none do ("All or Nothing").
2. **Consistency**: The database moves from one valid state to another, preserving constraints (`UNIQUE`, `FOREIGN KEY`, `CHECK`).
3. **Isolation**: Concurrent transactions cannot view uncommitted partial states of other transactions.
4. **Durability**: Once committed, changes are written to non-volatile storage (WAL) and survive system crashes.

### How `transaction.atomic()` Works in Django

```
                  with transaction.atomic():
                             │
                             ▼
                    Database: BEGIN;
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
   Search KB Entries                Insert QueryLog Row
   (Read Operation)                 (Write Operation)
            │                                 │
            └────────────────┬────────────────┘
                             │
             Did any Exception occur?
             ├── YES ──► Database: ROLLBACK; (Nothing persists!)
             └── NO  ──► Database: COMMIT;   (Both committed permanently!)
```

#### Nested Transactions & Savepoints
When nesting `transaction.atomic()` blocks, Django does NOT open multiple SQL transactions (PostgreSQL does not support nested `BEGIN`). Instead, Django uses **SQL Savepoints**:
```sql
BEGIN; -- Outer atomic block
  INSERT INTO api_querylog ...;
  SAVEPOINT s1; -- Inner atomic block starts
    UPDATE api_company ...;
    -- If error occurs inside inner block:
    ROLLBACK TO SAVEPOINT s1;
    RELEASE SAVEPOINT s1;
COMMIT; -- Outer transaction finishes
```

### The 4 ANSI SQL Isolation Levels

| Isolation Level | Dirty Reads | Non-Repeatable Reads | Phantom Reads | PostgreSQL Support |
| :--- | :---: | :---: | :---: | :--- |
| **Read Uncommitted** | Possible | Possible | Possible | Treated as Read Committed in Postgres |
| **Read Committed** *(Default)* | Prevented | Possible | Possible | Default in PostgreSQL & Django |
| **Repeatable Read** | Prevented | Prevented | Prevented (in Postgres MVCC) | Fully Supported |
| **Serializable** | Prevented | Prevented | Prevented | Uses SSI (Serializable Snapshot Isolation) |

- **Dirty Read**: Transaction A reads uncommitted changes from Transaction B. If B rolls back, A acted on bogus data.
- **Non-Repeatable Read**: Transaction A reads a row twice. In between, Transaction B updates that row and commits. A sees two different values.
- **Phantom Read**: Transaction A queries rows matching a range. Transaction B inserts a new row matching that range and commits. A queries again and sees a "phantom" row.

---

## 7. Django Signals: Mechanism, Benefits & Anti-Patterns

### What is the Django Signal Dispatcher?
Django's signals implement the **Observer (Publish-Subscribe) design pattern**.
- **Sender**: An object that announces an event (e.g. `User` model).
- **Signal**: The notification channel (`post_save`, `pre_save`, `post_delete`).
- **Receiver**: The callback function decorated with `@receiver`.

### How `post_save` Detects First Creation: `created` vs `instance._state.adding`

```python
@receiver(post_save, sender=User)
def create_company_profile(sender, instance, created, **kwargs):
    if created:
        Company.objects.create(
            user=instance,
            company_name=instance.email,
            api_key=secrets.token_urlsafe(32)
        )
```

**Under the Hood in Django's `Model.save_base()`**:
1. When a model instance is instantiated in Python (`user = User(...)`), Django initializes `instance._state.adding = True`.
2. When `save()` is executed:
   - If `self._state.adding is True`: Django executes a SQL `INSERT`.
   - If `self._state.adding is False`: Django executes a SQL `UPDATE`.
3. After the SQL `INSERT` completes successfully, Django dispatches the `post_save` signal with argument `created = True`.
4. Django then updates `instance._state.adding = False`.
5. Therefore, checking `if created:` in `post_save` is the canonical, reliable way to know this row was newly inserted into the database.

### Signal Wiring & `AppConfig.ready()`
*Interview Question: "Why should you never import signals at the root of `models.py` or `__init__.py`?"*
- **The Pitfall**: Importing signals prematurely causes circular imports or triggers `AppRegistryNotReady` because Django has not yet finished loading all model classes into memory.
- **The Correct Pattern**: Connect signals inside `AppConfig.ready()` in `apps.py`:
  ```python
  class ApiConfig(AppConfig):
      default_auto_field = 'django.db.models.BigAutoField'
      name = 'api'

      def ready(self):
          import api.signals  # noqa: F401
  ```
  Django guarantees `ready()` is only invoked after the complete app registry is populated.

### Signals Anti-Patterns & When to Avoid Them
1. **Hidden Side Effects**: Signals obscure control flow. A developer saving a User model may not realize 5 different background tasks, external webhooks, or profile records were triggered.
2. **Transaction Rollback Issues**: If a signal executes a non-database side effect (e.g. sending an email or charging a credit card) and the parent transaction fails and rolls back, the email was still sent!
   - *Fix*: Use `transaction.on_commit(callback)` to defer execution until the database transaction is guaranteed committed.

---

## 8. Django REST Framework (DRF) Pipeline

### DRF Serializer Lifecycle & Security Boundaries
Serializers perform two essential roles:
1. **Deserialization & Validation**:
   - `to_internal_value(data)` -> validates types and constraints.
   - `validate_<field>(value)` -> field-specific custom logic.
   - `validate(attrs)` -> cross-field validation.
   - Populates `.validated_data` or `.errors`.
2. **Mass Assignment Prevention**:
   - Attackers frequently inject unexpected fields (e.g. `{"role": "admin", "is_superuser": true}`).
   - By explicitly declaring allowed serializer fields, unauthorized keys are ignored or rejected, preventing privilege escalation.

### Authentication vs Permission in DRF

```
                           Incoming HTTP Request
                                     │
                                     ▼
                      [DRF Authentication Pipeline]
             Iterates over `DEFAULT_AUTHENTICATION_CLASSES`
                                     │
                        Is a valid token present?
                        ├── NO  ──► request.user = AnonymousUser
                        └── YES ──► request.user = User(username='acmecorp')
                                     │
                                     ▼
                       [DRF Permission Pipeline]
               Iterates over `permission_classes` list
                                     │
                     Calls permission.has_permission()
                                     │
                 Did ANY permission class return False?
                 ├── YES ──► Is request.user authenticated?
                 │            ├── NO  ──► Return HTTP 401 Unauthorized
                 │            └── YES ──► Return HTTP 403 Forbidden
                 │
                 └── NO  ──► Proceed to View Handler (post / get)
```

- **401 Unauthorized**: *"Who are you?"* (Missing, expired, or invalid credentials).
- **403 Forbidden**: *"I know who you are, but you do not have permission to access this resource."*

---

## 9. Authentication & Cryptography: JWT vs API Keys

### Anatomy of a JSON Web Token (JWT)

A JWT is a string formatted as: `Header.Payload.Signature`

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY...k0OTIsInVzZXJfaWQiOjF9.e8J4x9...
 └─────────────┬────────────────────┘ └──────────────────────┬──────────────────────┘ └───────────┬───────────┘
               │                                             │                                     │
           1. HEADER                                     2. PAYLOAD                            3. SIGNATURE
     {"alg": "HS256",                              {"token_type": "access",              HMACSHA256(
      "typ": "JWT"}                                 "exp": 1762097249,                     base64UrlEncode(header) + "." +
                                                    "user_id": 42}                         base64UrlEncode(payload),
                                                                                           SECRET_KEY)
```

1. **Header**: Declares algorithm (`HS256`) and token type (`JWT`).
2. **Payload**: Contains claims (`user_id`, `exp` expiration timestamp). Note: Payload is Base64URL-encoded, NOT encrypted! Anyone can decode and read it. Never put passwords or API secrets in a JWT payload.
3. **Signature**: Computed by signing `Header + "." + Payload` with the server's private `SECRET_KEY`.
   - If a malicious client modifies `user_id: 42` to `user_id: 1` in the payload, the computed signature will no longer match the token signature. The server immediately rejects it!

### Symmetric (HS256) vs Asymmetric (RS256) Signing

| Feature | HS256 (HMAC with SHA-256) | RS256 (RSA Signature with SHA-256) |
| :--- | :--- | :--- |
| **Key Type** | Single Shared Secret (`SECRET_KEY`) | Asymmetric Key Pair (Private + Public Key) |
| **Signing** | Done with `SECRET_KEY` | Done with **Private Key** (Auth Service only) |
| **Verification** | Requires `SECRET_KEY` | Done with **Public Key** (Any microservice can verify!) |
| **Best For** | Monolithic backends, single services | Distributed microservices, OAuth2 / OIDC providers |

### Cryptographic Security: `secrets` vs `random` in Python
*Interview Question: "Why must you use `secrets.token_urlsafe()` instead of `random.choice()` for generating API keys?"*
- `random` module uses the **Mersenne Twister algorithm**, which is a pseudo-random number generator (PRNG). If an attacker observes 624 outputs from a Mersenne Twister, they can reconstruct its internal state and predict every future "random" key!
- `secrets` module uses the Operating System's **CSPRNG** (Cryptographically Secure Pseudo-Random Number Generator):
  - Linux/macOS: `/dev/urandom` / `getrandom()` system call (hardware noise, interrupt timings).
  - Windows: `BCryptGenRandom` / `CryptGenRandom`.
- Generates true cryptographic entropy that cannot be reverse-engineered or predicted.

---

## 10. Step-by-Step Code Analysis (File-by-File Breakdown)

### 1. `api/models.py`
- **`Company`**:
  - `user`: `OneToOneField(User, on_delete=models.CASCADE, related_name='company')` -> Maps 1:1 to Django's built-in auth user.
  - `company_name`: Tenant's legal company name.
  - `api_key`: `max_length=64, unique=True, blank=True` -> Indexed with B-Tree unique index.
  - `role`: `choices=Role.choices, default=Role.CLIENT` -> Enforces RBAC (`admin` vs `client`).
- **`KBEntry`**:
  - `question` & `answer`: Curated knowledge text.
  - `category`: Choices (`api`, `database`, `cloud`, `framework`, `general`).
- **`QueryLog`**:
  - `company`: `ForeignKey(Company, on_delete=models.CASCADE, related_name='query_logs')`
  - `search_term`: String search query.
  - `results_count`: Number of matched records.
  - `queried_at`: `auto_now_add=True`.

### 2. `api/signals.py` & `api/apps.py`
- Receiver decorated with `@receiver(post_save, sender=User)`.
- When `created` is `True`, executes `Company.objects.create(user=instance, company_name=instance.email, api_key=secrets.token_urlsafe(32))`.
- Wired in `api/apps.py` under `def ready(self): import api.signals`.

### 3. `api/permissions.py`
- `IsAdminUser` subclasses `rest_framework.permissions.BasePermission`.
- Checks:
  ```python
  return (
      request.user and
      request.user.is_authenticated and
      hasattr(request.user, 'company') and
      request.user.company.role == Company.Role.ADMIN
  )
  ```
- Does NOT check `is_staff` or `is_superuser`, adhering strictly to domain-level tenant roles.

### 4. `api/views.py`
- **`RegisterView`**:
  - `authentication_classes = []`, `permission_classes = []` (Public).
  - Creates user -> signal creates company -> updates company name -> returns JWT token + API key with 201 Created.
- **`LoginView`**:
  - `authentication_classes = []`, `permission_classes = []` (Public).
  - Validates credentials using `authenticate(username, password)` -> returns JWT token + company credentials with 200 OK.
  - Returns 401 on bad credentials.
- **`KBQueryView`**:
  - Protected by default JWT authentication.
  - Extracts tenant from `request.user.company`.
  - Searches with `Q(question__icontains=term) | Q(answer__icontains=term)`.
  - Atomically writes `QueryLog` inside `with transaction.atomic():`.
  - Returns 200 with search term, count, and results list (even if count is 0).
- **`AdminUsageSummaryView`**:
  - Protected with `permission_classes = [IsAdminUser]`.
  - Aggregates `total_queries` via `QueryLog.objects.aggregate(total=Count('id'))`.
  - Computes `active_companies` via `QueryLog.objects.values('company').distinct().count()`.
  - Computes `top_search_terms` via `QueryLog.objects.values('search_term').annotate(count=Count('id')).order_by('-count')[:5]`.

---

## 11. Master Interview Question & Answer Bank (25+ Scenarios)

### Core Framework & Design

#### Q1: What is the difference between Django authentication and Django authorization?
**Answer**:
- **Authentication**: Verifying *who the user is* (identity). In TeamBoard, this is handled by SimpleJWT verifying the signed token and extracting the `user_id`.
- **Authorization**: Verifying *what the authenticated user is allowed to do* (permissions). In TeamBoard, this is handled by `IsAdminUser` checking `request.user.company.role == 'admin'`.

#### Q2: What is the purpose of `related_name` on a ForeignKey or OneToOneField?
**Answer**:
`related_name` defines the attribute name used for reverse relation lookups from the target model back to the source model.
- On `Company.user`: `related_name='company'` allows accessing `user.company` directly instead of the default `user.company_set.first()`.
- On `QueryLog.company`: `related_name='query_logs'` allows accessing `company.query_logs.all()` instead of `company.querylog_set.all()`.

#### Q3: Why should credentials never be hardcoded in `settings.py`?
**Answer**:
Hardcoded credentials violate Factor III of the **12-Factor App methodology** ("Store config in the environment").
1. **Security Risk**: If code is committed to Git, credentials leak into commit history, exposing databases to attackers.
2. **Environment Portability**: Development, staging, and production environments require different databases and keys without changing code.
3. We use `python-dotenv` to inject `.env` variables at runtime.

---

### Database & ORM

#### Q4: How does `__icontains` differ from `__contains` in Django ORM?
**Answer**:
- `__contains`: Case-sensitive match. In PostgreSQL, compiles to `WHERE column LIKE '%term%'` (or `LIKE BINARY`).
- `__icontains`: Case-insensitive match. In PostgreSQL, compiles to `WHERE column ILIKE '%term%'`.

#### Q5: What is the performance danger of `ILIKE '%term%'` on large tables, and how do you optimize it?
**Answer**:
Standard B-Tree indexes cannot be used for queries starting with a wildcard (`%term%`), forcing PostgreSQL to perform an expensive **Sequential Scan (Full Table Scan)** across every disk page.
**Optimization**:
1. Use **Trigram Indexes** (`pg_trgm` extension in PostgreSQL with a `GIN` or `GiST` index):
   ```sql
   CREATE EXTENSION pg_trgm;
   CREATE INDEX kb_question_trgm_idx ON api_kbentry USING gin (question gin_trgm_ops);
   ```
2. Or use **Full-Text Search** with PostgreSQL's native `tsvector` and `tsquery` data types and `GIN` indexes.

#### Q6: Explain what `QueryLog.objects.values('search_term').annotate(count=Count('id'))` does under the hood.
**Answer**:
In Django ORM, when `.values()` is followed by `.annotate()`, the fields passed to `.values()` become the SQL `GROUP BY` clause.
Django compiles this into:
```sql
SELECT search_term, COUNT(id) AS count
FROM api_querylog
GROUP BY search_term;
```
This groups all query logs with identical search terms together and calculates the frequency count per term directly inside PostgreSQL's query engine.

#### Q7: Why do we use `list(KBEntry.objects.filter(query))` inside the atomic block before creating the QueryLog?
**Answer**:
Calling `list(...)` forces immediate evaluation of the QuerySet within the database transaction, locking in the matched records and fetching their length `len(...)`. Passing the count directly to `QueryLog.objects.create()` ensures both the query execution and the audit row logging take place in the exact same transaction boundary.

---

### Transactions & Concurrency

#### Q8: What happens if an unhandled Python exception occurs inside `with transaction.atomic():`?
**Answer**:
Django's atomic context manager intercepts the exception. It issues a SQL `ROLLBACK` (or `ROLLBACK TO SAVEPOINT` if nested) to the database connection, undoing any insertions, updates, or deletions executed during that block, and then re-raises the exception up the call stack.

#### Q9: What is the difference between Optimistic and Pessimistic concurrency control?
**Answer**:
- **Pessimistic Concurrency**: Assumes conflicts will occur. Locks the row at read time using `SELECT ... FOR UPDATE` (`QuerySet.select_for_update()`). Other transactions must wait until the lock is released upon `COMMIT`.
- **Optimistic Concurrency**: Assumes conflicts are rare. Does not lock rows on read. Adds a `version` or `updated_at` column. On write:
  `UPDATE table SET balance = 50, version = version + 1 WHERE id = 1 AND version = 3;`
  If rows affected is 0, another transaction updated it first; the application retries or aborts.

---

### Security & API Architecture

#### Q10: Why did we set `authentication_classes = []` and `permission_classes = []` on Register and Login?
**Answer**:
In `settings.py`, we set global defaults:
```python
'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
```
Under this Zero Trust policy, every endpoint rejects unauthenticated requests by default. Because registration and login are the public entry points where unauthenticated clients must submit credentials to obtain a token, they must explicitly override and clear these two lists.

#### Q11: How do you invalidate or revoke a stateless JWT token before its expiration?
**Answer**:
Because stateless JWTs are self-contained and verified cryptographically without database lookups, they cannot be natively revoked before expiration.
**Standard Mitigation Strategies**:
1. **Short Access Token Lifetimes**: Make access tokens expire quickly (e.g. 5 to 15 minutes).
2. **Refresh Token Blacklisting**: Store the refresh token's unique identifier (`jti`) in a fast Redis cache upon logout. SimpleJWT provides `rest_framework_simplejwt.token_blacklist` for this.
3. **User Token Version / Epoch**: Add a `token_version` integer on the `User` model. Include `token_version` in the JWT payload. On password reset or logout, increment the user's `token_version`. Any incoming token with an older version is rejected.

#### Q12: Why should passwords always be configured with `write_only=True` in serializers?
**Answer**:
`write_only=True` ensures the password field is accepted during deserialization (parsing incoming client JSON), but is strictly excluded from serialization (formatting outgoing JSON responses). This prevents hashed or plain passwords from ever leaking into HTTP response bodies, logs, or network traces.

#### Q13: What is the difference between HTTP 400, 401, 403, and 404 in REST API design?
**Answer**:
- **400 Bad Request**: Malformed syntax, invalid JSON, or failing input validation (e.g. blank search term).
- **401 Unauthorized**: Missing, invalid, or expired authentication credentials (e.g. missing Bearer token).
- **403 Forbidden**: Authenticated, but lacking sufficient permissions (e.g. a regular `client` attempting to access `/api/admin/usage-summary/`).
- **404 Not Found**: The requested resource URL or model ID does not exist. Note: An empty search result is NOT a 404; it is a 200 OK with `results: []`.

---

### System Design & Scalability

#### Q14: How would you scale TeamBoard to handle 50,000 search queries per second?
**Answer**:
1. **Caching Layer (Redis / Memcached)**:
   - Popular search terms (e.g. "select_related") return identical answers.
   - Implement the **Cache-Aside pattern**: Check Redis for key `kb:search:<hash(search_term)>`. If hit, return in < 2ms.
2. **Read-Replicas for PostgreSQL**:
   - Route knowledge base reads to read-replicas using Django's database routers (`db_for_read`).
3. **Asynchronous Usage Logging (Kafka / Celery / SQS)**:
   - Writing `QueryLog` synchronously to PostgreSQL on every query creates a database write bottleneck.
   - Offload query logging: publish an event `{"company_id": 1, "term": "...", "count": 2}` to Apache Kafka or AWS SQS.
   - A stream processor (e.g. ClickHouse or TimescaleDB consumer) batches and ingests millions of audit logs without blocking the user-facing search API.
4. **Horizontal API Scaling**:
   - Run stateless Django Gunicorn containers behind an AWS Application Load Balancer (ALB) with auto-scaling based on CPU/Request count.

---

### Summary Checklist for Interview Candidates

- [x] Can explain the difference between `select_related` and `prefetch_related` and their generated SQL.
- [x] Can explain why `secrets.token_urlsafe(32)` is cryptographically secure vs `random`.
- [x] Can walk through the DRF Request lifecycle from Middleware down to Serializers.
- [x] Can explain why tenancy must be resolved from `request.user.company` and never from request bodies.
- [x] Can describe how `transaction.atomic()` provides ACID guarantees using SQL Savepoints.
- [x] Can describe how `instance._state.adding` and `created` work in Django signals.
- [x] Can write grouped aggregations using `.values('field').annotate(count=Count('id'))`.
- [x] Can explain the difference between 401 Unauthorized and 403 Forbidden.
