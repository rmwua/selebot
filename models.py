from sqlalchemy import (
    MetaData, Table, Column, Integer, Text, String,
    BigInteger, TIMESTAMP, func, Index, UniqueConstraint
)

metadata = MetaData()

celebrities = Table(
    "celebrities", metadata,
    Column("id",         Integer,    primary_key=True),
    Column("name",       Text,       nullable=False),
    Column("category",   Text,       nullable=True),
    Column("geo",        Text,       nullable=True),
    Column("status",     String(20), nullable=False),
    UniqueConstraint("name", "category", "geo", name="uq_celeb_name_cat_geo")
)

Index("idx_celeb_name_trgm", celebrities.c.name,
      postgresql_using="gin",
      postgresql_ops={"name": "gin_trgm_ops"})

pending_requests = Table(
    "pending_requests", metadata,
    Column("id",             Integer,    primary_key=True),
    Column("user_id",        BigInteger, nullable=False),
    Column("chat_id",        BigInteger, nullable=False),
    Column("message_id",     Integer,    nullable=False),
    Column("celebrity_name", Text,       nullable=False),
    Column("category", Text, nullable=False),
    Column("geo", Text, nullable=False),
    Column("created_at",     TIMESTAMP,  server_default=func.now(), nullable=False),
    Column("username",       String,     nullable=True)
)
