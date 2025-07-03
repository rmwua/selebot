import os
import pandas as pd
from unidecode import unidecode
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))
df = (
    pd.read_csv("celebrities_clean.csv", dtype=str)
      .rename(columns={
          "Имя":      "name",
          "Категория":"category",
          "Гео":      "geo",
          "Статус":   "status"
       })
      .fillna("")
      .apply(lambda col: col.str.lower())
)

# статус
df.loc[df["status"] == "черный список", "status"] = "нельзя использовать"
df.loc[df["category"] == "вальгус", "category"] = "суставы"
df.loc[df["category"] == "красота/омоложение", "category"] = "омоложение"
df.loc[df["category"] == "красота", "category"] = "омоложение"

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
        DO NOTHING
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
