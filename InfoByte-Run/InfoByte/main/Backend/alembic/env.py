from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from backend.database import DATABASE_URL, engine
from backend.models import Base


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
_application_tables = {
    "users",
    "sessions",
    "quiz_attempts",
    "quiz_attempt_answers",
    "alembic_version",
}


def include_object(obj, name, type_, reflected, compare_to):
    """Keep migrations scoped to the account and quiz tables managed here."""
    if type_ == "table":
        return name in _application_tables
    table = getattr(obj, "table", None)
    if table is not None and table.name not in _application_tables:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL.render_as_string(hide_password=False),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        database_name = connection.execute(text("SELECT current_database()")).scalar_one()
        if database_name != "InfoByte":
            raise RuntimeError(
                f"Refusing InfoByte migration: connected database is {database_name!r}, expected 'InfoByte'."
            )
        # SQLAlchemy 2 starts a transaction for the SELECT above. End it
        # before Alembic manages its own transaction, or closing this
        # connection could roll back the DDL.
        connection.commit()
        print(f"Alembic connected to database: {database_name}")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
