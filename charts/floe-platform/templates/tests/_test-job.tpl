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
      "testPath" "tests/e2e/"
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
  testPath        — Pytest collection path. Defaults to "tests/e2e/" for
                    product E2E runners; bootstrap callers set
                    "tests/bootstrap/" explicitly.
*/}}
{{- define "floe-platform.testJob" -}}
{{- $context := .context }}
{{- $suite := .suite }}
{{- $pytestMarker := .pytestMarker }}
{{- $serviceAccount := .serviceAccount }}
{{- $artifactPrefix := .artifactPrefix }}
{{- $testPath := default "tests/e2e/" .testPath }}
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
          # pytest writes .pyc caches, html reports, and json-report files
          # to /app during execution — readOnlyRootFilesystem is not practical.
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop:
              - ALL
            readOnlyRootFilesystem: false
            runAsNonRoot: true
            runAsUser: 1000
          args:
            - "--tb=short"
            - "-v"
            - "--color=yes"
            - {{ $testPath | quote }}
            - "-m"
            - {{ $pytestMarker | quote }}
            - "--junitxml=/artifacts/{{ $artifactPrefix }}-results.xml"
            - "--html=/artifacts/{{ $artifactPrefix }}-report.html"
            - "--self-contained-html"
            - "--json-report"
            - "--json-report-file=/artifacts/{{ $artifactPrefix }}-report.json"
            - "--log-cli-level=INFO"
          env:
            {{- include "floe-platform.testRunner.contractEnv" $context | nindent 12 }}
            - name: POSTGRES_USER
              value: floe
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.postgresql.secretName" $context }}
                  key: postgresql-password
            - name: MINIO_ENDPOINT
              value: "http://{{ include "floe-platform.minio.fullname" $context }}:9000"
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
              value: "http://{{ include "floe-platform.polaris.fullname" $context }}:{{ $context.Values.polaris.service.port | default 8181 }}/api/catalog"
            - name: POLARIS_CREDENTIAL
              valueFrom:
                secretKeyRef:
                  name: {{ include "floe-platform.polaris.credentialSecretName" $context }}
                  key: POLARIS_CREDENTIAL
            - name: POLARIS_WAREHOUSE
              value: {{ include "floe-platform.polaris.warehouse" $context | quote }}
            - name: POLARIS_SCOPE
              value: "PRINCIPAL_ROLE:ALL"
            - name: JAEGER_URL
              value: "http://{{ include "floe-platform.jaeger.queryName" $context }}:16686"
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://{{ include "floe-platform.otel.fullname" $context }}:4317"
            - name: OTEL_SERVICE_NAME
              value: "floe-test-runner-{{ $suite }}"
            - name: PYTHONPATH
              value: "/app:/app/testing"
            - name: PYTHONUNBUFFERED
              value: "1"
          resources:
            {{- toYaml $context.Values.tests.resources | nindent 12 }}
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            {{- if $context.Values.tests.artifacts.enabled }}
            - name: artifacts
              mountPath: /artifacts
            {{- end }}
      volumes:
        - name: tmp
          emptyDir: {}
        {{- if $context.Values.tests.artifacts.enabled }}
        - name: artifacts
          persistentVolumeClaim:
            claimName: {{ $context.Values.tests.artifacts.pvcName }}
        {{- end }}
{{- end }}
