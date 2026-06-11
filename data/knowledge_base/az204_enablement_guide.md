# Engineering Certification Enablement Guide (Synthetic)

> SYNTHETIC demonstration content. Not affiliated with Microsoft certification material.
> Source ID: KB-AZ204-001

## Cloud Engineer track

- Primary certification: AZ-204 (Developing Solutions for Azure)
- Secondary certification: AZ-305

### AZ-204 skill areas and recommended study hours

| Skill area | Weight | Recommended hours |
|---|---|---|
| Develop Azure compute solutions (Functions, App Service) | 25% | 6 |
| Develop for Azure storage (Blob, Cosmos DB) | 20% | 5 |
| Implement Azure security (auth, Key Vault) | 20% | 5 |
| Monitor, troubleshoot, optimize | 15% | 3 |
| Connect to and consume services (API Management, event/message) | 20% | 5 |

Total recommended study: ~24 hours.

### Key concepts by skill area

These are the exam-relevant concepts a learner must understand for each skill
area. Practice questions should test this understanding (not the study-hour
figures above).

**Develop Azure compute solutions (Functions, App Service)**
- Azure Functions runs event-driven, serverless code that scales automatically; you pay only for execution time. The Consumption plan scales to zero when idle.
- Triggers start a function (HTTP, Timer, Queue, Blob, Event Grid); bindings connect inputs/outputs declaratively without boilerplate SDK code.
- Azure App Service hosts web apps and APIs as a managed PaaS; deployment slots allow zero-downtime releases and swap/rollback.

**Develop for Azure storage (Blob, Cosmos DB)**
- Azure Blob Storage holds unstructured objects across access tiers: Hot (frequent access), Cool (infrequent), and Archive (rarely accessed, cheapest, retrieval latency).
- Azure Cosmos DB is a globally distributed, multi-model NoSQL database with single-digit-millisecond latency; the partition key choice drives scalability and even data distribution.
- Cosmos DB offers five consistency levels from Strong to Eventual, trading latency and availability against consistency.

**Implement Azure security (auth, Key Vault)**
- Azure Key Vault stores secrets, keys, and certificates so they never live in code or config; apps read them at runtime.
- A managed identity lets an app authenticate to Azure services (including Key Vault) without storing any credential - Azure manages the identity.
- Microsoft Entra ID (formerly Azure AD) handles authentication; role-based access control (RBAC) grants least-privilege authorization via role assignments.

**Monitor, troubleshoot, optimize**
- Application Insights collects telemetry (requests, dependencies, exceptions, custom metrics) for diagnosing performance and failures.
- Azure Monitor centralizes metrics and logs; Log Analytics queries them with KQL (Kusto Query Language).
- Distributed tracing follows a request across services to locate latency and errors.

**Connect to and consume services (API Management, event/message)**
- Azure API Management publishes, secures, and throttles APIs behind a single gateway, with policies for rate-limiting and transformation.
- Azure Service Bus is a message broker for reliable, ordered, transactional messaging (queues and topics/subscriptions).
- Event Grid delivers lightweight event notifications (publish/subscribe); Service Bus suits commands/work items while Event Grid suits reactive event distribution.

### Recommended study pattern

- 1-2 hours of focused study per session.
- Weekly assessment checkpoints.
- Target 75% practice score before attempting the exam.

### Accessibility guidance for this track

- Learners who report attention or focus difficulties benefit from shorter 25-minute study blocks with breaks, rather than long sessions.
- Storage and security modules are concept-heavy; offer plain-language summaries before deep dives.
- Practice questions should be available in a text-only, screen-reader-friendly format.
