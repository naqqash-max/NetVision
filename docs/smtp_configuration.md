# NetVision SMTP & Email Service Setup Guide

This guide details the email service architecture, environment variables, local development with Mailpit, production SMTP deployment, secret management, and Gmail App Password configuration.

---

## 1. Overview & Security Architecture

NetVision uses a decoupled, secure `EmailService` (`backend/app/services/email_service.py`) for delivering password reset notifications and account invitations.

### Security Guarantees
- **No Plaintext Passwords**: User passwords are never emailed, logged, or stored in plaintext.
- **Single-Use Tokens**: Recovery links use single-use, 256-bit cryptographically secure random tokens.
- **Token Hashing**: Tokens are stored in PostgreSQL solely as SHA-256 hashes (`token_hash`).
- **Expiration**: Reset links expire automatically after `RESET_TOKEN_EXPIRE_MINUTES` (default: 15 minutes).
- **Log Masking**: All secrets (`SMTP_PASSWORD`, tokens, keys) are scrubbed automatically from audit logs.

---

## 2. Environment Variables Reference

All SMTP settings are read dynamically from environment variables (or `.env` file). **Never hardcode credentials.**

| Variable | Description | Default | Production Example |
| :--- | :--- | :--- | :--- |
| `SMTP_HOST` | Hostname of the SMTP server | `smtp.gmail.com` | `smtp.sendgrid.net` |
| `SMTP_PORT` | Port for SMTP service | `587` | `587` (TLS) / `465` (SSL) |
| `SMTP_USERNAME` | SMTP authentication user / email | `""` | `apikey` or `your@email.com` |
| `SMTP_PASSWORD` | SMTP password or App Password | `""` | `your-16-char-app-password` |
| `SMTP_FROM_EMAIL` | Sender email address | `noreply@netvision.local` | `noc-alerts@yourdomain.com` |
| `SMTP_FROM_NAME` | Sender display name | `NetVision Operations Center` | `NetVision NOC` |
| `SMTP_TLS` | Enable STARTTLS encryption | `true` | `true` |
| `SMTP_SSL` | Enable implicit SSL encryption | `false` | `false` |
| `EMAIL_ENABLED` | Global toggle for outbound email | `true` | `true` |
| `FRONTEND_URL` | Base URL used for reset links | `http://localhost:3000` | `https://netvision.yourdomain.com` |
| `ENVIRONMENT` | Deployment environment mode | `production` | `production` |

---

## 3. Local Development with Mailpit

In local development, Mailpit can be used as a zero-configuration local SMTP server to catch outbound emails without sending external mail.

### Starting Mailpit with Docker Compose
```bash
docker compose up -d mailpit
```

### `.env` Settings for Mailpit
```env
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@netvision.local
SMTP_TLS=false
SMTP_SSL=false
EMAIL_ENABLED=true
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

### Accessing Captured Emails
Open your browser to: **`http://localhost:8025`**

---

## 4. Production Gmail SMTP Configuration & App Passwords

When using Gmail as an SMTP relay, Google requires an **App Password** if 2-Step Verification is enabled on your Google Account.

### Step-by-Step Gmail App Password Setup:
1. Log into your Google Account and go to **Security Settings** (`https://myaccount.google.com/security`).
2. Ensure **2-Step Verification** is enabled.
3. In the search bar at the top of Google Account, search for **App Passwords**.
4. Create a new App Password:
   - Select App: **Other (Custom name)**
   - Enter Name: `NetVision NOC SMTP`
   - Click **Generate**.
5. Google will display a 16-character pass-code (e.g. `abcd efgh ijkl mnop`).
6. Copy the 16-character code (without spaces) and paste it into your `.env` file as `SMTP_PASSWORD`.

### Production `.env` for Gmail SMTP:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.noc.admin@gmail.com
SMTP_PASSWORD=abcdefghijklmnop
SMTP_FROM_EMAIL=your.noc.admin@gmail.com
SMTP_FROM_NAME=NetVision Operations Center
SMTP_TLS=true
SMTP_SSL=false
EMAIL_ENABLED=true
FRONTEND_URL=https://netvision.yourdomain.com
ENVIRONMENT=production
```

---

## 5. Secret Management & Git Hygiene

- The `.env` file contains sensitive production credentials and **MUST NEVER** be committed to Git.
- Verify `.env` is listed in `.gitignore`:
  ```bash
  git check-ignore .env
  ```
- Always track configuration templates using `.env.example`.
- Secrets passed via Docker Compose are injected securely into container runtime environments.
