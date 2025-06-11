#!/usr/bin/env python3
import os
import pandas as pd
from unidecode import unidecode
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
df = pd.read_csv("celebrities_clean.csv").rename(columns={
    "Имя": "name", "Категория": "category",
    "Гео": "geo", "Статус": "status"
}).applymap(str).applymap(str.lower)

# статус
df.loc[df["status"] == "черный список", "status"] = "нельзя использовать"

with engine.begin() as conn:
    # вставляем / обновляем все поля, включая ascii_name
    insert = text("""
        INSERT INTO celebrities
          (name, normalized_name, ascii_name, category, geo, status)
        VALUES
          (:name,
           lower(unaccent(:name)),
           :ascii_name,
           :category,
           :geo,
           :status
          )
        ON CONFLICT (name, category, geo)
        DO UPDATE SET
          status         = EXCLUDED.status,
          normalized_name= EXCLUDED.normalized_name,
          ascii_name     = EXCLUDED.ascii_name;
    """)
    for _, row in df.iterrows():
        conn.execute(insert, {
            "name":            row["name"],
            "ascii_name":      unidecode(row["name"]).lower(),
            "category":        row["category"],
            "geo":             row["geo"],
            "status":          row["status"],
        })

print("Импорт завершён")
