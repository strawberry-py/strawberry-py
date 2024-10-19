from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Integer, inspect

from pie.database import database


def run():
    # We are using inspector to make sure the changes are necessary
    inspector = inspect(database.db)

    # Connect to database and create migration context
    with database.db.connect() as conn:
        mc = MigrationContext.configure(conn)

        # We are using transaction so either all changes passes or none passes
        with mc.begin_transaction():
            ops = Operations(mc)

            # Get column names for table `config`
            my_table_columns = [
                column["name"] for column in inspector.get_columns("config")
            ]

            # Add new column and set the value
            if "cache_max_messages" not in my_table_columns:
                column = Column(Integer, name="cache_max_messages", default=1000)
                ops.add_column(table_name="config", column=column)
                ops.execute("UPDATE config SET cache_max_messages = 1000;")
