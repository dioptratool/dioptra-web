# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Docker Development (Primary)
- `docker compose build` - Build Docker images
- `docker compose run web python manage.py build -y` - Initialize database with sample data
- `docker compose up -d` - Start all services in detached mode
- `docker compose run web python manage.py <command>` - Run Django management commands in container

### Local Development
- `make install` - Install Python dependencies locally
- `make up` - Start supporting services (DB, etc.)
- `make run` - Run Django development server locally
- `make bootstrap-db` - Initialize database with sample data
- `make shell` - Django shell
- `make dbshell` - Database shell

### Testing
- `make test` - Run pytest tests with database reuse
- `make test-rebuild-db` - Run tests with fresh database

### Database Management
- `make psql` - Connect to PostgreSQL database
- `make migrate` - Run Django migrations
- `make makemigrations` - Create new migrations
- `make showmigrations` - Show migration status

### Code Quality
- `make tidy` - Format code with black, djade, django-upgrade, pyupgrade
- `make audit` - Check code formatting (dry run)
- `make security/bandit-baseline` - Run security checks against baseline

### Frontend Development
- `make fe-install` - Install Node.js dependencies
- `make fe-build` - Build CSS and JavaScript assets
- `make fe-watch` - Watch for frontend changes

## Architecture Overview

This is a Django web application for the Dioptra financial analysis tool with the following structure:

### Core Django App Structure
- **`website/`** - Main Django application containing all business logic
- **`website/models/`** - Django models organized by domain (analysis, cost tracking, etc.)
- **`website/views/`** - Views organized by feature areas
- **`website/templates/`** - Django templates
- **`website/static/website/`** - Frontend assets (CSS, JS, images)

### Key Components
- **Analysis Engine**: Multi-step workflow for financial analysis (`website/views/analysis/steps/`)
- **User Management**: Custom auth with OAuth support (`website/users/`, `website/oauth_providers/`)
- **Cost Tracking**: Sophisticated cost allocation and categorization system
- **Data Loading**: Bulk data import capabilities (`website/data_loading/`)
- **Admin Interface**: Extended Django admin (`website/admin/`)

### Settings Configuration
- **`website/settings/local.py`** - Local development (default)
- **`website/settings/docker.py`** - Docker environment
- **`website/settings/test.py`** - Testing environment
- **`website/settings/remote.py`** - Production environment

### Database Architecture
- Primary PostgreSQL database for application data
- Secondary transaction store database for financial data
- Uses Docker containers for local development databases

### Frontend Stack
- Bootstrap 3 with Sass compilation via Gulp
- jQuery-based JavaScript
- Responsive design with custom CSS framework

### Authentication & Authorization
- Django's built-in auth with custom backends
- OAuth integration via django-allauth (Okta, OneLogin, Microsoft)
- Role-based permissions system

### Development Environment
- Python 3.13.5 (see `.tool-versions`)
- Node.js 22.17.0 for frontend tooling
- Docker Compose for containerized development
- PostgreSQL databases (main app + transactions)

### Testing Framework
- pytest with Django integration
- Database reuse between test runs for speed
- Separate test database configuration

## Important Notes

- Default login: `dioptra_default+administrator@dioptratool.org` / `password`
- Environment variables required: `DJANGO_SECRET_KEY`, `DATABASE_PASSWORD`
- The application expects a transaction data pipeline service (see README for details)
- Frontend assets must be built before deployment (`make fe-build`)
- Security scanning with bandit is part of the development workflow