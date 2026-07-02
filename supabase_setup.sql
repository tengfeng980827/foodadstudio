-- Food AI Studio Supabase setup
-- Run this once in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  plan text not null default 'trial',
  trial_limit integer not null default 10,
  trial_used integer not null default 0,
  trial_expired boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.designs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  user_email text,
  image_url text not null,
  download_url text,
  visual_type text,
  title text,
  created_at timestamptz not null default now()
);

create index if not exists designs_user_created_idx
  on public.designs (user_id, created_at desc);

create or replace function public.increment_trial_usage(user_id_input uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.profiles
  set
    trial_used = coalesce(trial_used, 0) + 1,
    trial_expired = case
      when plan = 'trial' and created_at < now() - interval '2 days' then true
      else trial_expired
    end,
    updated_at = now()
  where id = user_id_input;
end;
$$;

alter table public.profiles enable row level security;
alter table public.designs enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
on public.profiles for select
to authenticated
using (auth.uid() = id);

drop policy if exists "designs_select_own" on public.designs;
create policy "designs_select_own"
on public.designs for select
to authenticated
using (auth.uid() = user_id);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'generated-images',
  'generated-images',
  true,
  52428800,
  array['image/png', 'image/jpeg', 'image/webp']
)
on conflict (id) do update
set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "generated_images_public_read" on storage.objects;
create policy "generated_images_public_read"
on storage.objects for select
to public
using (bucket_id = 'generated-images');
