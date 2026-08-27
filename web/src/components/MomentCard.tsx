// 역할: 특이 순간 카드 (참조: API_SPEC §4.2 moments) — 시여 담당
// 스캐폴딩 스텁: 디자인은 TODO(시여)
import type { Moment } from "../api/types";

function formatMessageTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("ko-KR", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export default function MomentCard({ moment }: { moment: Moment }) {
  const hasMessages = Boolean(moment.messages?.length);

  const messages = moment.messages?.length
    ? moment.messages
    : [{ at: moment.at, text: moment.snippet ?? moment.text }];

  return (
    <details className="report-moment-detail">
      <summary className="report-moment-detail__summary">
        <span className="report-moment-detail__summary-label">
          {moment.text}
        </span>

        <span
          className="report-moment-detail__toggle"
          aria-hidden="true"
        >
          {hasMessages ? "메시지 보기" : "상세 보기"}
        </span>
      </summary>

      <div
        className="report-moment-detail__messages"
        aria-label="기억하고 싶은 순간의 메시지"
      >
        <p className="report-moment-detail__eyebrow">
          {hasMessages ? "이 순간의 대화" : "이 순간의 기록"}
        </p>

        <div className="report-moment-detail__message-list">
          {messages.map((message, index) => (
            <blockquote
              className="report-moment-detail__message"
              key={`${message.at}-${index}`}
            >
              <time dateTime={message.at}>
                {formatMessageTime(message.at)}
              </time>
              <p>{message.text}</p>
            </blockquote>
          ))}
        </div>
      </div>
    </details>
  );
}
