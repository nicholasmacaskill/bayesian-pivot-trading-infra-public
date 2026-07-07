import psycopg2
import sys
import os
from dotenv import load_dotenv

load_dotenv(".env")

# Direct Postgres Connection
DB_HOST = "127.0.0.1"
DB_PORT = "54322"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "postgres"

def refresh_schema():
    print(f"🔄 Refreshing PostgREST Schema Cache...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        cur.execute("NOTIFY pgrst, 'reload schema';")
        
        print("✅ Signal sent. Cache should refresh shortly.")
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    refresh_schema()
