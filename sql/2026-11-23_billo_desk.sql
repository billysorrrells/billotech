-- billo_desk: private rows for the Billo Browser doorway (open loops, people, watch list).
-- Owner-only RLS: auth email billysorrells@gmail.com or billysorrells@writersroom.bse. Applied 2026-11-23.
create table if not exists public.billo_desk (id bigint generated always as identity primary key, kind text not null check (kind in ('loop','person','watch','link')), title text not null, detail text, link text, tag text, sort int default 100, done boolean default false, updated_at timestamptz default now());
alter table public.billo_desk enable row level security;
create or replace function public.billo_desk_owner() returns boolean language sql stable as $$ select coalesce(auth.jwt()->>'email','') in ('billysorrells@gmail.com','billysorrells@writersroom.bse') $$;
create policy billo_desk_owner_all on public.billo_desk for all to authenticated using (public.billo_desk_owner()) with check (public.billo_desk_owner());
