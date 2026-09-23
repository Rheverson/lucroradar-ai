{# Falha quando |a - b| > tolerância absoluta (centavos por arredondamento). #}
{% test approx_equal(model, column_name, other, tolerance=0.05) %}
select * from {{ model }} where abs(coalesce({{ column_name }},0) - coalesce({{ other }},0)) > {{ tolerance }}
{% endtest %}
