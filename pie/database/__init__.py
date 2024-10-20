from __future__ import annotations

import importlib
import os
from typing import List

from sqlalchemy import Engine, String, create_engine, inspect
from sqlalchemy.orm import (
    Mapped,
    Session,
    declarative_base,
    mapped_column,
    sessionmaker,
)

from pie.cli import COLOR


class Database:
    """Main database connector."""

    def __init__(self):
        self.base = declarative_base()
        self.db: Engine = create_engine(
            os.getenv("DB_STRING"),
            # This forces the SQLAlchemy 1.4 to use the 2.0 syntax
            future=True,
        )


database = Database()
session: Session = sessionmaker(database.db, future=True)()


class DatabaseVersion(database.base):
    """Table that holds and manages DB versioning info for modules.

    :param module_name: Name of the module (with dots as path separators).
    :param version: Version of the module DB.
    """

    __tablename__ = "database_versions"
    module_name: Mapped[str] = mapped_column(String, primary_key=True)
    version: Mapped[int]

    def get(module_name: str) -> DatabaseVersion:
        """Returns the current version for DB stub.

        :module_name: Name of the module (with dots as path separators)
        """
        db_version = (
            session.query(DatabaseVersion)
            .filter_by(module_name=module_name)
            .one_or_none()
        )
        return db_version

    def set(module_name: str, version: int) -> DatabaseVersion:
        """Sets the current version for DB stub.

        :module_name: Name of the module (with dots as path separators)
        :db_version: Version of the DB to set
        """
        db_version = DatabaseVersion(module_name=module_name, version=version)
        session.merge(db_version)
        session.commit()

        return db_version


def init_core():
    """Load core models and create their tables.

    This function is responsible for creation of all core tables.
    """
    # Everything depends on DB versioning, we have to make sure it's created
    database.base.metadata.create_all(database.db)
    session.commit()

    _import_database(module_name="pie.database.config")

    for module in ("acl", "i18n", "logger", "storage", "spamchannel"):
        module_name: str = f"pie.{module}.database"
        _import_database(module_name=module_name)


def init_modules():
    """Load all database models and create their tables.

    This function is responsible for creation of all module tables.
    """
    repositories: List[str] = _list_directory_directories("modules")
    for repository in repositories:
        modules: List[str] = _list_directory_directories(repository)
        for module in modules:
            # Detect module's database files
            database_stub: str = os.path.join(module, "database")
            if not os.path.isfile(database_stub + ".py") and not os.path.isdir(
                database_stub
            ):
                continue

            module_name = database_stub.replace(os.sep, ".")

            # Import the module DB
            _import_database(module_name=module_name)


def _get_module_tables(module_name: str):
    return [
        class_reg_value.__tablename__
        for class_reg_value in database.base.registry._class_registry.values()
        if getattr(class_reg_value, "__module__") == module_name
        and hasattr(class_reg_value, "__tablename__")
    ]


def _import_database(module_name: str):
    """This functions imports the DB file (if exists).

    It also checks the DB file version against the DBVersion table.

    If the DB scheme is outdated, performs an update.

    Default version is 1 (to stay compatible with)

    :module_name: Name of the module (with dots as path separators)
    """
    try:
        db_module = importlib.import_module(module_name)

        module_version: int = getattr(db_module, "VERSION", 1)
        db_version: DatabaseVersion = DatabaseVersion.get(module_name=module_name)

        # Check if the DB is created from scratch. If so, set the DBVersion to current Module version.
        inspector = inspect(database.db)
        module_tables = _get_module_tables(module_name)
        existing_tables = inspector.get_table_names()
        found = False
        for table in module_tables:
            if table in existing_tables:
                found = True
                break
        if not found:
            db_version = DatabaseVersion.set(
                module_name=module_name, version=module_version
            )

        current_version = db_version.version if db_version else 1

        database.base.metadata.create_all(database.db)
        session.commit()

        for version in range(current_version, module_version):
            print(
                f"Updating database models {COLOR.green}{module_name}{COLOR.none}"
                + f" from version {COLOR.green}{version}{COLOR.none}"
                + f" to {COLOR.green}{version + 1}{COLOR.none}."
            )
            _update_schemes(module_name, version)

        print(
            f"Database models {COLOR.green}{module_name}{COLOR.none}"
            + f" version {COLOR.green}{module_version}{COLOR.none} imported."
        )
    except Exception as exc:
        session.rollback()
        print(
            f"Database models {COLOR.red}{module_name}{COLOR.none} failed: "
            f"{COLOR.cursive}{exc}{COLOR.none}."
        )  # noqa: T001
        raise


def _update_schemes(module_name: str, version: int):
    """Update the schemes for the DB."""
    path = module_name.split(".")
    path[-1] = "updates"
    path.append(f"update_{version}_to_{version + 1}")

    update_stub = ".".join(path)
    update = importlib.import_module(update_stub)
    update.run()
    DatabaseVersion.set(module_name=module_name, version=version + 1)


def _list_directory_directories(directory: str) -> List[str]:
    """Return filtered list of directories.

    :param directory: Absolute or relative (from the ``__main__`` file) path to
        the directory.
    :return: List of paths to directories inside the requested directory.
        Directories starting with underscore (e.g. ``__pycache__``) are not
        included.

    This function is used for repository & module discovery in
    :meth:`_import_database_tables` function.
    """
    if not os.path.isdir(directory):
        raise ValueError(f"{directory} is not a directory.")

    all_files = os.listdir(directory)
    filenames = [f for f in all_files if not f.startswith("_")]
    files = [os.path.join(directory, d) for d in filenames]
    return [d for d in files if os.path.isdir(d)]
