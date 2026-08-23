# 역할: 금지 표현 regex 검증 — 잡아야 할 것/통과해야 할 것 (TC-AGENT-004, FR-004 P-1)
import json
import re
from pathlib import Path

PATTERNS_FILE = Path(__file__).resolve().parents[1] / "app" / "prompts" / "banned_patterns.txt"


def _patterns() -> list[re.Pattern]:
    out = []
    for line in PATTERNS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(re.compile(line))
    return out


PATTERNS = _patterns()


def _hit(text: str) -> str | None:
    for p in PATTERNS:
        if p.search(text):
            return p.pattern
    return None


# 잡아야 하는 문장 — 지목·비교·수치·판정
BANNED = [
    "A가 묻는 질문이 줄었어요.",                    # 인물 지목
    "B의 답장이 평소보다 길었어요.",                # 인물 지목
    "형준님이 더 자주 연락했어요.",                 # 지목 + 비교
    "한쪽이 상대보다 말을 많이 걸었어요.",          # 비교
    "누가 더 적극적인지 보여요.",                   # 비교
    "질문이 30% 줄었어요.",                         # 수치 (밴딩 결정)
    "관계 온도 72점이에요.",                        # 점수 (TC-AGENT-004-1)
    "지난주보다 관계가 좋아졌어요.",                # 가치 판단
    "바빠서 답장이 늦어진 것 때문에 그래요.",       # 원인 단정
    "더 자주 연락하세요.",                          # 명령 (TC-AGENT-004-3)
    "두 분은 잘 맞는 편이에요.",                    # 관계 판정
]

# 통과해야 하는 문장 — 의견이 제시한 톤 그대로
ALLOWED = [
    "이번 대화에서는 서로에게 궁금한 걸 묻는 순간들이 자주 보였어요.",
    "이건 서로에 대한 관심이 꾸준히 유지되고 있다는 신호예요.",
    "다음엔 그 질문에 조금 더 깊은 답으로 화답해보면, 대화가 한 단계 더 풍성해질 거예요.",
    "대화의 리듬이 대체로 빠른 편이에요.",
    "표현 방식에 각자의 스타일이 묻어나요.",
    "지난 4주에 비해 서로에게 묻는 순간이 좀 뜸했어요.",   # 기준선 비교는 사람 비교가 아니다
    "바쁜 시기였을 수도, 대화 주제가 옮겨간 걸 수도 있어요.",
    "다음엔 상대 하루에 대해 질문 하나를 더 던져보면 어떨까요.",
]


def test_banned_sentences_are_caught():
    missed = [t for t in BANNED if _hit(t) is None]
    assert not missed, f"못 잡은 문장: {missed}"


def test_allowed_sentences_pass():
    caught = [(t, _hit(t)) for t in ALLOWED if _hit(t)]
    assert not caught, f"오탐: {caught}"


MOCK = Path(__file__).resolve().parents[1] / "mock" / "report_stored.json"


def test_mock_report_text_passes():
    """목 리포트의 LLM 측 문장(관찰·해석·제안)이 금지 표현에 안 걸려야 한다.
    moments[].text 는 코드 생성이라 대상 아님 (수치가 근거)."""
    d = json.loads(MOCK.read_text(encoding="utf-8"))
    texts = []
    for h in d["highlights"]:
        texts.append(h["observation"])
        texts.extend(h["interpretations"])
    texts.extend(sg["text"] for sg in d["suggestions"])
    caught = [(t, _hit(t)) for t in texts if _hit(t)]
    assert not caught, caught


def test_interpretations_are_clauses_not_sentences():
    """API_SPEC §4.2 렌더 규칙: 절이므로 마침표로 끝나지 않는다 (프론트가 이어 붙임)."""
    d = json.loads(MOCK.read_text(encoding="utf-8"))
    for h in d["highlights"]:
        assert len(h["interpretations"]) >= 2
        for c in h["interpretations"]:
            assert not c.rstrip().endswith("."), c
