"""
카카오톡 대화 내보내기 파서.

PC / Android / iOS 모두 실제 샘플로 검증됨.

형식 3종:
  - 대괄호 (PC + Android 최신 앱): 헤더 + `--- 날짜 ---` 구분선 + `[이름] [오후 1:43] 본문`
  - 구 Android: `2026년 8월 5일 오후 11:12, 이름 : 본문` (한 줄에 날짜까지)
  - iOS: `2026. 8. 5. 오전 10:58, 이름 : 본문`


사용:
    from kakao_parser import parse_export
    msgs = parse_export(open("KakaoTalk_xxx.txt", "rb").read())
    # zip 이면 parse_export(zip_bytes) 로 그대로 넘기면 내부 .txt 를 찾아 처리
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------- 데이터 모델

MSG_TYPES = ("text", "photo", "emoticon", "file", "video", "voice", "call", "deleted")


@dataclass
class Message:
    sender: str
    sent_at: datetime  # tz-aware (Asia/Seoul)
    body: str
    msg_type: str
    is_question: bool
    body_len: int
    tokens: list[str] = field(
        default_factory=list
    )  # 단어 집계용 (text 만). 저장하지 않음

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sent_at"] = self.sent_at.isoformat()
        return d


# ---------------------------------------------------------------- 공통 규칙

# 플레이스홀더 → msg_type  (순서 중요: 구체적인 것 먼저)
_PLACEHOLDERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^사진( \d+장)?$"), "photo"),
    (re.compile(r"^이모티콘$"), "emoticon"),
    (re.compile(r"^파일: .+$", re.S), "file"),
    (re.compile(r"^동영상$"), "video"),
    (re.compile(r"^음성메시지$"), "voice"),
    (re.compile(r"^(보이스톡|페이스톡) 해요$"), "call"),
    (re.compile(r"^삭제된 메시지입니다\.?$"), "deleted"),
]

# 질문 판정 (REQUIREMENTS FR-002 question_rate). 네 규칙:
#  (1) 물음표가 끝에 (뒤에 공백·~·ㅋ·ㅎ·.·! 허용)  → "뭐해?ㅋㅋ"
#  (2) 의문사 + 구어 어미로 끝남, 또는 의문사 단독   → "뭐해", "어디야", "언제 와", "왜"
#  (3) 강한 의문 어미로 끝남 (오탐 제외: "아니", "할까 말까")
#  (4) 느낌표로 끝나면 비질문 ("언제 와!" 는 감탄)
# 한계: 형태소 분석 없음. "괜찮아" 처럼 질문/평서 동형은 물음표 없으면 평서문.
_TRAIL = r"[\s~ㅋㅎ]*$"
_Q_MARK = re.compile(r"[?？][\s~ㅋㅎ.!]*$")
_Q_WORDS = (
    r"(뭐|뭘|무슨|무엇|언제|어디|누구|누가|왜|어떻게|어떡|어때|얼마|몇|어느|어떤)"
)
_Q_WORD_RE = re.compile(_Q_WORDS)
_Q_WORD_ALONE = re.compile(r"^" + _Q_WORDS + r"[야요]?" + _TRAIL)
_Q_COLLOQ_END = re.compile(
    r"(어|아|야|지|죠|요|나|니|까|데|래|게|해|돼|와|가|줘|네|나요|ㄹ까)" + _TRAIL
)
_Q_STRONG_END = re.compile(
    r"(?<!아)(니)" + _TRAIL + r"|(냐|까|까요|나요|ㄹ까|을까|을까요)" + _TRAIL
)
_Q_HESITATE = re.compile(r"까\s*말까" + _TRAIL)
_EXCLAIM_END = re.compile(r"![\s~ㅋㅎ]*$")

# 본문에서 제거할 제어문자 (링크 미리보기 흔적 등)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def classify(body: str) -> str:
    for pat, t in _PLACEHOLDERS:
        if pat.match(body):
            return t
    return "text"


def is_question(body: str) -> bool:
    b = body.rstrip()
    if _Q_MARK.search(b):  # (1)
        return True
    if _EXCLAIM_END.search(b):  # (4)
        return False
    if _Q_HESITATE.search(b):  # "할까 말까" 는 독백
        return False
    if _Q_WORD_RE.search(b) and (
        _Q_COLLOQ_END.search(b) or _Q_WORD_ALONE.match(b)
    ):  # (2)
        return True
    return bool(_Q_STRONG_END.search(b))  # (3)


# ---------------------------------------------------------------- 토크나이즈 (단어 집계용, FR-002 sentiment)
# 목적: 감성 사전 매칭에 쓸 단어 목록. 형태소 분석 없이 규칙만.
#  - 반복 축약: "좋아아아" → "좋아", "조아조아" → "조아". "ㅋㅋㅋㅋ"/"ㅎㅎ"/"ㅠㅠ" 는 통째로 제거
#  - 문장부호·숫자·URL 제거
#  - 흔한 조사 제거: 이/가/을/를/은/는/도/만/에/로/의/요 (2글자 이상 어절에서만)
_URL_RE = re.compile(r"https?://\S+")
_REPEAT_RE = re.compile(r"(.)\1{2,}")
_REPEAT2_RE = re.compile(
    r"(..)\1+"
)  # "조아조아" → "조아"                         # 같은 글자 3회 이상 → 1회
_JAMO_RE = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]+")  # 자모만 있는 덩어리 (ㅋㅋ ㅠㅠ)
_PUNCT_RE = re.compile(r"[^\w가-힣\s]")
_PARTICLE_RE = re.compile(r"(이|가|을|를|은|는|도|만|에|로|의|요)$")


def tokenize(body: str) -> list[str]:
    b = _URL_RE.sub(" ", body)
    b = _JAMO_RE.sub(" ", b)
    b = _PUNCT_RE.sub(" ", b)
    out: list[str] = []
    for w in b.split():
        w = _REPEAT_RE.sub(r"\1", w)
        w = _REPEAT2_RE.sub(r"\1", w)
        if len(w) >= 2:
            w = _PARTICLE_RE.sub("", w)
        if len(w) >= 1 and not w.isdigit():
            out.append(w)
    return out


def _clean(body: str) -> str:
    return _CONTROL_RE.sub("", body).strip()


def _to_24h(ampm: str | None, hour: int) -> int:
    """폰이 24시간제로 설정돼 있으면 오전/오후 없이 시각이 그대로 나온다(ampm=None) — 변환 없이 통과."""
    if ampm is None:
        return hour
    if ampm == "오전":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def _make(sender: str, when: datetime, body: str) -> Message:
    body = _clean(body)
    mtype = classify(body)
    return Message(
        sender=sender.strip(),
        sent_at=when,
        body=body,
        msg_type=mtype,
        is_question=(mtype == "text" and is_question(body)),
        body_len=len(body) if mtype == "text" else 0,
        tokens=tokenize(body) if mtype == "text" else [],
    )


# ---------------------------------------------------------------- 레코드 분할 + 시스템 메시지


def _split_records(text: str) -> list[str]:
    """
    CRLF 가 있으면 CRLF 로, 없으면(LF 로 정규화된 파일) LF 로 나눈다.
    CRLF 로 나누면 PC 의 여러 줄 메시지(내부 LF)는 한 레코드로 유지되고,
    Android(내부 줄바꿈도 CRLF)는 조각나지만 파서의 이어붙이기가 다시 합친다.
    """
    return text.split("\r\n") if "\r\n" in text else text.split("\n")


# 대화 내용이 아닌 줄. 이어붙이기 대상에서 빼야 해서 명시적으로 열거한다.
# (한계: 목록에 없는 시스템 문구는 직전 메시지의 이어지는 줄로 붙는다)
_SYSTEM_RES: tuple[re.Pattern, ...] = (
    re.compile(r"^.+ 님과 카카오톡 대화$"),
    re.compile(r"^저장한 날짜 ?: .+$"),
    re.compile(r"^.+님이 .+님을 초대했습니다\.?$"),
    re.compile(r"^.+님이 (들어왔|나갔)습니다\.?$"),
    re.compile(r"^.+님을 내보냈습니다\.?$"),
    re.compile(r"^.+님이 방장이 되(었습니다|어 .+)$"),
    re.compile(r"^.+님이 채팅방 이름을 (변경|수정)하였습니다\.?$"),
    re.compile(r"^.+님이 (공지를 등록했|공지를 수정했|메시지를 가렸)습니다\.?$"),
    re.compile(r"^채팅방 관리자가 .+$"),
    # 구 Android / iOS: 시각 뒤가 쉼표가 아니라 콜론이면 시스템 메시지.
    # 오전/오후 없이 24시간제로 나오는 폰 설정도 있음(_MSG_RE 들과 동일한 이유) → 선택적으로.
    re.compile(r"^\d{4}년 \d{1,2}월 \d{1,2}일 (?:(?:오전|오후) )?\d{1,2}:\d{2}: "),
    re.compile(r"^\d{4}\. \d{1,2}\. \d{1,2}\. (?:(?:오전|오후) )?\d{1,2}:\d{2}: "),
)

# 대시 없는 날짜 구분선 (iOS / 구 Android). 대괄호 형식은 _BRACKET_DATE_RE 가 잡는다.
_BARE_DATE_RE = re.compile(r"^\d{4}년 \d{1,2}월 \d{1,2}일 \S+요일$")


def _is_system(rec: str) -> bool:
    return any(p.match(rec) for p in _SYSTEM_RES)


# ------------------------------------------------- 대괄호 형식 = PC + Android 최신 앱 (확인됨)

_PC_HEADER_RE = re.compile(r"^(.+) 님과 카카오톡 대화$")
_BRACKET_DATE_RE = re.compile(r"^-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일 \S+ -+$")
_BRACKET_MSG_RE = re.compile(
    # 오전/오후는 폰이 12시간제일 때만 붙는다 — 24시간제 폰은 "[20:24]" 처럼 바로 시각이 나온다.
    r"^\[(.+?)\] \[(?:(오전|오후) )?(\d{1,2}):(\d{2})\] (.*)$", re.S
)


def parse_bracket(text: str) -> list[Message]:
    """
    `[이름] [오후 1:43] 본문` 형식. PC 와 Android 최신 앱이 이 형식을 공유한다
    (헤더·구분선·본문 배치가 같아 내용만으로는 구분 불가).

    여러 줄 메시지: 새 메시지 머리글·날짜 구분선·시스템 메시지가 아닌 줄은
    직전 메시지의 이어지는 줄로 붙인다(중간 빈 줄 포함). PC 는 내부 줄바꿈이
    LF 라 애초에 한 레코드이므로 영향이 없고, Android 는 내부도 CRLF 라
    레코드가 쪼개지는데 이 로직이 원문을 복원한다.
    """
    out: list[Message] = []
    cur_date: date | None = None
    sender: str | None = None
    when: datetime | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal sender, when, lines
        if sender is not None and when is not None:
            out.append(_make(sender, when, "\n".join(lines)))
        sender, when, lines = None, None, []

    for rec in _split_records(text):
        m = _BRACKET_DATE_RE.match(rec)
        if m:
            flush()
            cur_date = date(int(m[1]), int(m[2]), int(m[3]))
            continue
        m = _BRACKET_MSG_RE.match(rec)
        if m:
            flush()
            if cur_date is None:
                continue  # 날짜 구분선 앞이면 날짜를 모른다 → 버림
            who, ampm, hh, mm, body = m.groups()
            sender = who
            when = datetime(
                cur_date.year,
                cur_date.month,
                cur_date.day,
                _to_24h(ampm, int(hh)),
                int(mm),
                tzinfo=KST,
            )
            lines = [body]
            continue
        if _is_system(rec):
            flush()  # 시스템 메시지(초대/퇴장/방장 등) → 버림
            continue
        if sender is not None:
            lines.append(rec)  # 여러 줄 메시지의 이어지는 줄
        # 그 외(헤더, 첫 메시지 전 빈 줄) → 버림
    flush()
    return out


# PC 는 대괄호 형식의 한 갈래 — 기존 이름 유지 (docs/TEST_CASES.md TC-PARSE-002)
parse_pc = parse_bracket


# ---------------------------------------------------------------- 구 Android 형식 (확인됨)

# 한 줄에 날짜까지: "2026년 8월 5일 오후 11:12, 이름 : 본문". 날짜 구분선 없음.
_ANDROID_MSG_RE = re.compile(
    # 24시간제 폰: "...일 20:24, 이름 : 본문" (오전/오후 생략)
    r"^(\d{4})년 (\d{1,2})월 (\d{1,2})일 (?:(오전|오후) )?(\d{1,2}):(\d{2}), (.+?) : (.*)$",
    re.S,
)


def parse_android(text: str) -> list[Message]:
    """
    Android 내보내기는 앱 버전에 따라 두 가지다.
      (신) PC 와 같은 대괄호 형식 → parse_bracket 이 처리
      (구) 한 줄에 날짜까지 → 아래 로직

    구 형식의 여러 줄 메시지는 둘째 줄부터 날짜·이름 없이 그대로 나오므로
    머리글/날짜 구분선/시스템 메시지가 아닌 줄은 직전 메시지에 이어붙인다.
    """
    records = _split_records(text)
    if any(_BRACKET_MSG_RE.match(r) for r in records):
        return parse_bracket(text)

    out: list[Message] = []
    sender: str | None = None
    when: datetime | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal sender, when, lines
        if sender is not None and when is not None:
            out.append(_make(sender, when, "\n".join(lines)))
        sender, when, lines = None, None, []

    for rec in records:
        m = _ANDROID_MSG_RE.match(rec)
        if m:
            flush()
            y, mo, d, ampm, hh, mm, who, body = m.groups()
            sender = who
            when = datetime(
                int(y), int(mo), int(d), _to_24h(ampm, int(hh)), int(mm), tzinfo=KST
            )
            lines = [body]
            continue
        if _BARE_DATE_RE.match(rec) or _is_system(rec):
            flush()  # 날짜 구분선 / 시스템 메시지 → 버림
            continue
        if sender is not None:
            lines.append(rec)  # 여러 줄 메시지의 이어지는 줄
    flush()
    return out


# ---------------------------------------------------------------- iOS "텍스트 메시지만 보내기" (확인됨)
#   헤더:   "Talk_2026.8.21 23:43-1.txt" / "저장한 날짜 : 2026. 8. 22. 오후 11:16"
#   구분선: "2026년 8월 5일 수요일"  (대시 없음, 메시지마다 날짜가 있어 실제로는 불필요)
#   시스템: "2026. 8. 5. 오전 9:10: 김OO님이 ... 초대했습니다."  (시각 뒤 콜론)
#   메시지: "2026. 8. 5. 오전 10:58, 이름 : 본문"               (시각 뒤 쉼표, " : " 구분)
#   레코드 끝 CRLF / 내부 줄바꿈 LF → PC 와 동일 트릭. BOM 있음.
_IOS_MSG_RE = re.compile(
    # 24시간제 폰: "2026. 8. 5. 20:24, 이름 : 본문" (오전/오후 생략)
    r"^(\d{4})\. (\d{1,2})\. (\d{1,2})\. (?:(오전|오후) )?(\d{1,2}):(\d{2}), (.+?) : (.*)$",
    re.S,
)
_IOS_HEADER_RE = re.compile(r"^저장한 날짜 : \d{4}\. \d{1,2}\. \d{1,2}\.")  # 오전/오후는 12시간제 폰에만 있음


def parse_ios(text: str) -> list[Message]:
    """
    iOS 는 내부 줄바꿈이 LF 라 CRLF 분할만으로 여러 줄 메시지가 한 레코드로 잡힌다.
    다만 LF 로 정규화된 파일도 견디도록, 머리글이 아닌 줄은 직전 메시지에 이어붙인다.
    """
    out: list[Message] = []
    sender: str | None = None
    when: datetime | None = None
    lines: list[str] = []

    def flush() -> None:
        nonlocal sender, when, lines
        if sender is not None and when is not None:
            out.append(_make(sender, when, "\n".join(lines)))
        sender, when, lines = None, None, []

    for rec in _split_records(text):
        m = _IOS_MSG_RE.match(rec)
        if m:
            flush()
            y, mo, d, ampm, hh, mm, who, body = m.groups()
            sender = who
            when = datetime(
                int(y), int(mo), int(d), _to_24h(ampm, int(hh)), int(mm), tzinfo=KST
            )
            lines = [body]
            continue
        if _BARE_DATE_RE.match(rec) or _is_system(rec):
            flush()  # 날짜 구분선 / 시스템 메시지 → 버림
            continue
        if sender is not None:
            lines.append(rec)  # 여러 줄 메시지의 이어지는 줄
        # 그 외(파일명 헤더) → 버림
    flush()
    return out


# ---------------------------------------------------------------- 형식 감지 + 진입점


def detect_format(text: str) -> str:
    """
    PC 와 Android 최신 앱은 형식이 같아 구분할 수 없다 → 둘 다 "pc" 로 보고
    같은 파서(parse_bracket)로 넘긴다. "android" 는 구 형식 전용.
    """
    head = _split_records(text)[:40]
    first = head[0].strip() if head else ""
    if _PC_HEADER_RE.match(first) or any(
        _BRACKET_DATE_RE.match(l) or _BRACKET_MSG_RE.match(l) for l in head
    ):
        return "pc"
    if any(_IOS_HEADER_RE.match(l) or _IOS_MSG_RE.match(l) for l in head):
        return "ios"
    if any(_ANDROID_MSG_RE.match(l) for l in head):
        return "android"
    raise ValueError("알 수 없는 카카오톡 내보내기 형식입니다")


def _extract_txt_from_zip(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        txts = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not txts:
            raise ValueError("zip 안에 .txt 가 없습니다")
        # 가장 큰 txt 하나만 사용 (사진·파일은 폐기)
        name = max(txts, key=lambda n: z.getinfo(n).file_size)
        return z.read(name)


def decode_export(data: bytes) -> tuple[str, str]:
    """zip 추출·UTF-8 디코딩 후 (감지 형식, 텍스트)를 반환한다."""
    if data[:2] == b"PK":
        data = _extract_txt_from_zip(data)
    text = data.decode("utf-8-sig")
    fmt = detect_format(text)
    return fmt, text


def parse_export(data: bytes) -> list[Message]:
    fmt, text = decode_export(data)
    return {"pc": parse_bracket, "android": parse_android, "ios": parse_ios}[fmt](text)


# ---------------------------------------------------------------- 커플 서비스 검증


def validate_couple(msgs: list[Message]) -> tuple[str, str]:
    """발화자가 정확히 2명인지 확인하고 (이름1, 이름2) 반환."""
    senders = sorted({m.sender for m in msgs})
    if len(senders) != 2:
        raise ValueError(
            f"커플 대화방 파일을 올려주세요 (발화자 {len(senders)}명 감지)"
        )
    return senders[0], senders[1]


if __name__ == "__main__":
    import collections
    import json
    import sys

    msgs = parse_export(open(sys.argv[1], "rb").read())
    print(f"{len(msgs)} messages")
    print("types:", collections.Counter(m.msg_type for m in msgs))
    print("senders:", collections.Counter(m.sender for m in msgs).most_common(5))
    print("questions:", sum(m.is_question for m in msgs))
    print("range:", msgs[0].sent_at, "→", msgs[-1].sent_at)
    print("sample:", json.dumps(msgs[0].to_dict(), ensure_ascii=False)[:200])
