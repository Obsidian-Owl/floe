{{/*
Shared E2E test runner Job template.

The standard (job-e2e.yaml) and destructive (job-e2e-destructive.yaml)
runners differ only in four places — Job name, test-type label, runner
ServiceAccount, pytest marker, and artifact filename prefix. Before this
partial was extracted, both files were ~140 lines of 95%-identical YAML;
every bug fix had to be applied twice and drift was near-certain. This
template is the single source of truth.

Usage:
  {{- include "floe-platform.testJob" (dict
      "context" .
      "suite" "e2e"
      "pytestMarker" "not destructive"
      "serviceAccount" (include "floe-platform.testRunner.saName" .)
      "artifactPrefix" "e2e"
      ) }}

Fields:
  context         — Top-level chart context (`.`). Required for helper
                    calls and .Values / .Release access.
  suite           — Human-readable suite identifier used for the Job
                    `metadata.name` (`floe-test-<suite>`), the
                    `test-type` label, and the OTel service name suffix.
                    Use "e2e" for the non-destructive runner,
                    "e2e-destructive" for the destructive runner.
  pytestMarker    — Value for `pytest -m`. Use "not destructive" to
                    exclude destructive tests; "destructive" to include
                    only destructive tests.
  serviceAccount  — Rendered ServiceAccount name. Callers resolve the
                    helper themselves so the template can stay agnostic
                    about which SA a given suite uses.
  artifactPrefix  — Filename prefix for junitxml/html/json-report
                    artifacts. Typically matches `suite`.
*/}}
{{- define "floe-platform.testJob" -}}
{{- $context := .context }}
{{- $suite := .suite }}
{{- $pytestMarker := .pytestMarker }}
{{- $serviceAccount := .serviceAccount }}
{{- $artifactPrefix := .artifactPrefix }}
{{- $polaris := include "floe-platform.polaris.fullname" $context }}
{{- $minio := include "floe-platform.minio.fullname" $context }}
{{- $postgres := include "floe-platform.postgresql.host" $context }}
{{- $dagsterWeb := include "floe-platform.dagster.webserverName" $context }}
{{- $marquez := include "floe-platform.marquez.fullname" $context }}
{{- $otel := include "floe-platform.otel.fullname" $context }}
apiVersion: batch/v1
kind: Job
metadata:
  name: floe-test-{{ $suite }}
  namespace: {{ $context.Release.Namespace }}
  labels:
    {{- include "floe-platform.labels" $context | nindent 4 }}
    app.kubernetes.io/component: test-runner
    test-type: {{ $suite }}
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 3600
  template:
    metadata:
      labels:
        {{- include "floe-platform.selectorLabels" $context | nindent 8 }}
        app.kubernetes.io/component: test-runner
        test-type: {{ $suite }}
    spec:
      restartPolicy: Never
      serviceAccountName: {{ $serviceAccount }}
      securityContext:
        {{- include "floe-platform.podSecurityContext" $context | nindent 8 }}
      containers:
        - name: test-runner
          image: "{{ $context.Values.tests.image.repository }}:{{ $context.Values.tests.image.tag }}"
          imagePullPolicy: {{ $context.Values.tests.image.pullPolicy }}
          securityContext:
            {{- include "floe-platform.containerSecurityContext" $context | nindent 12 }}
          args:
            - "--tb=short"
            - "-v"
            - "--color=yes"
            - "tests/e2e/"
            - "-m"
            - {{ $pytestMarker | quote }}
            - "--junitxml=/artifacts/{{ $artifactPrefix }}-results.xml"
            - "--html=/artifacts/{{ $artifactPrefix }}-report.html"
            - "--self-contained-html"
            - "--json-report"
            - "--json-report-file=/artifacts/{{ $artifactPrefix }}-report.json"
            - "--log-cli-level=INFO"
          env:
            - name: INTEGRATION_TEST_HOST
              value: "k8s"
            - name: POSTGRES_HOST
              value: {{ $postgres | quote }}
            - name: POSTGRES_PORT
              value: {{ include "floe-platform.postgresql.port" $context | quote }}
            - name: POSTGRES_USER
              value: floe
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.postgresql.secretName" $context }}
                  key: postgresql-password
            - name: MINIO_ENDPOINT
              value: "http://{{ $minio }}:9000"
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.minio.secretName" $context }}
                  key: root-user
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.minio.secretName" $context }}
                  key: root-password
            - name: AWS_REGION
              value: us-east-1
            - name: POLARIS_URI
              value: "http://{{ $polaris }}:{{ $context.Values.polaris.service.port | default 8181 }}/api/catalog"
            - name: POLARIS_CREDENTIAL
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.polaris.credentialSecretName" $context }}
                  key: POLARIS_CREDENTIAL
            - name: POLARIS_WAREHOUSE
              value: {{ include "floe-platform.polaris.warehouse" $context | quote }}
            - name: POLARIS_SCOPE
              value: "PRINCIPAL_ROLE:ALL"
            - name: POLARIS_HOST
              value: {{ $polaris | quote }}
            - name: POLARIS_MANAGEMENT_HOST
              value: {{ $polaris | quote }}
            - name: MINIO_HOST
              value: {{ $minio | quote }}
            - name: MINIO_CONSOLE_HOST
              value: {{ $minio | quote }}
            - name: MARQUEZ_HOST
              value: {{ $marquez | quote }}
            - name: DAGSTER_HOST
              value: {{ $dagsterWeb | quote }}
            - name: DAGSTER_WEBSERVER_HOST
              value: {{ $dagsterWeb | quote }}
            - name: OTEL_HOST
              value: {{ $otel | quote }}
            - name: OTEL_COLLECTOR_GRPC_HOST
              value: {{ $otel | quote }}
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://{{ $otel }}:4317"
            - name: OTEL_SERVICE_NAME
              value: "floe-test-runner-{{ $suite }}"
            - name: PYTHONPATH
              value: "/app:/app/testing"
            - name: PYTHONUNBUFFERED
              value: "1"
          resources:
            {{- toYaml $context.Values.tests.resources | nindent 12 }}
          {{- if $context.Values.tests.artifacts.enabled }}
          volumeMounts:
            - name: artifacts
              mountPath: /artifacts
          {{- end }}
      {{- if $context.Values.tests.artifacts.enabled }}
      volumes:
        - name: artifacts
          persistentVolumeClaim:
            claimName: {{ $context.Values.tests.artifacts.pvcName }}
      {{- end }}
{{- end }}
