create table if not exists topology_snapshot (
  id bigserial primary key,
  created_at timestamptz not null default now(),
  source text not null,
  source_revision text,
  node_count integer not null default 0,
  link_count integer not null default 0,
  payload jsonb not null
);

create index if not exists topology_snapshot_created_at_idx
  on topology_snapshot (created_at desc);

create table if not exists topology_node (
  snapshot_id bigint not null references topology_snapshot(id) on delete cascade,
  node_id text not null,
  node_key text,
  address text,
  name text,
  coords text,
  city text,
  country text,
  x double precision,
  y double precision,
  metadata jsonb not null default '{}'::jsonb,
  primary key (snapshot_id, node_id)
);

create index if not exists topology_node_name_idx
  on topology_node (name);

create table if not exists topology_link (
  snapshot_id bigint not null references topology_snapshot(id) on delete cascade,
  source_node_id text not null,
  target_node_id text not null,
  kind text not null default 'mesh',
  metadata jsonb not null default '{}'::jsonb,
  primary key (snapshot_id, source_node_id, target_node_id, kind)
);

create table if not exists topology_probe (
  id bigserial primary key,
  measured_at timestamptz not null default now(),
  node_id text not null,
  probe_url text not null,
  status text not null,
  latency_ms integer,
  vantage text not null default 'browser',
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists topology_probe_node_id_measured_at_idx
  on topology_probe (node_id, measured_at desc);
