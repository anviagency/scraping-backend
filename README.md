# Scraping-backend

Backend for the Scraping.co.il platform built with Django, REST framework, and Stripe integration.

## Features

- User authentication and registration
- Stripe payment integration
- External systems integration
- Webhook management
- API documentation with Swagger

## Getting Started

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Docker and Docker Compose (optional)

### Local Development Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/scraping-backend.git
cd scraping-backend
```

2. Create a virtual environment and activate it:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file based on the `.env.template`:

```bash
cp .env.template .env
```

5. Edit the `.env` file with your configuration.

6. Run migrations:

```bash
python manage.py migrate
```

7. Create a superuser:

```bash
python manage.py createsuperuser
```

8. Run the development server:

```bash
python manage.py runserver
```

### Docker Setup

1. Clone the repository:

```bash
git clone https://github.com/yourusername/scraping-backend.git
cd scraping-backend
```

2. Create a `.env` file based on the `.env.template`:

```bash
cp .env.template .env
```

3. Edit the `.env` file with your configuration.

4. Build and start the containers:

```bash
docker-compose up -d
```

5. Create a superuser:

```bash
docker-compose exec web python manage.py createsuperuser
```

## API Documentation

API documentation is available at `/swagger/` when the server is running.

## Project Structure

- `accounts`: User authentication and management
- `payments`: Stripe integration and payment processing
- `integrations`: External systems integration
- `api`: Central API entry point
- `utils`: Utility functions

## Deployment

The project includes Docker and Nginx configurations for deployment. Follow these steps:

1. Set up your server with Docker and Docker Compose.
2. Clone the repository and configure the `.env` file.
3. Run `docker-compose up -d` to start all services.
4. Set up SSL certificates with certbot.

## License

This project is licensed under the MIT License - see the LICENSE file for details.