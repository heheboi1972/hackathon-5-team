# 역할: 1-V1 검증 — e5(intfloat/multilingual-e5-large) 한국어 카톡 문장 임베딩 품질 확인.
#       20문장을 5개 주제 그룹(각 4문장)으로 묶어 임베딩 후 코사인 유사도 행렬을 뽑고,
#       "같은 주제 문장끼리 유사도 상위에 오는가"를 확인한다. (설계 노트 ① 챗봇 top-k 판단의 전제조건)
#
# 사용법 (레포 루트에서):
#   pip install ibm-watsonx-ai --break-system-packages   (이미 설치돼 있으면 생략)
#   python scripts/v1_similarity_test.py
#
# 준비물: 레포 루트의 .env 에 AI_PROVIDER=watsonx, WATSONX_API_KEY / WATSONX_PROJECT_ID 채워져 있어야 함.
#         (docker나 postgres/qdrant는 필요 없음 — 순수 임베딩 API 호출만 함)
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows cp949 콘솔에서도 한글 깨짐 방지
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    """.env 를 아주 단순하게 파싱 (python-dotenv 의존성 없이)."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.split("#", 1)[0].strip().strip('"').strip("'")
    return env


# ---------------------------------------------------------------- 테스트 문장 (5주제 x 4문장)
# 그룹 태그는 우리가 채점할 때만 쓰고, 모델에는 원문 그대로만 넘긴다.
SENTENCES: list[tuple[str, str]] = [
    ("제주도", "우리 저번에 제주도 여행 언제 가기로 했었지?"),
    ("제주도", "제주도 숙소는 게스트하우스로 예약했잖아"),
    ("제주도", "협재 해변 사진 진짜 예쁘게 나왔더라"),
    ("제주도", "다음 달에 진짜 제주도 가는 거 맞지?"),

    ("저녁약속", "오늘 저녁에 뭐 먹을까?"),
    ("저녁약속", "이따 만나서 파스타 먹으러 갈까"),
    ("저녁약속", "저녁 약속 몇 시로 잡을까"),
    ("저녁약속", "새로 생긴 이자카야 가보고 싶어"),

    ("다툼", "아까 그렇게 말해서 좀 서운했어"),
    ("다툼", "네가 연락 늦게 해서 걱정했잖아"),
    ("다툼", "미안해 내가 예민하게 굴었나 봐"),
    ("다툼", "우리 이런 걸로 자주 싸우는 것 같아"),

    ("기념일", "이번 기념일에 뭐 받고 싶어?"),
    ("기념일", "생일 선물로 뭐 사줄지 고민 중이야"),
    ("기념일", "우리 사귄 지 벌써 1년 됐네"),
    ("기념일", "기념일에 특별한 곳 예약해놨어"),

    ("일상안부", "오늘 하루 어땠어?"),
    ("일상안부", "출근길에 비 많이 오더라"),
    ("일상안부", "점심은 먹었어?"),
    ("일상안부", "오늘 회사에서 좀 피곤한 일 있었어"),
]

# 실전 시나리오: 실제 챗봇에 들어올 법한 질문 3개 → query: 접두사로 임베딩해서
# 20개 문장(passage) 중 어떤 게 상위로 뽑히는지 확인 (설계 노트에 나온 실제 예시 포함)
QUERIES: list[str] = [
    "우리 언제 제주도 얘기했지?",
    "저번에 우리 왜 싸웠었지?",
    "우리 기념일에 뭐 하기로 했지?",
]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def main() -> None:
    env = load_env(ENV_PATH)
    provider = env.get("AI_PROVIDER", "mock")
    api_key = env.get("WATSONX_API_KEY", "")
    project_id = env.get("WATSONX_PROJECT_ID", "")
    url = env.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    model_id = env.get("WATSONX_EMBEDDING_MODEL_ID", "intfloat/multilingual-e5-large")

    if provider != "watsonx" or not api_key or not project_id:
        print("⚠️  .env 의 AI_PROVIDER=watsonx 와 WATSONX_API_KEY / WATSONX_PROJECT_ID 가 채워져 있는지 확인해줘.")
        print(f"   현재 값: AI_PROVIDER={provider!r}, WATSONX_API_KEY={'(있음)' if api_key else '(없음)'}, "
              f"WATSONX_PROJECT_ID={'(있음)' if project_id else '(없음)'}")
        sys.exit(1)

    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import Embeddings
    from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames as E

    print(f"임베딩 모델: {model_id}")
    creds = Credentials(url=url, api_key=api_key)
    emb = Embeddings(
        model_id=model_id, credentials=creds, project_id=project_id,
        params={E.TRUNCATE_INPUT_TOKENS: 512, E.RETURN_OPTIONS: {"input_text": False}},
    )

    is_e5 = "e5" in model_id.lower()
    groups = [g for g, _ in SENTENCES]
    texts = [t for _, t in SENTENCES]

    print(f"\n1) 문장 {len(texts)}개 임베딩 중 (passage: 접두사 {'적용' if is_e5 else '미적용'})...")
    passages = [f"passage: {t}" if is_e5 else t for t in texts]
    vectors = emb.embed_documents(passages)
    print("   완료.")

    # ---------------------------------------------------------- ① 그룹 내 vs 그룹 간 유사도
    n = len(texts)
    within_scores: list[float] = []
    cross_scores: list[float] = []
    matrix: list[list[float]] = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            sim = cosine(vectors[i], vectors[j])
            matrix[i][j] = sim
            if groups[i] == groups[j]:
                within_scores.append(sim)
            else:
                cross_scores.append(sim)

    print("\n2) 문장별 상위 3개 유사 문장 (같은 그룹이면 ✓, 다르면 ✗):")
    hits, total = 0, 0
    for i in range(n):
        ranked = sorted(
            [(j, matrix[i][j]) for j in range(n) if j != i],
            key=lambda x: x[1], reverse=True,
        )[:3]
        print(f"\n[{groups[i]}] {texts[i]}")
        for rank, (j, score) in enumerate(ranked, start=1):
            mark = "✓" if groups[j] == groups[i] else "✗"
            print(f"   {rank}. {mark} ({score:.3f}) [{groups[j]}] {texts[j]}")
            total += 1
            if mark == "✓":
                hits += 1

    avg_within = sum(within_scores) / len(within_scores) if within_scores else 0.0
    avg_cross = sum(cross_scores) / len(cross_scores) if cross_scores else 0.0

    print("\n" + "=" * 60)
    print("[요약 1] 그룹 내부 평균 유사도 vs 그룹 간 평균 유사도")
    print(f"  그룹 내부(같은 주제)  평균: {avg_within:.3f}")
    print(f"  그룹 간(다른 주제)    평균: {avg_cross:.3f}")
    print(f"  차이(gap):            {avg_within - avg_cross:.3f}")
    print(f"[요약 2] top-3 안에 같은 그룹 문장이 들어온 비율: {hits}/{total} ({hits/total:.0%})")
    print("=" * 60)
    print("판단 기준 (참고): gap이 뚜렷하고(대략 0.05~0.1 이상) top-3 적중률이 높을수록")
    print("  '임베딩이 의미로 구분하고 있다'고 볼 수 있음. gap이 작고 적중률도 낮으면")
    print("  top-1만 보여주는 방식은 위험 → top-3 나열형 + threshold 처리가 더 필요하다는 근거가 됨.")

    # ---------------------------------------------------------- ② 실전 질문 → 검색 시나리오
    print("\n3) 실전 시나리오: 질문(query:) → 20문장 중 상위 3개 매칭")
    q_vectors = [emb.embed_query(f"query: {q}" if is_e5 else q) for q in QUERIES]
    for q, qv in zip(QUERIES, q_vectors):
        ranked = sorted(range(n), key=lambda j: cosine(qv, vectors[j]), reverse=True)[:3]
        print(f"\nQ: {q}")
        for rank, j in enumerate(ranked, start=1):
            print(f"   {rank}. ({cosine(qv, vectors[j]):.3f}) [{groups[j]}] {texts[j]}")

    # ---------------------------------------------------------- 저장 (팀 공유용)
    out_path = REPO_ROOT / "scripts" / "v1_similarity_result.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["문장"] + [f"{g}:{t}" for g, t in SENTENCES])
        for i in range(n):
            w.writerow([f"{groups[i]}:{texts[i]}"] + [f"{matrix[i][j]:.4f}" for j in range(n)])
    print(f"\n전체 행렬은 여기 저장했어: {out_path}")


if __name__ == "__main__":
    main()
