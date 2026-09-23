{% test dbt_unique_unit_day(model) %}
select unit_id, date_day, count(*) from {{ model }} group by 1, 2 having count(*) > 1
{% endtest %}
