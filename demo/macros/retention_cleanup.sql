{% macro retention_cleanup(model) %}
  {#
    Retention macro: delete records older than 1 hour.
    Applied as post-hook to mart models to prevent unbounded growth in demos.
    Uses _loaded_at timestamp column present in all models.
  #}
  {% if execute %}
    {% set retention_query %}
      DELETE FROM {{ model }} WHERE _loaded_at < {{ dbt.current_timestamp() }} - INTERVAL '1 hour'
    {% endset %}
    {% do run_query(retention_query) %}
  {% endif %}
{% endmacro %}
