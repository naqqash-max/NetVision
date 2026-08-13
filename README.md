# NetVision

![NetVision Banner](./netvision_preview.png)

NetVision is a premium, full-stack enterprise-grade Network Telemetry and Management Platform. It provides network administrators and operators with a consolidated glass-pane dashboard for real-time ICMP, TCP, and SNMP network monitoring, automated threshold-based alerting, interactive topology maps, and strict Role-Based Access Control (RBAC).

---

## 🌟 Key Features

*   **⚡ Real-Time ICMP Polling**: Active background daemon that queries authorized targets, records historical latency, packet loss, and reports online/degraded/offline status transitions.
*   **🔌 TCP Port Monitoring**: Fine-grained monitoring engine verifying the reachability of configured TCP services (e.g., SSH, HTTP, PostgreSQL) on monitored hosts.
*   **📊 Live SNMP Telemetry**: Full SNMP v2c implementation querying interface operational statuses, traffic-rate counters (inbound/outbound bandwidth), sysName, sysDescr, and system uptime.
*   **🚨 Alert & Event Engine**: Evaluates metrics against configurable thresholds, deduplicates events, transitions alert states, and sends instant alerts.
*   **🔒 Auth & Role-Based Access Control (RBAC)**: Secure FastAPI authentication powered by JWT tokens and salted bcrypt password hashes. Distinct roles enforce granular permissions:
    *   `ADMIN`: Full write-access (manage users, register/delete/edit devices, modify network topology).
    *   `OPERATOR`: Read-only access + manual diagnostics trigger (trigger manual Ping, run ad-hoc SNMP polls).
    *   `VIEWER`: Read-only telemetry access.
*   **🗺️ Topology Visualizer**: A dynamic network connectivity graph rendering fiber/ethernet links between active hosts with status indication.
*   **📝 Secure Audit Logging**: Immutable database logs detailing configuration changes, access logs, and diagnostic triggers with user attribution.

---

## 🏗️ Architecture

NetVision is designed as a distributed, decoupled multi-container application orchestrating three primary sub-systems:

```mermaid
graph TD
    Client[React SPA Frontend] -->|authFetch JWT| Backend[FastAPI Core API]
    Backend -->|SQLAlchemy| DB[(PostgreSQL Database)]
    Engine[Networking Engine Daemon] -->|Poll Status| DB
    Engine -->|ICMP Ping / TCP Socket| Target[Network Devices]
    Engine -->|SNMP Get/Walk| Target
```

1.  **React Frontend**: A modern, glassmorphic UI built using React, Tailwind CSS, Lucide icons, and optimized state management.
2.  **FastAPI Backend**: Reentrant REST API handling user sessions, device configurations, active alerts, topology links, and audit logs.
3.  **Networking Engine**: A dedicated background service executing parallel scheduling tasks to poll target devices via ICMP, TCP sockets, and SNMP handlers.

---

## 📁 Repository Structure

```text
├── backend/                   # FastAPI Web Application
│   ├── app/
│   │   ├── api/               # Router endpoints and dependency injection (RBAC)
│   │   ├── core/              # DB session, configurations, security utilities
│   │   ├── models/            # SQLAlchemy database models
│   │   └── schemas/           # Pydantic validation schemas
│   └── Dockerfile
├── frontend/                  # React Vite Client Application
│   ├── src/                   # App.jsx, components, utilities, styling
│   └── Dockerfile
├── networking-engine/         # Monitoring & Diagnostics Scheduler
│   ├── services/              # icmp_monitor, tcp_monitor, snmp_monitor, alert_engine
│   └── Dockerfile
├── database/                  # Database Migration and Seeds
│   ├── schema.sql             # SQL Schema definition
│   └── seed.sql               # Seed data for initial users and devices
├── tests/                     # Test Suites
│   └── test_backend/          # API, RBAC, ICMP, and TCP Backend Integration Tests
└── docker-compose.yml         # Container Orchestration Manifest
```

---

## 🚀 Quick Start (Docker Compose)

Ensure you have [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed.

### 1. Build and Run the Stack
Spin up the NetVision services in the background:
```bash
docker-compose up -d --build
```
This starts the following services:
*   `netvision_db` (PostgreSQL on port `5432`)
*   `netvision_backend` (FastAPI on port `8000`)
*   `netvision_frontend` (React Nginx server on port `3000`)
*   `netvision_networking_engine` (Telemetry poller)
*   `netvision_snmpsim` (Simulated SNMP Agent on port `1161/udp`)

### 2. Access the Application
Open your browser and navigate to:
*   **Web Portal**: [http://localhost:3000](http://localhost:3000)
*   **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Log In Credentials
To access administrative features, log in using the initial seeded credentials:
*   **Username**: `admin`
*   **Password**: `admin123`

---

## ⚙️ Configuration & Environment

The backend container loads configuration parameters via environment variables defined inside `docker-compose.yml`:

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://admin:supersecretpassword123@database:5432/netvision` |
| `SECRET_KEY` | JWT signing secret | `anothertopsysecretkey9876543210` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Session validity duration | `60` |

---

## 🧪 Running the Test Suite

The backend features a comprehensive test suite with 32 automated unit and integration tests covering authentication, database schema validations, API routes, RBAC constraints, and diagnostics.

To run the backend test suite inside the production-like container environment:

```bash
# Copy tests folder into the running backend container
docker cp tests netvision_backend:/app/tests

# Execute the test suite using pytest
docker exec -it netvision_backend pytest -v

# Clean up tests folder from the container
docker exec netvision_backend rm -rf tests
```

---

## 🛡️ Security & Auditing

*   **Role Gating**: Strict endpoint verification on the FastAPI layer via `require_admin` and `require_operator` dependencies.
*   **Password Hashing**: Passwords are saved inside the database using salted `bcrypt` hashes; raw passwords are never returned or logged.
*   **Stateful Audit Trails**: All state changes (device creation, threshold alterations, manual diagnostic executions, configuration changes) log the user, operation details, client IP address, and timestamp.
