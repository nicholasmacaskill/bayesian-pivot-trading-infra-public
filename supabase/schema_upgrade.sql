-- Enable pgvector extension to support embeddings
create extension if not exists vector;

-- Add embedding and trade level columns to journal and scans tables (768 dimensions for Gemini)
alter table journal add column if not exists embedding vector(768);
alter table scans add column if not exists embedding vector(768);

-- Trade levels: required for outcome resolution and fine-tuning
alter table scans add column if not exists entry real;
alter table scans add column if not exists stop_loss real;
alter table scans add column if not exists target real;
alter table scans add column if not exists r_multiple real default 3.0;

-- Outcome fields: populated by resolve_scan_outcomes.py
alter table scans add column if not exists outcome text default 'OPEN';
alter table scans add column if not exists resolved_at timestamptz;
alter table scans add column if not exists actual_r real;

-- Create match_trades function for semantic search
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
-- Create match_scans function for semantic search
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
