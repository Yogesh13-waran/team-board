"""
Management Command to Seed Knowledge Base (KBEntry) Records.

================================================================================
Usage:
    python manage.py seed_kb
    python manage.py seed_kb --with-admin
================================================================================
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import KBEntry, Company


KB_SEED_DATA = [
    {
        "category": KBEntry.Category.DATABASE,
        "question": "What is select_related in Django ORM?",
        "answer": (
            "select_related performs a SQL JOIN (usually INNER JOIN or LEFT OUTER JOIN) "
            "and fetches related single-object relationships (ForeignKey and OneToOneField) "
            "in the same SQL query. This prevents the classic N+1 query problem by caching "
            "the related objects in memory upon the initial query execution."
        )
    },
    {
        "category": KBEntry.Category.DATABASE,
        "question": "When should I use prefetch_related vs select_related?",
        "answer": (
            "Use select_related when traversing single-valued relationships (ForeignKey, OneToOneField) "
            "via SQL JOINs. Use prefetch_related when traversing multi-valued relationships "
            "(ManyToManyField, reverse ForeignKey) or GenericForeignKey. prefetch_related executes "
            "a separate SQL query per relationship using an IN clause and joins them in Python memory."
        )
    },
    {
        "category": KBEntry.Category.DATABASE,
        "question": "How does transaction.atomic() work in Django?",
        "answer": (
            "transaction.atomic() is a context manager and decorator providing ACID transaction "
            "guarantees. Inside an atomic block, database operations either all commit successfully "
            "or all roll back on exception. In nested atomic blocks, Django employs database "
            "SAVEPOINTs to allow partial rollbacks of inner blocks without aborting the outer transaction."
        )
    },
    {
        "category": KBEntry.Category.FRAMEWORK,
        "question": "When should I use Q objects in Django queries?",
        "answer": (
            "Q objects (django.db.models.Q) encapsulate SQL query conditions so they can be combined "
            "using bitwise logical operators: OR (|), AND (&), and NOT (~). Standard QuerySet filter() "
            "kwargs are always combined with AND. Q objects are essential for complex queries like "
            "case-insensitive keyword matching across multiple text columns (question OR answer)."
        )
    },
    {
        "category": KBEntry.Category.FRAMEWORK,
        "question": "How do Django signals work and when should you avoid them?",
        "answer": (
            "Django signals implement the Observer pattern, notifying registered receiver callbacks "
            "when actions occur (e.g. post_save on User). They decouple components but can introduce "
            "hidden side effects, implicit control flow, and performance overhead. Avoid signals for "
            "core business logic if direct method calls or overriding save() are cleaner and more explicit."
        )
    },
    {
        "category": KBEntry.Category.API,
        "question": "What is a JWT token and how does stateless authentication work?",
        "answer": (
            "A JSON Web Token (JWT) is a compact, URL-safe cryptographic token composed of three parts: "
            "Header, Payload, and Signature (encoded as header.payload.signature). Stateless authentication "
            "allows the backend to verify the user identity by validating the HMAC-SHA256 signature against "
            "its SECRET_KEY without querying a database or session store on every request."
        )
    },
    {
        "category": KBEntry.Category.API,
        "question": "How do REST API rate limiting and throttling protect backend services?",
        "answer": (
            "Rate limiting restricts the number of API requests a client can execute within a specified "
            "time window (e.g. 100 requests per minute). It protects backend servers from denial of service "
            "(DoS), resource starvation, brute-force credential stuffing, and ensures fair usage among "
            "multi-tenant B2B customers. Common algorithms include Token Bucket and Leaky Bucket."
        )
    },
    {
        "category": KBEntry.Category.API,
        "question": "What are HTTP idempotency and safe methods in API design?",
        "answer": (
            "A request method is safe if it does not alter server state (GET, HEAD, OPTIONS). "
            "A request method is idempotent if executing it multiple times produces the exact same "
            "server-side result as executing it once (GET, PUT, DELETE). POST is neither safe nor "
            "idempotent because repeated requests create duplicate resources."
        )
    },
    {
        "category": KBEntry.Category.DATABASE,
        "question": "What is an ACID transaction and what are the 4 isolation levels?",
        "answer": (
            "ACID stands for Atomicity (all-or-nothing), Consistency (rules preserved), Isolation "
            "(concurrent independence), and Durability (committed data persists). The standard ANSI SQL "
            "isolation levels are: Read Uncommitted (allows dirty reads), Read Committed (default in PostgreSQL), "
            "Repeatable Read (prevents non-repeatable reads), and Serializable (strict serial ordering)."
        )
    },
    {
        "category": KBEntry.Category.DATABASE,
        "question": "What is connection pooling in PostgreSQL and why is PgBouncer used?",
        "answer": (
            "PostgreSQL forks a separate operating system process for each client connection, which consumes "
            "RAM and CPU context-switching overhead. A connection pooler like PgBouncer maintains a warm "
            "pool of pre-established database connections, serving hundreds or thousands of client requests "
            "over a small set of persistent backend connections in transaction or session pooling mode."
        )
    },
    {
        "category": KBEntry.Category.CLOUD,
        "question": "How does Docker containerization differ from Virtual Machines?",
        "answer": (
            "Virtual Machines (VMs) virtualize physical hardware via a Hypervisor, running a full guest OS "
            "with its own kernel. Docker containers virtualize the operating system kernel, sharing the host "
            "Linux kernel via namespaces (isolation) and cgroups (resource limits). Containers are lightweight, "
            "start in milliseconds, and consume minimal memory compared to heavy VMs."
        )
    },
    {
        "category": KBEntry.Category.CLOUD,
        "question": "What are Kubernetes Pods, Deployments, and Services?",
        "answer": (
            "In Kubernetes, a Pod is the smallest deployable compute unit holding one or more containers. "
            "A Deployment manages declarative replicas, rolling updates, and self-healing for Pods. "
            "A Service provides a persistent IP address, DNS name, and load balancing across dynamic Pods."
        )
    },
    {
        "category": KBEntry.Category.GENERAL,
        "question": "How does Redis caching improve backend API throughput?",
        "answer": (
            "Redis is an in-memory key-value data structure store offering sub-millisecond read/write latencies. "
            "By caching frequently queried database records (cache-aside pattern), Redis drastically cuts down "
            "database load, reduces API response times, and prevents thundering herd issues under peak traffic."
        )
    },
    {
        "category": KBEntry.Category.GENERAL,
        "question": "What is the CAP theorem in distributed systems?",
        "answer": (
            "The CAP theorem states that any distributed data store can simultaneously guarantee at most two "
            "out of three properties during network failures: Consistency (every read receives the most recent "
            "write), Availability (every non-failing node returns a response), and Partition Tolerance "
            "(the system continues operating despite dropped or delayed network messages). Since networks "
            "cannot avoid partitions, systems must choose between CP and AP."
        )
    },
    {
        "category": KBEntry.Category.CLOUD,
        "question": "What is the difference between horizontal and vertical scaling?",
        "answer": (
            "Vertical scaling (scaling up) means adding more CPU, RAM, or storage to a single server instance. "
            "It has physical hardware ceilings and introduces a single point of failure. Horizontal scaling "
            "(scaling out) means adding more machine instances behind a load balancer, providing high availability, "
            "linear elasticity, and redundancy for cloud-native architectures."
        )
    }
]


class Command(BaseCommand):
    help = "Seeds initial Knowledge Base (KBEntry) records and optional default Admin user."

    def add_arguments(self, parser):
        parser.add_argument(
            '--with-admin',
            action='store_true',
            help='Also create a default platform admin user and company for testing.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding TeamBoard Knowledge Base entries..."))

        created_count = 0
        updated_count = 0

        for item in KB_SEED_DATA:
            entry, created = KBEntry.objects.get_or_create(
                question=item['question'],
                defaults={
                    'answer': item['answer'],
                    'category': item['category']
                }
            )
            if created:
                created_count += 1
            else:
                entry.answer = item['answer']
                entry.category = item['category']
                entry.save()
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded KB entries: {created_count} created, {updated_count} updated. "
                f"Total in DB: {KBEntry.objects.count()}."
            )
        )

        if options['with_admin']:
            admin_user, user_created = User.objects.get_or_create(
                username='teamboard_admin',
                defaults={
                    'email': 'admin@teamboard.internal',
                    'is_staff': True,
                }
            )
            if user_created:
                admin_user.set_password('adminpass123')
                admin_user.save()

            # Ensure company role is ADMIN
            company = admin_user.company
            company.company_name = "TeamBoard Admin Headquarters"
            company.role = Company.Role.ADMIN
            company.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Platform Admin ensured: username='teamboard_admin', role='{company.role}', "
                    f"api_key='{company.api_key}'"
                )
            )
