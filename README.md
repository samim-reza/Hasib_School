# Hasib School Management System

A production-ready Django application for managing a school/madrasa workflow, including admissions, student attendance, notices, teacher accounts, and finance tracking.

The UI and business flow are tailored for Bangla-speaking users, with Bengali labels and admin text across major modules.

## Highlights

- Teacher and super-admin authentication flows
- Student management with soft remove (inactive status)
- Admission workflow with printable admission sheet
- Daily attendance with teacher activity logging
- Public home page with active notices and admission headlines
- Super-admin notice board and admission ad management
- Finance transaction management (income/expense, filters, summaries)
- Admin-side financial history report with PDF export
- Health endpoint for uptime checks
- Render-ready deployment setup (Gunicorn + Whitenoise + build script)

## Tech Stack

- Python 3.11+
- Django 5.2
- PostgreSQL (recommended for production) via `DATABASE_URL`
- SQLite (default fallback for local development)
- Gunicorn + Whitenoise for production serving
- Tailwind/PostCSS build pipeline under `theme/static_src`

## Project Apps

- `academic`: authentication views, teacher portal, attendance, admissions, role checks
- `core`: notices and admission headlines shown on the public home page
- `finance`: transaction model and admin report/PDF export
- `theme`: frontend styling source and build config
- `config`: global Django settings, URL routing, ASGI/WSGI

## Quick Start (Local)

### 1. Clone and create virtual environment

```bash
git clone <your-repo-url>
cd Hasib_School
python -m venv .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Update `.env` values for local or production use.

### 4. Apply migrations and create an admin

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Run development server

```bash
python manage.py runserver
```

App will be available at:

- `http://127.0.0.1:8000/`
- Admin: `http://127.0.0.1:8000/admin/`

## Frontend Styles (Tailwind/PostCSS)

The CSS build pipeline is inside `theme/static_src`.

### Install Node dependencies

```bash
cd theme/static_src
npm install
```

### Watch mode (development)

```bash
npm run dev
```

### Production build

```bash
npm run build
```

Generated CSS output goes to `theme/static/css/dist/styles.css`.

## Environment Variables

The project includes `.env.example`. Primary variables:

| Variable | Required | Example | Notes |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | Yes | `replace_with_secure_key` | Falls back to `SECRET_KEY` if set |
| `DEBUG` | Yes | `False` | Use `False` in production |
| `ALLOWED_HOSTS` | Yes | `127.0.0.1,localhost,.onrender.com` | Comma-separated list |
| `CSRF_TRUSTED_ORIGINS` | Production | `https://*.onrender.com` | Comma-separated list |
| `DATABASE_URL` | Recommended | `postgresql://...` | Falls back to local SQLite when missing |
| `ADMIN_USERNAME` | Optional | `admin` | Present in template for optional bootstrap workflows |
| `ADMIN_EMAIL` | Optional | `admin@example.com` | Present in template for optional bootstrap workflows |
| `ADMIN_PASSWORD` | Optional | `change_this_password` | Present in template for optional bootstrap workflows |

## Authentication and Roles

- Super-admin routes are under `/super_admin/` and require a Django superuser.
- Teacher routes are under `/teacher/`.
- Teacher accounts created from management screens are initialized with default password `default123`.
- On first login with default password, teachers are redirected to password change.

## Key Routes

| Route | Purpose |
|---|---|
| `/` | Public home page with notices and admission headline |
| `/health/` | Plain-text health check (`ok`) |
| `/teacher/login/` | Teacher/admin login |
| `/teacher/` | Teacher portal (students, attendance, activity) |
| `/teacher/admissions/` | Admission records listing |
| `/super_admin/` | Super-admin login |
| `/super_admin/dashboard/` | Super-admin dashboard |
| `/super_admin/notices/` | Notice management |
| `/super_admin/admission-ads/` | Admission ad management |
| `/super_admin/finance/` | Finance management |
| `/admin/` | Django admin |

## Deployment (Render-Friendly)

This repository is already prepared for Render-like platforms:

- `build.sh` installs requirements, runs `collectstatic`, and applies migrations
- `Procfile` starts Gunicorn with production-friendly options
- Static files served through Whitenoise
- Secure cookie and proxy settings enabled automatically when `DEBUG=False`

### Typical deployment checklist

1. Set environment variables from `.env.example`.
2. Ensure `DEBUG=False`.
3. Set `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for your real domain(s).
4. Provide a production `DATABASE_URL` (PostgreSQL recommended).
5. Deploy with build command:

```bash
./build.sh
```

6. Start command is already defined by `Procfile`.

## Useful Commands

```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --no-input

# Run tests
python manage.py test

# Generate a secure Django secret key
python find_django_key.py
```

## Testing Status

Test modules exist, but currently contain placeholders only. Add unit/integration tests for admissions, attendance, and finance workflows before major production changes.

## Directory Overview

```text
Hasib_School/
|- academic/          # Core school workflows (teacher, attendance, admissions)
|- core/              # Notices and admission headlines
|- finance/           # Transactions and financial reporting
|- config/            # Django settings and root URL config
|- theme/             # Tailwind/PostCSS source and templates
|- templates/         # Global admin template overrides
|- static/            # Project static assets
|- requirements.txt
|- build.sh
|- Procfile
|- manage.py
```

## Security Notes

- Do not commit `.env` files.
- Rotate `DJANGO_SECRET_KEY` for each environment.
- Keep `DEBUG=False` in production.
- Use HTTPS and correct trusted origins configuration.

## License

No license file is currently provided. Add a `LICENSE` file if you want to define usage rights explicitly.
