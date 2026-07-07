import psycopg2
import sys
import os
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local")

# Supabase Local Settings (Direct Postgres Connection)
DB_HOST = "127.0.0.1"
DB_PORT = "54322"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "postgres"

def init_vector_schema():
    print(f"🔌 Connecting to Local Supabase for Vector Upgrade...")
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
        
        print("🧠 Enabling pgvector extension...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        print("📊 Adding embedding columns to journal and scans tables...")
        # Add vector columns (768 dimensions for Gemini/Vertex embeddings)
        cur.execute("ALTER TABLE journal ADD COLUMN IF NOT EXISTS embedding vector(768);")
        cur.execute("ALTER TABLE scans ADD COLUMN IF NOT EXISTS embedding vector(768);")
        
        print("🔎 Creating match functions...")
        # Create RPC functions for similarity search
        cur.execute("""
            create or replace function match_trades (
              query_embedding vector(768),
              match_threshold float,
              match_count int
            )
            returns table (
              id bigint,
              trade_id text,
              symbol text,
              pnl real,
              ai_grade real,
              notes text,
              similarity float
            )
            language plpgsql
            as $$
            begin
              return query(
                select
                  journal.id,
                  journal.trade_id,
                  journal.symbol,
                  journal.pnl,
                  journal.ai_grade,
                  journal.notes,
                  1 - (journal.embedding <=> query_embedding) as similarity
                from journal
                where 1 - (journal.embedding <=> query_embedding) > match_threshold
                order by journal.embedding <=> query_embedding
                limit match_count
              );
            end;
            $$;

            create or replace function match_scans (
              query_embedding vector(768),
              match_threshold float,
              match_count int
            )
            returns table (
              id bigint,
              symbol text,
              pattern text,
              ai_score real,
              ai_reasoning text,
              similarity float
            )
            language plpgsql
            as $$
            begin
              return query(
                select
                  scans.id,
                  scans.symbol,
                  scans.pattern,
                  scans.ai_score,
                  scans.ai_reasoning,
                  1 - (scans.embedding <=> query_embedding) as similarity
                from scans
                where 1 - (scans.embedding <=> query_embedding) > match_threshold
                order by scans.embedding <=> query_embedding
                limit match_count
              );
            end;
            $$;
        """)
        
        print("✅ Vector Schema Upgrade Complete.")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Database Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_vector_schema()
