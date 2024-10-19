"""This is an example on how to handle DB updates from version to version

The name of the file must be update_{version}_to_{version+1}.py
For example: `update_1_to_2.py`
The file must be placed into folder `updates` located in the same directory
as database.py file for the module
For example:
    `./pie/acl/updates/update_1_to_2.py`
    `./modules/base/errors/updates/update_1_to_2.py`

The update can be done only from version to version + 1 (can't skip versions).

The inspector should be used to figure out if the update is needed.
It might happen that the module with newer schema is freshly installed
before the core is updated to the version that supports DB updates
"""

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

            # Check that the rename of the table is needed
            if "old_boring_name" in inspector.get_table_names():
                ops.rename_table("old_boring_name", "cool_new_name")

            # Get column names for table `my_table`
            my_table_columns = [
                column["name"] for column in inspector.get_columns("my_table")
            ]

            # Check if the column needs to be renamed. This can be also used to add / remove column
            if "my_old_name" in my_table_columns:
                ops.alter_column(
                    "my_table", column_name="my_old_name", new_column_name="my_new_name"
                )

            # Adds a column and sets the value for all rows
            if "add_this" not in my_table_columns:
                column = Column(Integer, name="add_this", default=42)
                ops.add_column(table_name="my_table", column=column)
                ops.execute("UPDATE my_table SET add_this = 42")
