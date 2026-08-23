"""
결정론적 지표 계산 (기획서 §3, §7.1).  LLM 없음.

파서 출력(Message 리스트) → 세션 분할 → 주간 지표 → 기준선 비교 → 이상치.

사용:
    from kakao_parser import parse_export, validate_couple
    from metrics import build_weekly_metrics
    msgs = parse_export(open(path, "rb").read())
    name_a, name_b = validate_couple(msgs)
    weeks = build_weekly_metrics(msgs, name_a, name_b)   # list[dict], §7.1 구조, 주 오름차순

상수는 전부 상단에. V2 검증(세션 기준) 은 SESSION_GAP_MIN 만 바꿔 재실행.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, date, timedelta

try:
    from .kakao_parser import Message
except ImportError:  # 단독 실행(python metrics.py) 호환
    from kakao_parser import Message

# ---------------------------------------------------------------- 상수 (§3)

SESSION_GAP_MIN = 30          # 이 이상 간격이면 새 세션           [검증 대기 V2]
BASELINE_WEEKS_TREND = 4      # 추이형 지표: 직전 N주 평균
BASELINE_WEEKS_OUTLIER = 8    # 이상치형 지표: 직전 N주 분포
IQR_K = 1.5                   # 이상치 = Q1 - K*IQR 미만 / Q3 + K*IQR 초과
MAX_OUTLIERS_PER_WEEK = 3     # 지표당 주당 최대 보고 건수
MIN_SAMPLES_FOR_IQR = 20      # 분포가 이보다 작으면 이상치 판정 보류
REPLY_GAP_MAX_MIN = 12 * 60   # 이 이상 지연은 수면 등으로 보고 답장 간격에서 제외
OUTLIER_MIN_RATIO = 3.0       # 이상치 보고 조건: 기준선 중앙값의 N배 이상(또는 1/N 이하)
USE_LOG_IQR = True            # 오른쪽 꼬리 분포(답장 간격·세션 길이) → log 변환 후 IQR

# ---------------------------------------------------------------- 세션


@dataclass
class Session:
    session_id: int
    started_at: datetime
    ended_at: datetime
    initiator: str             # 표시용 (돌아보기 세션 목록). 지표 아님 — ISSUE A2
    messages: list[Message]

    @property
    def msg_count(self) -> int:
        return len(self.messages)


def split_sessions(msgs: list[Message], gap_min: int = SESSION_GAP_MIN) -> list[Session]:
    """시간순 정렬 후 간격 >= gap_min 이면 세션을 끊는다. 모든 msg_type 포함.
    session_id = 첫 메시지 sent_at 의 epoch 초 (결정론). 재업로드로 다시 나눠도 같은 세션은 같은 ID."""
    msgs = sorted(msgs, key=lambda m: m.sent_at)
    sessions: list[Session] = []
    cur: list[Message] = []
    gap = timedelta(minutes=gap_min)
    for m in msgs:
        if cur and (m.sent_at - cur[-1].sent_at) >= gap:
            sessions.append(_close(cur))
            cur = []
        cur.append(m)
    if cur:
        sessions.append(_close(cur))
    return sessions


def _close(msgs: list[Message]) -> Session:
    sid = int(msgs[0].sent_at.timestamp())
    return Session(sid, msgs[0].sent_at, msgs[-1].sent_at, msgs[0].sender, msgs)


# ---------------------------------------------------------------- 주 단위 버킷


def week_start_of(d: date) -> date:
    return d - timedelta(days=d.weekday())  # 월요일


def _bucket_by_week(sessions: list[Session]) -> dict[date, list[Session]]:
    """세션은 시작 시각의 주에 귀속."""
    buckets: dict[date, list[Session]] = defaultdict(list)
    for s in sessions:
        buckets[week_start_of(s.started_at.date())].append(s)
    return dict(sorted(buckets.items()))


# ---------------------------------------------------------------- 원시 관측값 (세션 단위)


@dataclass
class RawWeek:
    week_start: date
    sessions: list[Session]
    # 추이형 원시값
    text_msgs: dict[str, list[Message]]    # who -> text 메시지
    by_weekday: list[int]                  # 0=월 … 6=일, 전체 메시지 수
    by_hour: list[int]                     # 0~23
    # 이상치형 원시값
    reply_gaps: list[tuple[str, str, int, datetime, float]]   # (kind, who, session_id, at, gap_min)
                                                                 # kind: in_session | resume
    session_lengths: list[tuple[int, datetime, int]]     # (session_id, at, msg_count)


def _observe(week_start: date, sessions: list[Session], a: str, b: str) -> RawWeek:
    text = {a: [], b: []}
    by_wd = [0] * 7
    by_hr = [0] * 24
    gaps: list[tuple[str, int, datetime, float]] = []
    lens: list[tuple[int, datetime, int]] = []
    prev: Message | None = None   # 세션 경계를 넘어 유지
    for s in sessions:
        lens.append((s.session_id, s.started_at, s.msg_count))
        for i, m in enumerate(s.messages):
            by_wd[m.sent_at.weekday()] += 1
            by_hr[m.sent_at.hour] += 1
            if m.msg_type == "text":
                text[m.sender].append(m)
            # 답장 간격: 발화자가 바뀐 첫 메시지까지. 두 종류를 분리해 각자 기준선을 갖게 한다.
            #   in_session: 대화 중 답장 (세션 내)
            #   resume    : 대화가 끊긴 뒤 *상대가* 재개한 지연 (세션 경계). 같은 사람이 다시 말 건 건 답장이 아님.
            if prev is not None and prev.sender != m.sender:
                gap = (m.sent_at - prev.sent_at).total_seconds() / 60
                kind = "resume" if i == 0 else "in_session"
                if kind == "in_session" or gap <= REPLY_GAP_MAX_MIN:
                    gaps.append((kind, m.sender, s.session_id, m.sent_at, gap))
            prev = m
    return RawWeek(week_start, sessions, text, by_wd, by_hr, gaps, lens)


# ---------------------------------------------------------------- 주간 지표


def _ratio(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def _median(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 1) if xs else None


def _trend_metrics(rw: RawWeek, a: str, b: str) -> dict:
    """커플 합산(couple) + 사람별(a/b). 응답에는 couple 과 요청자 것(mine)만 나간다 — ISSUE B3.
    couple 은 사람별 값의 평균이 아니라 두 사람 메시지를 **합친 뒤** 계산한 값."""
    both = rw.text_msgs[a] + rw.text_msgs[b]
    return {
        "question_rate": {
            "couple": _ratio(sum(m.is_question for m in both), len(both)),
            "a": _ratio(sum(m.is_question for m in rw.text_msgs[a]), len(rw.text_msgs[a])),
            "b": _ratio(sum(m.is_question for m in rw.text_msgs[b]), len(rw.text_msgs[b])),
        },
        "message_length_median": {
            "couple": _median([m.body_len for m in both]),
            "a": _median([m.body_len for m in rw.text_msgs[a]]),
            "b": _median([m.body_len for m in rw.text_msgs[b]]),
        },
        # A2 로 initiation_ratio 가 빠진 자리. 이상치형으로도 계속 쓰인다(세션 단위 분포)
        "reply_gap_median_min": _gap_medians(rw, "in_session", a, b),
    }


def _gap_medians(rw: RawWeek, kind: str, a: str, b: str) -> dict:
    """couple = 양방향 전체의 중앙값."""
    def med(who=None):
        return _median([g for k, w, _, _, g in rw.reply_gaps if k == kind and (who is None or w == who)])
    return {"couple": med(), "a": med(a), "b": med(b)}


def _summary_extras(rw: RawWeek, a: str, b: str) -> dict:
    """§7.2 summary 에 들어갈 현황값 중 추이형에 없는 것.
    summary = metrics(현재값) + 여기. 따라서 reply_gap 은 승격 후에도 summary 에 그대로 남는다."""
    return {
        "resume_delay_median_min": _gap_medians(rw, "resume", a, b),
        "session_length_median": _median([n for _, _, n in rw.session_lengths]),
        "activity": _activity(rw),
    }


def _activity(rw: RawWeek) -> dict:
    """활발한 요일·시간대 (커플 합산, 복호화·LLM 없음). 메시지가 없으면 top 은 None."""
    has = sum(rw.by_weekday) > 0
    return {
        "top_weekday": max(range(7), key=lambda i: rw.by_weekday[i]) if has else None,
        "top_hour": max(range(24), key=lambda i: rw.by_hour[i]) if has else None,
        "by_weekday": list(rw.by_weekday),
        "by_hour": list(rw.by_hour),
    }


# ---------------------------------------------------------------- 감성 단어 "내 단어" (FR-002 sentiment)
# 사전(couple_lexicon)은 코드 밖에서 온다: {term: (canonical, polarity)}. 여기서는 세기만 한다 (P-2).
# 부정어가 앞 2토큰 안에 있거나 뒤에 "지 않/지 마" 가 붙으면 해당 등장은 제외 (뒤집지 않음).

_NEGATORS = {"안", "못", "별로", "전혀"}
_NEG_SUFFIX = ("지않", "지마", "지않아", "지마라")
TERM_MIN_COUNT = 3   # 이 미만은 카드에 표시하지 않음


def count_terms(msgs: list[Message], lexicon: dict[str, tuple[str, str]]) -> dict[tuple[str, str, str], int]:
    """
    → {(sender, canonical, polarity): count}.  polarity 는 pos|neg 만 (neutral·exclude 는 세지 않음).
    msgs 는 한 주치. sender 는 원본 이름 그대로 (호출자가 a/b 매핑).
    """
    out: dict[tuple[str, str, str], int] = defaultdict(int)
    for m in msgs:
        if m.msg_type != "text" or not m.tokens:
            continue
        toks = m.tokens
        for i, t in enumerate(toks):
            hit = lexicon.get(t)
            if not hit:
                continue
            canonical, pol = hit
            if pol not in ("pos", "neg"):
                continue
            if any(x in _NEGATORS for x in toks[max(0, i - 2):i]):
                continue
            nxt = "".join(toks[i + 1:i + 3])
            if nxt.startswith(_NEG_SUFFIX):
                continue
            out[(m.sender, canonical, pol)] += 1
    return dict(out)


def top_terms(counts: dict[tuple[str, str, str], int], sender: str, k: int = 3) -> dict:
    """한 사람의 pos/neg 상위 k. TERM_MIN_COUNT 미만 제외. → {"pos": [{canonical, count}], "neg": [...]}"""
    res = {"pos": [], "neg": []}
    for (who, canonical, pol), c in counts.items():
        if who == sender and c >= TERM_MIN_COUNT:
            res[pol].append({"canonical": canonical, "count": c})
    for pol in res:
        res[pol] = sorted(res[pol], key=lambda x: (-x["count"], x["canonical"]))[:k]
    return res


# ---------------------------------------------------------------- 기준선 비교 (추이형)


def _attach_baseline(weeks: list[dict], key: str, who: str, history: list[dict]) -> None:
    """history = 직전 BASELINE_WEEKS_TREND 주의 metrics dict 들.
    who ∈ {"couple", "a", "b"}. `comparable` 은 **couple 기준**으로만 정해진다 —
    리포트 문장·하이라이트가 couple 값만 보기 때문 (ISSUE B3)."""
    cur = weeks[-1]["metrics"][key]
    vals = [h["metrics"][key][who] for h in history if h["metrics"][key][who] is not None]
    ok = len(history) >= BASELINE_WEEKS_TREND and bool(vals) and cur[who] is not None
    if not ok:
        cur[f"baseline_{who}"] = None
        cur[f"delta_{who}"] = None
    else:
        base = round(statistics.mean(vals), 3)
        cur[f"baseline_{who}"] = base
        cur[f"delta_{who}"] = round(cur[who] - base, 3)
    if who == "couple":
        cur["comparable"] = ok


# ---------------------------------------------------------------- 에이전트 입력 밴딩 (ISSUE B3)
# LLM 은 숫자를 보지 않는다. 코드가 delta 를 방향·정도로 바꿔서 넘긴다 (P-2 결정론).
# "누가 몇 %" 가 프롬프트에 들어갈 길 자체를 없애는 장치 — 수치는 타임라인 그래프가 보여준다.

BAND_STEADY = 0.15    # 기준선 대비 변화율이 이 미만이면 "그대로"
BAND_SLIGHT = 0.35    # 이 미만이면 "조금", 이상이면 "뚜렷하게"


def band(value: float | None, baseline: float | None) -> dict | None:
    """(couple 값, couple 기준선) → {direction: up|down|steady, magnitude: slight|clear}.
    비교 불가면 None. magnitude 는 direction != steady 일 때만 의미가 있다."""
    if value is None or not baseline:
        return None
    ratio = abs(value - baseline) / abs(baseline)
    if ratio < BAND_STEADY:
        return {"direction": "steady", "magnitude": "slight"}
    return {
        "direction": "up" if value > baseline else "down",
        "magnitude": "slight" if ratio < BAND_SLIGHT else "clear",
    }


def agent_metric_input(metrics: dict) -> list[dict]:
    """해석·제안 에이전트에 넘길 입력. **숫자도 사람별 값도 넘기지 않는다**.
    변화가 없는(steady) 지표와 비교 불가 주차는 애초에 후보가 아니라 제외."""
    out = []
    for key, m in metrics.items():
        if not m.get("comparable"):
            continue
        b = band(m.get("couple"), m.get("baseline_couple"))
        if b is None or b["direction"] == "steady":
            continue
        out.append({"metric": key, **b})
    return out


# ---------------------------------------------------------------- 이상치 (이상치형)


def _iqr_bounds(xs: list[float]) -> tuple[float, float, float] | None:
    """(lo, hi, median) 을 원 단위로 반환. USE_LOG_IQR 이면 log 공간에서 IQR 계산 후 역변환."""
    if len(xs) < MIN_SAMPLES_FOR_IQR:
        return None
    med = statistics.median(xs)
    if USE_LOG_IQR:
        ys = [math.log1p(x) for x in xs]
        q = statistics.quantiles(ys, n=4)
        iqr = q[2] - q[0]
        lo, hi = math.expm1(q[0] - IQR_K * iqr), math.expm1(q[2] + IQR_K * iqr)
    else:
        q = statistics.quantiles(xs, n=4)
        iqr = q[2] - q[0]
        lo, hi = q[0] - IQR_K * iqr, q[2] + IQR_K * iqr
    # 의미 있는 이상치만: 기준선 중앙값 대비 N배 이상 / 이하
    hi = max(hi, med * OUTLIER_MIN_RATIO)
    lo = min(lo, med / OUTLIER_MIN_RATIO) if med > 0 else lo
    return lo, hi, med


def _outliers(rw: RawWeek, history: list[RawWeek], a: str, b: str) -> list[dict]:
    out: list[dict] = []
    if len(history) < 1:
        return out

    # 답장 간격: (종류 × 사람) 별 분포
    for kind, metric in (("in_session", "reply_gap"), ("resume", "resume_delay")):
        for who in (a, b):
            base = [g for h in history for (k, w, _, _, g) in h.reply_gaps if k == kind and w == who]
            bounds = _iqr_bounds(base)
            if not bounds:
                continue
            lo, hi, med = bounds
            cands = []
            for (k, w, sid, at, g) in rw.reply_gaps:
                if k != kind or w != who:
                    continue
                if g > hi:
                    cands.append((g / max(hi, 1e-9), "high", sid, at, g))
                elif g < lo:
                    cands.append((lo / max(g, 1e-9), "low", sid, at, g))
            cands.sort(reverse=True)
            for _, direction, sid, at, g in cands[:MAX_OUTLIERS_PER_WEEK]:
                out.append({
                    "metric": metric,
                    "who": "a" if who == a else "b",
                    "session_id": sid,
                    "at": at.isoformat(),
                    "value_min": round(g, 1),
                    "baseline_median_min": round(med, 1),
                    "direction": direction,
                })

    # 세션 길이: 커플 합산 분포
    base = [n for h in history for (_, _, n) in h.session_lengths]
    bounds = _iqr_bounds(base)
    if bounds:
        lo, hi, med = bounds
        cands = []
        for (sid, at, n) in rw.session_lengths:
            if n > hi:
                cands.append((n - hi, "high", sid, at, n))
            elif n < lo:
                cands.append((lo - n, "low", sid, at, n))
        cands.sort(reverse=True)
        for _, direction, sid, at, n in cands[:MAX_OUTLIERS_PER_WEEK]:
            out.append({
                "metric": "session_length",
                "session_id": sid,
                "at": at.isoformat(),
                "value": n,
                "baseline_median": round(med, 1),
                "direction": direction,
            })
    return out


# ---------------------------------------------------------------- 진입점


def build_weekly_metrics(
    msgs: list[Message], name_a: str, name_b: str,
    gap_min: int = SESSION_GAP_MIN, events: dict[date, list[str]] | None = None,
) -> list[dict]:
    """
    §7.1 `weekly_metrics.metrics` 구조의 dict 를 주 오름차순으로 반환.
    events: {week_start: ["생일", ...]}  (로드맵 — 기념일 배지)
    """
    sessions = split_sessions(msgs, gap_min)
    buckets = _bucket_by_week(sessions)
    raws: list[RawWeek] = []
    out: list[dict] = []

    for wk, sess in buckets.items():
        rw = _observe(wk, sess, name_a, name_b)
        week = {
            "week_start": wk.isoformat(),
            "data_weeks_available": len(raws) + 1,
            "baseline_weeks": BASELINE_WEEKS_TREND,
            "session_count": len(sess),
            "message_count": sum(s.msg_count for s in sess),
            "metrics": _trend_metrics(rw, name_a, name_b),
            "summary_extras": _summary_extras(rw, name_a, name_b),
            "outliers": [],
            "context": {"events": (events or {}).get(wk, [])},
        }
        out.append(week)

        history = out[-1 - BASELINE_WEEKS_TREND:-1]
        for key in ("question_rate", "message_length_median", "reply_gap_median_min"):
            for who in ("couple", "a", "b"):
                _attach_baseline(out, key, who, history)

        week["outliers"] = _outliers(rw, raws[-BASELINE_WEEKS_OUTLIER:], name_a, name_b)
        raws.append(rw)

    return out


# ---------------------------------------------------------------- CLI


if __name__ == "__main__":
    import sys, json
    try:
        from .kakao_parser import parse_export, validate_couple
    except ImportError:
        from kakao_parser import parse_export, validate_couple

    data = open(sys.argv[1], "rb").read()
    gap = int(sys.argv[2]) if len(sys.argv) > 2 else SESSION_GAP_MIN
    msgs = parse_export(data)
    try:
        a, b = validate_couple(msgs)
    except ValueError as e:
        # 단톡방 테스트용: 상위 2명만 남김
        from collections import Counter
        top = [n for n, _ in Counter(m.sender for m in msgs).most_common(2)]
        print(f"[warn] {e} → 상위 2명({top})만 사용")
        msgs = [m for m in msgs if m.sender in top]
        a, b = sorted(top)

    sessions = split_sessions(msgs, gap)
    print(f"A={a}  B={b}  msgs={len(msgs)}  sessions={len(sessions)} (gap={gap}min)")
    weeks = build_weekly_metrics(msgs, a, b, gap)
    print(f"weeks={len(weeks)}")
    for w in weeks:
        m = w["metrics"]
        print(f"  {w['week_start']}  sess={w['session_count']:3d} msgs={w['message_count']:4d}  "
              f"q={m['question_rate']['couple']} len={m['message_length_median']['couple']} "
              f"gap={m['reply_gap_median_min']['couple']}  "
              f"comparable={m['question_rate'].get('comparable')}  "
              f"top_wd={w['summary_extras']['activity']['top_weekday']} top_hr={w['summary_extras']['activity']['top_hour']}  "
              f"outliers={len(w['outliers'])}")
    if "--json" in sys.argv:
        print(json.dumps(weeks[-1], ensure_ascii=False, indent=2))
