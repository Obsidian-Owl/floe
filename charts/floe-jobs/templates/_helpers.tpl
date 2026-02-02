{{/*
Expand the name of the chart.
*/}}
{{- define "floe-jobs.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this.
*/}}
{{- define "floe-jobs.fullname" -}}
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
{{- define "floe-jobs.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "floe-jobs.labels" -}}
helm.sh/chart: {{ include "floe-jobs.chart" . }}
{{ include "floe-jobs.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.global.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "floe-jobs.selectorLabels" -}}
app.kubernetes.io/name: {{ include "floe-jobs.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "floe-jobs.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "floe-jobs.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create job labels with job-specific additions
*/}}
{{- define "floe-jobs.jobLabels" -}}
{{ include "floe-jobs.labels" . }}
app.kubernetes.io/component: {{ .jobName }}
{{- end }}

{{/*
Polaris endpoint - auto-discover or use explicit value
*/}}
{{- define "floe-jobs.polarisEndpoint" -}}
{{- if .Values.platform.polarisEndpoint }}
{{- .Values.platform.polarisEndpoint }}
{{- else if .Values.platform.releaseName }}
{{- $ns := .Values.platform.namespace | default .Release.Namespace }}
{{- printf "http://%s-polaris.%s.svc.cluster.local:8181" .Values.platform.releaseName $ns }}
{{- else }}
{{- "" }}
{{- end }}
{{- end }}

{{/*
OTel collector endpoint - auto-discover or use explicit value
*/}}
{{- define "floe-jobs.otelEndpoint" -}}
{{- if .Values.platform.otelEndpoint }}
{{- .Values.platform.otelEndpoint }}
{{- else if .Values.platform.releaseName }}
{{- $ns := .Values.platform.namespace | default .Release.Namespace }}
{{- printf "%s-otel-collector.%s.svc.cluster.local:4317" .Values.platform.releaseName $ns }}
{{- else }}
{{- "" }}
{{- end }}
{{- end }}

{{/*
Merge default security context with job-specific overrides
*/}}
{{- define "floe-jobs.podSecurityContext" -}}
{{- $defaults := .Values.defaults.securityContext }}
{{- $overrides := .jobSecurityContext | default dict }}
{{- mustMergeOverwrite $defaults $overrides | toYaml }}
{{- end }}

{{/*
Merge default container security context with job-specific overrides
*/}}
{{- define "floe-jobs.containerSecurityContext" -}}
{{- $defaults := .Values.defaults.containerSecurityContext }}
{{- $overrides := .jobContainerSecurityContext | default dict }}
{{- mustMergeOverwrite $defaults $overrides | toYaml }}
{{- end }}

{{/*
Merge default resources with job-specific overrides
*/}}
{{- define "floe-jobs.resources" -}}
{{- $defaults := .Values.defaults.resources }}
{{- $overrides := .jobResources | default dict }}
{{- mustMergeOverwrite $defaults $overrides | toYaml }}
{{- end }}
