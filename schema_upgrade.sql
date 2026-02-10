-- Enable pgvector extension to support embeddings
create extension if not exists vector;

-- Add embedding column to journal table (768 dimensions for Gemini)
alter table journal add column if not exists embedding vector(768);

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
