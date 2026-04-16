# Week 1 Learnings

## What I built

- FastAPI app with CRUD endpoints
- PostgreSQL integration
- Pydantic validation
- Structured JSON logging
- Test suite (unit + integration)

## Key concepts I understand

1. Type hints: Type hints in Python provide a way to indicate the expected data types of function arguments and return values. They help with code readability, maintainability, and can be used by tools like linters and IDEs for static type checking. In this project, type hints are used extensively with FastAPI and Pydantic models to ensure data consistency and improve developer experience.
2. Dependency injection: FastAPI uses dependency injection to manage the creation and lifecycle of objects that your endpoints depend on. This allows you to define dependencies, such as database sessions or authentication mechanisms, in a declarative way. FastAPI automatically resolves these dependencies and injects them into your endpoint functions, promoting code reuse, testability, and separation of concerns.
3. Testing pyramid: Unit tests focus on testing individual components in isolation, ensuring that each function or method behaves as expected. Integration tests verify that different components of the application work together correctly, often involving interactions with external systems like databases. End-to-end (E2E) tests simulate real user scenarios by testing the entire application stack, from the frontend to the backend, to ensure that all components work together seamlessly.
4. Structured logging: Structured logging involves capturing log data in a consistent, machine-readable format, such as JSON, rather than plain text. This approach allows for better log aggregation, searching, and analysis, especially in distributed systems. In this project, structured JSON logging is used to include metadata like request correlation IDs, making it easier to trace and debug requests across different services.

## What I struggled with

- Alembic migrations with psycopg3: Initially, I faced issues running Alembic migrations due to the use of psycopg3 with SQLAlchemy. The main problem was that the connection object provided by psycopg3 did not have the expected .dialect attribute, which caused errors when running migrations. After researching and experimenting, I found a solution by using SQLAlchemy's sync Engine with the psycopg dialect in the `alembic/env.py` file. This approach allows Alembic to work properly with psycopg3 and is compatible with Python 3.14.
- Database configuration: I had to adjust the PostgreSQL configuration for development. Initially, I had `listen_addresses = '*'` in `postgresql.conf`, which is not ideal for a local development environment. I removed this setting to restrict connections to localhost. Additionally, I kept the localhost `trust` rule in `pg_hba.conf` for development purposes, which allows for easier authentication without requiring passwords.
- Documentation: I realized the importance of documenting the issues I encountered, especially the one with Alembic and psycopg3. I created a `gotchas.md` file to document this issue and the authentication patterns I used in the database configuration. This documentation will be helpful for future reference and for other developers who might face similar issues.
- Performance testing: I added baseline performance tests for inserting and listing 1000 records in `test_performance.py`. This was important to establish benchmarks for future optimizations and to ensure that the application can handle a reasonable load. Writing these tests required careful consideration of how to measure performance accurately and consistently.
- Logging configuration: Setting up structured logging with the `structlog` library required some experimentation to get the configuration right. I had to ensure that the logs included the necessary metadata, such as request correlation IDs, and that they were output in a consistent JSON format. This involved configuring the logging setup at the application initialization stage and ensuring that all loggers in the application were properly configured to use the structured logging setup.