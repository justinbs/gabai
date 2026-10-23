-- Row count of every table, the newest audit entry and the migration revision.
-- Run the same file against production and against the restored copy, then compare.
select table_name || ' ' ||
       (xpath('/row/c/text()',
              query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text
from information_schema.tables
where table_schema = 'public' and table_type = 'BASE TABLE'
order by table_name;
select 'newest_audit_entry ' || coalesce(max(id)::text, 'none') from audit_log_entries;
select 'migration ' || version_num from alembic_version;
