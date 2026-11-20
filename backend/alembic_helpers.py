import sqlalchemy as sa

from alembic import op


class AdditiveSchema:
    """Small idempotent helper for migrations that may run after create_all()."""

    def create_table(self, name, *columns):
        if name not in sa.inspect(op.get_bind()).get_table_names():
            op.create_table(name, *columns)

    def create_index(self, name, table_name, columns, **kwargs):
        existing = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}
        if name not in existing:
            op.create_index(name, table_name, columns, **kwargs)
