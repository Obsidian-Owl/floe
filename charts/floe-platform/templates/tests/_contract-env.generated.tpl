{{- define "floe-platform.testRunner.contractEnv" -}}
{{- $context := . -}}
- name: FLOE_EXECUTION_CONTEXT
  value: "in-cluster"
- name: FLOE_RELEASE_NAME
  value: {{ $context.Release.Name | quote }}
- name: FLOE_NAMESPACE
  value: {{ $context.Release.Namespace | quote }}
- name: DAGSTER_WEBSERVER_HOST
  value: {{ include "floe-platform.dagster.webserverName" $context | quote }}
- name: DAGSTER_WEBSERVER_PORT
  value: "3000"
- name: POLARIS_HOST
  value: {{ include "floe-platform.polaris.fullname" $context | quote }}
- name: POLARIS_PORT
  value: "8181"
- name: POLARIS_MANAGEMENT_HOST
  value: {{ include "floe-platform.polaris.fullname" $context | quote }}
- name: POLARIS_MANAGEMENT_PORT
  value: "8182"
- name: MINIO_HOST
  value: {{ include "floe-platform.minio.fullname" $context | quote }}
- name: MINIO_PORT
  value: "9000"
- name: MINIO_CONSOLE_HOST
  value: {{ include "floe-platform.minio.fullname" $context | quote }}
- name: MINIO_CONSOLE_PORT
  value: "9001"
- name: POSTGRES_HOST
  value: {{ include "floe-platform.postgresql.host" $context | quote }}
- name: POSTGRES_PORT
  value: "5432"
- name: JAEGER_QUERY_HOST
  value: {{ include "floe-platform.jaeger.queryName" $context | quote }}
- name: JAEGER_QUERY_PORT
  value: "16686"
- name: OTEL_COLLECTOR_GRPC_HOST
  value: {{ include "floe-platform.otel.fullname" $context | quote }}
- name: OTEL_COLLECTOR_GRPC_PORT
  value: "4317"
- name: OTEL_COLLECTOR_HTTP_HOST
  value: {{ include "floe-platform.otel.fullname" $context | quote }}
- name: OTEL_COLLECTOR_HTTP_PORT
  value: "4318"
- name: MARQUEZ_HOST
  value: {{ include "floe-platform.marquez.fullname" $context | quote }}
- name: MARQUEZ_PORT
  value: "5000"
{{- end -}}
