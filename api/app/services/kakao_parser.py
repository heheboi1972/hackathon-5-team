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
from dataclasses import dataclass, asdict
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

# 질문 판정 (§3 지표 2): '?' 로 끝나거나 *강한* 의문 어미로 끝남.
# '어/야/지/죠' 는 평서문("알았어", "그래야지")에도 쓰여 물음표 없이는 구분 불가 → 제외.
# 보수적 정의: 놓치는 질문은 있어도 평서문을 질문으로 세지는 않는다.
_QUESTION_ENDINGS = re.compile(r"(니|냐|까|까요|나요|가요|ㄹ까|을까|을까요)[\s~ㅋㅎ]*$")

# 본문에서 제거할 제어문자 (링크 미리보기 흔적 등)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def classify(body: str) -> str:
    for pat, t in _PLACEHOLDERS:
        if pat.match(body):
            return t
    return "text"


def is_question(body: str) -> bool:
    b = body.rstrip()
    if b.endswith("?") or b.endswith("？"):
        return True
    return bool(_QUESTION_ENDINGS.search(b))


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
