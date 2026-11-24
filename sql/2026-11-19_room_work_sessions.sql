-- Saved working state + full edit history (undo/redo/jump) per room project and tool (mix, board3d).
-- BILLO BINDER (hnzekejoaamsnmtqtwie). Reuses public.room_is_member(p text). Waiting on Billy's approval to apply.
create table if not exists public.room_work_sessions (
  id uuid primary key default gen_random_uuid(),
  project text not null references public.room_projects(id) on delete cascade,
  kind text not null check (kind in ('mix','board3d')),
  title text, head int not null default 0,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (project, kind));
create table if not exists public.room_work_edits (
  id bigserial primary key,
  session_id uuid not null references public.room_work_sessions(id) on delete cascade,
  seq int not null, label text not null, state jsonb not null, author text,
  discarded boolean not null default false, created_at timestamptz not null default now(),
  unique (session_id, seq));
alter table public.room_work_sessions enable row level security;
alter table public.room_work_edits enable row level security;
drop policy if exists rws_read on public.room_work_sessions;
drop policy if exists rwe_read on public.room_work_edits;
create policy rws_read on public.room_work_sessions for select to authenticated using (public.room_is_member(project));
create policy rwe_read on public.room_work_edits for select to authenticated
  using (exists (select 1 from public.room_work_sessions s where s.id = session_id and public.room_is_member(s.project)));
create or replace function public.room_work_open(p_project text, p_kind text, p_seed jsonb, p_title text default null)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s room_work_sessions; st jsonb;
begin
  if not room_is_member(p_project) then raise exception 'not on this project'; end if;
  select * into s from room_work_sessions where project = p_project and kind = p_kind;
  if not found then
    insert into room_work_sessions(project, kind, title, head) values (p_project, p_kind, p_title, 0) returning * into s;
    insert into room_work_edits(session_id, seq, label, state, author) values (s.id, 0, 'Start', coalesce(p_seed,'{}'::jsonb), auth.jwt()->>'email');
  end if;
  select state into st from room_work_edits where session_id = s.id and seq = s.head;
  return jsonb_build_object('session', s.id, 'head', s.head, 'state', st,
    'history', (select coalesce(jsonb_agg(jsonb_build_object('seq',seq,'label',label,'author',author,'at',created_at) order by seq),'[]')
                from room_work_edits where session_id = s.id and not discarded));
end $$;
create or replace function public.room_work_commit(p_session uuid, p_label text, p_state jsonb)
returns int language plpgsql security definer set search_path = public as $$
declare s room_work_sessions; n int;
begin
  select * into s from room_work_sessions where id = p_session for update;
  if not found or not room_is_member(s.project) then raise exception 'not on this project'; end if;
  update room_work_edits set discarded = true where session_id = s.id and seq > s.head and not discarded;
  select coalesce(max(seq),0) + 1 into n from room_work_edits where session_id = s.id;
  insert into room_work_edits(session_id, seq, label, state, author) values (s.id, n, left(p_label,200), p_state, auth.jwt()->>'email');
  update room_work_sessions set head = n, updated_at = now() where id = s.id;
  return n;
end $$;
create or replace function public.room_work_move(p_session uuid, p_seq int)
returns jsonb language plpgsql security definer set search_path = public as $$
declare s room_work_sessions; st jsonb;
begin
  select * into s from room_work_sessions where id = p_session for update;
  if not found or not room_is_member(s.project) then raise exception 'not on this project'; end if;
  select state into st from room_work_edits where session_id = s.id and seq = p_seq and not discarded;
  if st is null then raise exception 'no such step'; end if;
  update room_work_sessions set head = p_seq, updated_at = now() where id = s.id;
  return st;
end $$;
revoke all on function public.room_work_open(text,text,jsonb,text), public.room_work_commit(uuid,text,jsonb), public.room_work_move(uuid,int) from public, anon;
grant execute on function public.room_work_open(text,text,jsonb,text), public.room_work_commit(uuid,text,jsonb), public.room_work_move(uuid,int) to authenticated;
insert into public.room_projects (id, title, show_name, code, kind, status, format, brand_key, sort, created_by, logline)
values ('kfx-sipping','Sipping','Sipping — Whip ft. Lil Jeremy','SIP','record','Mix in progress · waiting on Lil Jeremy vocals','Record · 3:10 · 152 BPM · B minor','kfx',6,'billysorrells@gmail.com',
        'Whip''s record with Lil Jeremy; soundtrack candidate for Whip — The Break Up.')
on conflict (id) do nothing;
insert into public.room_members (email, project, role)
select m.email, 'kfx-sipping', m.role from public.room_members m where m.project = 'kfx-whip-101'
and not exists (select 1 from public.room_members x where x.project='kfx-sipping' and lower(x.email)=lower(m.email));
