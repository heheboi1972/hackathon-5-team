"""
카카오톡 대화 내보내기 파서.

PC 형식은 실제 샘플로 검증됨. Android / iOS 는 샘플 확보 후 regex 만 채우면 됨.

사용:
    from kakao_parser import parse_export
    msgs = parse_export(open("KakaoTalk_xxx.txt", "rb").read())
    # zip 이면 parse_export(zip_bytes) 로 그대로 넘기면 내부 .txt 를 찾아 처리
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------- 데이터 모델

MSG_TYPES = ("text", "photo", "emoticon", "file", "video", "voice", "call", "deleted")


@dataclass
class Message:
    sender: str
    sent_at: datetime          # tz-aware (Asia/Seoul)
    body: str
    msg_type: str
    is_question: bool
    body_len: int
    tokens: list[str] = field(default_factory=list)   # 단어 집계용 (text 만). 저장하지 않음

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
_Q_WORDS = r"(뭐|뭘|무슨|무엇|언제|어디|누구|누가|왜|어떻게|어떡|어때|얼마|몇|어느|어떤)"
_Q_WORD_RE = re.compile(_Q_WORDS)
_Q_WORD_ALONE = re.compile(r"^" + _Q_WORDS + r"[야요]?" + _TRAIL)
_Q_COLLOQ_END = re.compile(r"(어|아|야|지|죠|요|나|니|까|데|래|게|해|돼|와|가|줘|네|나요|ㄹ까)" + _TRAIL)
_Q_STRONG_END = re.compile(r"(?<!아)(니)" + _TRAIL + r"|(냐|까|까요|나요|ㄹ까|을까|을까요)" + _TRAIL)
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
    if _Q_MARK.search(b):                       # (1)
        return True
    if _EXCLAIM_END.search(b):                  # (4)
        return False
    if _Q_HESITATE.search(b):                   # "할까 말까" 는 독백
        return False
    if _Q_WORD_RE.search(b) and (_Q_COLLOQ_END.search(b) or _Q_WORD_ALONE.match(b)):   # (2)
        return True
    return bool(_Q_STRONG_END.search(b))        # (3)


# ---------------------------------------------------------------- 토크나이즈 (단어 집계용, FR-002 sentiment)
# 목적: 감성 사전 매칭에 쓸 단어 목록. 형태소 분석 없이 규칙만.
#  - 반복 축약: "좋아아아" → "좋아", "조아조아" → "조아". "ㅋㅋㅋㅋ"/"ㅎㅎ"/"ㅠㅠ" 는 통째로 제거
#  - 문장부호·숫자·URL 제거
#  - 흔한 조사 제거: 이/가/을/를/은/는/도/만/에/로/의/요 (2글자 이상 어절에서만)
_URL_RE = re.compile(r"https?://\S+")
_REPEAT_RE = re.compile(r"(.)\1{2,}")
_REPEAT2_RE = re.compile(r"(..)\1+")                          # "조아조아" → "조아"                         # 같은 글자 3회 이상 → 1회
_JAMO_RE = re.compile(r"[ㄱ-ㅎㅏ-ㅣ]+")                          # 자모만 있는 덩어리 (ㅋㅋ ㅠㅠ)
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


def _to_24h(ampm: str, hour: int) -> int:
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


# ---------------------------------------------------------------- PC 형식 (확인됨)

_PC_HEADER_RE = re.compile(r"^(.+) 님과 카카오톡 대화$")
_PC_DATE_RE = re.compile(r"^-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일 \S+ -+$")
_PC_MSG_RE = re.compile(r"^\[(.+?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] (.*)$", re.S)


def parse_pc(text: str) -> list[Message]:
    """
    PC 내보내기. 메시지 끝은 CRLF, 메시지 내부 줄바꿈은 LF → CRLF 로 split 하면
    여러 줄 메시지가 한 레코드로 잡힌다.
    """
    records = text.split("\r\n")
    out: list[Message] = []
    cur_date: date | None = None

    for rec in records:
        if not rec.strip():
            continue
        m = _PC_DATE_RE.match(rec)
        if m:
            cur_date = date(int(m[1]), int(m[2]), int(m[3]))
            continue
        m = _PC_MSG_RE.match(rec)
        if m and cur_date is not None:
            sender, ampm, hh, mm, body = m.groups()
            when = datetime(
                cur_date.year, cur_date.month, cur_date.day,
                _to_24h(ampm, int(hh)), int(mm), tzinfo=KST,
            )
            out.append(_make(sender, when, body))
            continue
        # 그 외: 헤더, 시스템 메시지(초대/퇴장/삭제 등) → 버림
    return out


# ---------------------------------------------------------------- Android / iOS (샘플 확보 후 채움)

# 예상 형식: "2026년 8월 5일 오후 11:12, 이름 : 본문"  (한 줄, 날짜 구분선 없음)
_ANDROID_MSG_RE = re.compile(
    r"^(\d{4})년 (\d{1,2})월 (\d{1,2})일 (오전|오후) (\d{1,2}):(\d{2}), (.+?) : (.*)$", re.S
)


def parse_android(text: str) -> list[Message]:
    """TODO: 실제 샘플로 검증 필요. 여러 줄 메시지의 줄바꿈 처리 방식 확인."""
    out: list[Message] = []
    pending: Message | None = None
    for line in text.splitlines():
        m = _ANDROID_MSG_RE.match(line)
        if m:
            y, mo, d, ampm, hh, mm, sender, body = m.groups()
            when = datetime(int(y), int(mo), int(d), _to_24h(ampm, int(hh)), int(mm), tzinfo=KST)
            pending = _make(sender, when, body)
            out.append(pending)
        elif pending is not None and line.strip():
            # 여러 줄 메시지의 연속 줄로 가정 (샘플로 확인 필요)
            pending.body = _clean(pending.body + "\n" + line)
            pending.body_len = len(pending.body) if pending.msg_type == "text" else 0
            pending.is_question = pending.msg_type == "text" and is_question(pending.body)
    return out


# iOS "텍스트 메시지만 보내기" (확인됨)
#   헤더:   "Talk_2026.8.21 23:43-1.txt" / "저장한 날짜 : 2026. 8. 22. 오후 11:16"
#   구분선: "2026년 8월 5일 수요일"  (대시 없음, 메시지마다 날짜가 있어 실제로는 불필요)
#   시스템: "2026. 8. 5. 오전 9:10: 김OO님이 ... 초대했습니다."  (시각 뒤 콜론)
#   메시지: "2026. 8. 5. 오전 10:58, 이름 : 본문"               (시각 뒤 쉼표, " : " 구분)
#   레코드 끝 CRLF / 내부 줄바꿈 LF → PC 와 동일 트릭. BOM 있음.
_IOS_MSG_RE = re.compile(
    r"^(\d{4})\. (\d{1,2})\. (\d{1,2})\. (오전|오후) (\d{1,2}):(\d{2}), (.+?) : (.*)$", re.S
)
_IOS_HEADER_RE = re.compile(r"^저장한 날짜 : \d{4}\. \d{1,2}\. \d{1,2}\. (오전|오후)")


def parse_ios(text: str) -> list[Message]:
    out: list[Message] = []
    for rec in text.split("\r\n"):
        m = _IOS_MSG_RE.match(rec)
        if not m:
            continue  # 헤더, 날짜 구분선, 시스템 메시지 → 버림
        y, mo, d, ampm, hh, mm, sender, body = m.groups()
        when = datetime(int(y), int(mo), int(d), _to_24h(ampm, int(hh)), int(mm), tzinfo=KST)
        out.append(_make(sender, when, body))
    return out


# ---------------------------------------------------------------- 형식 감지 + 진입점

def detect_format(text: str) -> str:
    head = text.replace("\r\n", "\n").split("\n")[:12]
    joined = "\n".join(head)
    if _PC_HEADER_RE.match(head[0].strip()) or "---------------" in joined:
        return "pc"
    if any(_IOS_HEADER_RE.match(l) for l in head) or any(_IOS_MSG_RE.match(l) for l in head):
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


def parse_export(data: bytes) -> list[Message]:
    if data[:2] == b"PK":
        data = _extract_txt_from_zip(data)
    text = data.decode("utf-8-sig")
    fmt = detect_format(text)
    return {"pc": parse_pc, "android": parse_android, "ios": parse_ios}[fmt](text)


# ---------------------------------------------------------------- 커플 서비스 검증

def validate_couple(msgs: list[Message]) -> tuple[str, str]:
    """발화자가 정확히 2명인지 확인하고 (이름1, 이름2) 반환."""
    senders = sorted({m.sender for m in msgs})
    if len(senders) != 2:
        raise ValueError(f"커플 대화방 파일을 올려주세요 (발화자 {len(senders)}명 감지)")
    return senders[0], senders[1]


if __name__ == "__main__":
    import sys, json, collections
    msgs = parse_export(open(sys.argv[1], "rb").read())
    print(f"{len(msgs)} messages")
    print("types:", collections.Counter(m.msg_type for m in msgs))
    print("senders:", collections.Counter(m.sender for m in msgs).most_common(5))
    print("questions:", sum(m.is_question for m in msgs))
    print("range:", msgs[0].sent_at, "→", msgs[-1].sent_at)
    print("sample:", json.dumps(msgs[0].to_dict(), ensure_ascii=False)[:200])
