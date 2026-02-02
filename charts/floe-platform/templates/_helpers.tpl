{{/*
floe-platform Helm Chart Helper Templates
=========================================

This file contains helper templates used across all chart templates.
Templates follow Helm best practices for naming, labels, and selectors.

Usage:
  {{ include "floe-platform.fullname" . }}
  {{ include "floe-platform.labels" . }}
*/}}

{{/*
Expand the name of the chart.
*/}}
{{- define "floe-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this.
If release name contains chart name it will be used as a full name.
*/}}
{{- define "floe-platform.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "floe-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels for all resources.
*/}}
{{- define "floe-platform.labels" -}}
helm.sh/chart: {{ include "floe-platform.chart" . }}
{{ include "floe-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: floe-platform
floe.dev/environment: {{ .Values.global.environment | default "dev" }}
{{- with .Values.global.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels for pod selection.
*/}}
{{- define "floe-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "floe-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Component-specific labels.
Usage: {{ include "floe-platform.componentLabels" (dict "component" "polaris" "context" .) }}
*/}}
{{- define "floe-platform.componentLabels" -}}
{{ include "floe-platform.labels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Component-specific selector labels.
Usage: {{ include "floe-platform.componentSelectorLabels" (dict "component" "polaris" "context" .) }}
*/}}
{{- define "floe-platform.componentSelectorLabels" -}}
{{ include "floe-platform.selectorLabels" .context }}
app.kubernetes.io/component: {{ .component }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "floe-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "floe-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Namespace helper - returns the namespace to deploy to.
Uses release namespace unless explicitly overridden.
*/}}
{{- define "floe-platform.namespace" -}}
{{- if .Values.namespace.name }}
{{- .Values.namespace.name }}
{{- else }}
{{- .Release.Namespace }}
{{- end }}
{{- end }}

{{/*
Environment-based namespace using cluster mapping.
Usage: {{ include "floe-platform.environmentNamespace" (dict "environment" "staging" "context" .) }}
*/}}
{{- define "floe-platform.environmentNamespace" -}}
{{- $env := .environment }}
{{- $context := .context }}
{{- $mapping := dict }}
{{- range $key, $value := $context.Values.clusterMapping }}
{{- if has $env $value.environments }}
{{- $mapping = $value }}
{{- end }}
{{- end }}
{{- if $mapping.namespaceTemplate }}
{{- tpl $mapping.namespaceTemplate (dict "environment" $env) }}
{{- else }}
{{- printf "floe-%s" $env }}
{{- end }}
{{- end }}

{{/*
PostgreSQL connection string.
Returns the connection string for PostgreSQL based on configuration.
*/}}
{{- define "floe-platform.postgresql.host" -}}
{{- if .Values.postgresql.enabled }}
{{- printf "%s-postgresql" (include "floe-platform.fullname" .) }}
{{- else }}
{{- .Values.dagster.postgresql.host }}
{{- end }}
{{- end }}

{{- define "floe-platform.postgresql.port" -}}
{{- if .Values.postgresql.enabled }}
{{- 5432 }}
{{- else }}
{{- .Values.dagster.postgresql.port | default 5432 }}
{{- end }}
{{- end }}

{{/*
PostgreSQL secret name.
*/}}
{{- define "floe-platform.postgresql.secretName" -}}
{{- if .Values.postgresql.auth.existingSecret }}
{{- .Values.postgresql.auth.existingSecret }}
{{- else }}
{{- printf "%s-postgresql" (include "floe-platform.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Polaris component name.
*/}}
{{- define "floe-platform.polaris.fullname" -}}
{{- printf "%s-polaris" (include "floe-platform.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
OTel Collector component name.
*/}}
{{- define "floe-platform.otel.fullname" -}}
{{- printf "%s-otel" (include "floe-platform.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Marquez component name.
*/}}
{{- define "floe-platform.marquez.fullname" -}}
{{- printf "%s-marquez" (include "floe-platform.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common annotations for all resources.
*/}}
{{- define "floe-platform.annotations" -}}
{{- with .Values.global.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Pod security context.
*/}}
{{- define "floe-platform.podSecurityContext" -}}
{{- toYaml .Values.podSecurityContext }}
{{- end }}

{{/*
Container security context.
*/}}
{{- define "floe-platform.containerSecurityContext" -}}
{{- toYaml .Values.containerSecurityContext }}
{{- end }}

{{/*
Image pull secrets.
*/}}
{{- define "floe-platform.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end }}

{{/*
Resource preset lookup.
Usage: {{ include "floe-platform.resourcePreset" (dict "preset" "small" "context" .) }}
*/}}
{{- define "floe-platform.resourcePreset" -}}
{{- $preset := .preset }}
{{- $presets := .context.Values.resourcePresets }}
{{- if hasKey $presets $preset }}
{{- toYaml (get $presets $preset) }}
{{- else }}
{{- toYaml (get $presets "small") }}
{{- end }}
{{- end }}

{{/*
Wait-for-postgres init container.
Waits for PostgreSQL to be ready before starting main container.
*/}}
{{- define "floe-platform.waitForPostgres" -}}
- name: wait-for-postgres
  image: postgres:16-alpine
  imagePullPolicy: {{ .Values.global.imagePullPolicy }}
  command:
    - /bin/sh
    - -c
    - |
      until pg_isready -h {{ include "floe-platform.postgresql.host" . }} -p {{ include "floe-platform.postgresql.port" . }}; do
        echo "Waiting for PostgreSQL..."
        sleep 2
      done
      echo "PostgreSQL is ready"
  securityContext:
    {{- include "floe-platform.containerSecurityContext" . | nindent 4 }}
{{- end }}
