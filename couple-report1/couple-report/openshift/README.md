# OpenShift 골격

배포 리소스는 후속 SRE 단계에서 작성합니다. `api/Dockerfile`의 빌드 컨텍스트는 저장소 루트(`.`)를 사용해야 `data/knowledge`를 포함할 수 있습니다.

예정 파일: Namespace/Secret/ConfigMap, Postgres·Qdrant StatefulSet, API·Web Deployment/Service/Route, `tekton/` 파이프라인.

