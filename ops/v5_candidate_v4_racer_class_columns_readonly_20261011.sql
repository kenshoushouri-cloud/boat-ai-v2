-- V5 candidate-v4 one-column type mismatch diagnosis, metadata ONLY.
-- Run on: boat-v2-postgres / production / postgres-hobby-fullhistory-candidate-v4 / Data > Query.
-- One SELECT; no data rows, schema changes, privileges changes or writes.
-- racer_class was declared INTEGER by pg_schema_compat_v5.py;
-- racer_class_text was declared TEXT; neither definition proves live state.
WITH expected(column_name) AS (
  VALUES ('racer_class'), ('racer_class_text'), ('racer_number')
)
SELECT e.column_name,
       COALESCE(c.udt_name, 'MISSING') AS udt_name,
       COALESCE(c.data_type, 'MISSING') AS data_type,
       COALESCE(c.is_nullable, 'UNKNOWN') AS is_nullable,
       CASE
         WHEN c.column_name IS NULL THEN 'COLUMN_MISSING'
         WHEN e.column_name = 'racer_class'
              AND c.udt_name IN ('int2','int4','int8') THEN 'NUMERIC_CLASS_CODE'
         WHEN e.column_name = 'racer_class_text'
              AND c.udt_name IN ('text','varchar') THEN 'TEXT_CLASS_CANDIDATE'
         WHEN e.column_name = 'racer_number'
              AND c.udt_name IN ('int2','int4','int8') THEN 'RACER_NUMBER_COMPATIBLE'
         ELSE 'UNEXPECTED_TYPE'
       END AS inspection_status
FROM expected e
LEFT JOIN information_schema.columns c
  ON c.table_schema = 'public'
 AND c.table_name = 'v2_race_entries'
 AND c.column_name = e.column_name
ORDER BY e.column_name;
