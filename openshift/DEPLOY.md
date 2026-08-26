# 재배포 절차 (해찬)

api/web 코드가 바뀐 뒤 클러스터에 반영하는 전체 순서. 매번 이 문서 순서대로 하면 된다 —
아래 각 단계는 실제로 문제가 났던 지점들이라 순서를 건너뛰면 다시 걸린다.

## 0. 로그인 확인

토큰은 대략 하루 지나면 만료된다. 아무 `oc` 명령이나 `Unauthorized` 를 내면 이것부터.

```
oc login --token=sha256~... --server=https://c100-e.us-south.containers.cloud.ibm.com:32294
oc project couple-report
```

## 1. git 상태 확인 — 배포와 소스가 일치하는지 먼저 본다

재배포가 필요한지 판단하는 기준은 "로컬에 새 커밋이 있다"가 아니라
**"클러스터에 떠 있는 이미지의 소스 커밋 ≠ 지금 main"** 이다.

```bash
git fetch --prune
git log --oneline HEAD..origin/main   # 새 커밋 있으면 pull
git pull origin main

# 지금 배포된 이미지가 어느 커밋인지 (직전 PipelineRun 결과)
oc get pipelinerun -n couple-report --sort-by=.status.startTime -o json | \
  python -c "import json,sys; d=json.load(sys.stdin)['items'][-1]; print(d['metadata']['name'], d['status']['results'])"
```

두 값이 다르면(대개 다르다 — 팀원이 계속 머지하니까) 3번으로.

## 2. PR이 있다면: 머지 전에 mergeable 확인

```bash
gh pr view <번호> --json mergeable,mergeStateStatus
```

`CONFLICTING` 이 나오면 **rebase 로 해결한다** (강제로 밀어붙이지 않는다):

```bash
git checkout <브랜치>
git rebase origin/main     # 이미 main에 들어간 커밋은 "skipped previously applied commit" 으로 자동 제외됨
git push --force-with-lease origin <브랜치>
```

`--force-with-lease` 는 내가 마지막으로 본 원격 상태 이후 남이 그 브랜치를 안 건드렸을 때만 push된다 —
이 브랜치는 혼자 작업하는 브랜치일 때만 이 흐름을 쓴다.

```bash
gh pr merge <번호> --squash --delete-branch
git checkout main && git pull origin main
```

## 3. (선택) 로컬 검증

배포 전에 최소한 이거라도:

```bash
cd api && python -m pytest tests/ -q
```

기존 PostgreSQL PVC에는 `postgres/init.sql`이 다시 실행되지 않으므로 새 컬럼이 추가된
배포에서는 저장소의 마이그레이션을 먼저 적용한다. 각 파일은 재실행 가능해야 한다.

```bash
oc exec -i postgres-0 -n couple-report -- \
  psql -v ON_ERROR_STOP=1 -U couple -d couple_report \
  < postgres/migrations/001_add_couples_first_met_at.sql
```

## 4. 빌드 파이프라인 실행

```bash
oc create -f openshift/tekton/30-pipelinerun.yaml
```

`generateName` 이라 매번 새 이름(`couple-report-api-build-xxxxx`)이 나온다 — 아래 확인 명령에 그 이름을 넣는다.

```bash
# 진행 상황
oc get pipelinerun -n couple-report

# 완료까지 기다리기 (성공/실패 조건이 될 때까지)
oc get pipelinerun <이름> -o jsonpath='{.status.conditions[0].status}'
```

실패하면 어느 Task 가 실패했는지부터:

```bash
oc get taskrun -l tekton.dev/pipelineRun=<이름> -o json | \
  python -c "import json,sys
for t in json.load(sys.stdin)['items']:
    c=t['status']['conditions'][0]
    print(t['metadata']['labels'].get('tekton.dev/pipelineTask'),'->',c['status'],c.get('reason'))"

oc logs -l tekton.dev/pipelineTask=<build 또는 build-web> --tail=40 --all-containers
```

## 5. 롤아웃

파이프라인이 성공해도 **파드가 자동으로 새 이미지를 받지 않는다** — `imagePullPolicy: Always` 라
같은 `:latest` 태그를 다시 밀어도 재시작을 걸어야 새 이미지를 당겨온다.

```bash
oc rollout restart deploy/couple-report-api deploy/couple-report-web -n couple-report
oc rollout status deploy/couple-report-api -n couple-report --timeout=180s
oc rollout status deploy/couple-report-web -n couple-report --timeout=180s
```

## 6. 검증 — "떴다"가 아니라 "맞는 게 떴다"를 확인

```bash
# 파드 4개 다 Running 인지
oc get pods -n couple-report

# 배포된 이미지의 소스 커밋이 방금 pull한 main과 같은지 (이게 핵심 — 안 맞으면 4번부터 다시)
oc get pipelinerun <4번 이름> -o jsonpath='{.status.results[0].value}'
git rev-parse HEAD

# 프론트·백엔드·프록시 연결까지
WEB=$(oc get route couple-report-web -o jsonpath='{.spec.host}')
curl -s -o /dev/null -w "웹: %{http_code}\n" "https://$WEB/"
curl -s "https://$WEB/health/ready"   # nginx 경유로 백엔드까지 확인 — {"postgres":true,"qdrant":true,"watsonx":true} 여야 함
```

## 절대 하면 안 되는 것

- **`oc apply -f openshift/00-namespace-secret.yaml` 를 하지 않는다.** 이 파일에는 Secret 이 없다
  (2026-08-25에 실제로 지워서 겪은 사고 — 빈 `stringData` 템플릿이 apply 때마다 실제 키를 덮었다).
  ConfigMap 부분만 apply 대상이고, Secret 은 `oc create`/`oc patch` 로만 다룬다.
- `git push --force`(리스 없이) 는 쓰지 않는다. 항상 `--force-with-lease`.
- 롤아웃 후 파드 `Running` 만 보고 끝내지 않는다 — 6번의 소스 커밋 비교까지 해야
  "예전 이미지가 아직 떠 있는데 Running 이라 문제없어 보이는" 상태를 놓치지 않는다.
