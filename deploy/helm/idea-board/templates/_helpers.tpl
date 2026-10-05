{{- define "idea-board.fullname" -}}
{{- .Release.Name | trunc 50 | trimSuffix "-" -}}
{{- end -}}

{{- define "idea-board.labels" -}}
app.kubernetes.io/name: idea-board
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "idea-board.selectorLabels" -}}
app.kubernetes.io/name: idea-board
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
