{#
  Seleciona a versão mais recente de cada chave natural na camada raw.
  - Lotes posteriores substituem os anteriores (tabelas de estado).
  - Cópias idênticas dentro do mesmo lote são contadas em _copies_in_batch.
#}
{% macro latest_version(source_table, key) %}
    select *
    from (
        select
            r.*,
            row_number() over (partition by btrim(r.{{ key }}) order by r._batch_id desc, r._row_number desc) as _version_rank,
            count(*) over (partition by btrim(r.{{ key }}), r._batch_id) as _copies_in_batch,
            (dense_rank() over (partition by btrim(r.{{ key }}) order by r._batch_id)
             + dense_rank() over (partition by btrim(r.{{ key }}) order by r._batch_id desc) - 1) as _versions
        from {{ source('raw', source_table) }} r
    ) v
    where _version_rank = 1
{% endmacro %}
