{{/*
Expand the name of the chart.
*/}}
{{- define "cognee-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "cognee-platform.fullname" -}}
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
{{- define "cognee-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "cognee-platform.labels" -}}
helm.sh/chart: {{ include "cognee-platform.chart" . }}
{{ include "cognee-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "cognee-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cognee-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "cognee-platform.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "cognee-platform.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the namespace for resources
*/}}
{{- define "cognee-platform.namespace" -}}
{{- .Values.global.namespace | default .Release.Namespace }}
{{- end }}

{{/*
PostgreSQL connection string
*/}}
{{- define "cognee-platform.postgresql.host" -}}
{{- if .Values.global.externalDatabase.postgresql.enabled }}
{{- .Values.global.externalDatabase.postgresql.host }}
{{- else }}
{{- printf "%s-postgresql" (include "cognee-platform.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Redis connection string
*/}}
{{- define "cognee-platform.redis.host" -}}
{{- if .Values.global.externalDatabase.redis.enabled }}
{{- .Values.global.externalDatabase.redis.host }}
{{- else }}
{{- printf "%s-redis-master" (include "cognee-platform.fullname" .) }}
{{- end }}
{{- end }}
