{{/*
Expand the name of the chart.
*/}}
{{- define "cognee-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "cognee-api.fullname" -}}
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
{{- define "cognee-api.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "cognee-api.labels" -}}
helm.sh/chart: {{ include "cognee-api.chart" . }}
{{ include "cognee-api.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "cognee-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cognee-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "cognee-api.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "cognee-api.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get PostgreSQL host
*/}}
{{- define "cognee-api.postgresql.host" -}}
{{- if .Values.database.postgresql.host }}
{{- .Values.database.postgresql.host }}
{{- else if .Values.global }}
{{- if .Values.global.externalDatabase }}
{{- if .Values.global.externalDatabase.postgresql }}
{{- if .Values.global.externalDatabase.postgresql.host }}
{{- .Values.global.externalDatabase.postgresql.host }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Get Neo4j host
*/}}
{{- define "cognee-api.neo4j.host" -}}
{{- if .Values.database.neo4j.host }}
{{- .Values.database.neo4j.host }}
{{- else }}
{{- printf "%s-neo4j" .Release.Name }}
{{- end }}
{{- end }}

{{/*
Get Redis host
*/}}
{{- define "cognee-api.redis.host" -}}
{{- if .Values.database.redis.host }}
{{- .Values.database.redis.host }}
{{- else if .Values.global }}
{{- if .Values.global.externalDatabase }}
{{- if .Values.global.externalDatabase.redis }}
{{- if .Values.global.externalDatabase.redis.host }}
{{- .Values.global.externalDatabase.redis.host }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
