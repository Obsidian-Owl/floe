{{/*
Expand the name of the chart.
*/}}
{{- define "cube.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "cube.fullname" -}}
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
{{- define "cube.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "cube.labels" -}}
helm.sh/chart: {{ include "cube.chart" . }}
{{ include "cube.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "cube.selectorLabels" -}}
app.kubernetes.io/name: {{ include "cube.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Cube API labels
*/}}
{{- define "cube.api.labels" -}}
{{ include "cube.labels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Cube API selector labels
*/}}
{{- define "cube.api.selectorLabels" -}}
{{ include "cube.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Cube Refresh Worker labels
*/}}
{{- define "cube.refreshWorker.labels" -}}
{{ include "cube.labels" . }}
app.kubernetes.io/component: refresh-worker
{{- end }}

{{/*
Cube Refresh Worker selector labels
*/}}
{{- define "cube.refreshWorker.selectorLabels" -}}
{{ include "cube.selectorLabels" . }}
app.kubernetes.io/component: refresh-worker
{{- end }}

{{/*
Cube Store labels
*/}}
{{- define "cube.cubeStore.labels" -}}
{{ include "cube.labels" . }}
app.kubernetes.io/component: cube-store
{{- end }}

{{/*
Cube Store selector labels
*/}}
{{- define "cube.cubeStore.selectorLabels" -}}
{{ include "cube.selectorLabels" . }}
app.kubernetes.io/component: cube-store
{{- end }}
