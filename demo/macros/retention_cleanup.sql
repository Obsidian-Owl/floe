{% macro retention_cleanup(model) %}
  {#
    Retention macro: delete records older than 1 hour.
    Applied as post-hook to mart models to prevent unbounded growth in demos.
    Only runs if the model has a _loaded_at timestamp column.
  #}
  {% if execute %}
    {% set columns = adapter.get_columns_in_relation(model) %}
    {% set col_names = columns | map(attribute='name') | list %}
    {% if '_loaded_at' in col_names %}
      {% set retention_query %}
        DELETE FROM {{ model }} WHERE _loaded_at < {{ dbt.current_timestamp() }} - INTERVAL '1 hour'
      {% endset %}
      {% do run_query(retention_query) %}
    {% endif %}
  {% endif %}
{% endmacro %}
