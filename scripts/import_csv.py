import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

df = pd.read_csv("celebrities_clean.csv")

df = df.rename(columns={
    "Имя":      "name",
    "Категория":"category",
    "Гео":      "geo",
    "Статус":   "status"
})

for col in ["name", "category", "geo", "status"]:
    df[col] = df[col].astype(str).str.lower()

engine = create_engine(DATABASE_URL)

with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
    for _, row in df.iterrows():
        conn.execute(
            text("""
                INSERT INTO celebrities (name, category, geo, status)
                VALUES (:name, :category, :geo, :status)
                ON CONFLICT (name, category, geo) DO NOTHING
            """),
            {
                "name":     row["name"],
                "category": row["category"],
                "geo":      row["geo"],
                "status":   row["status"],
            }
        )

print("Импорт из celebrities_clean.csv завершён")
