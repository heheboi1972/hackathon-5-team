import { useState } from "react";
import type { FormEvent } from "react";
import { ApiClientError, api } from "../api/client";
import type { ChatResponse, ChatTurn, Citation } from "../api/types";
import Badge from "./Badge";
import Button from "./Button";
import Card from "./Card";

type ChatEntry = {
  id: string;
  role: ChatTurn["role"];
  content: string | null;
  citations?: Citation[];
  redirect?: string | null;
};

const CHAT_MAX_LENGTH = 500;

function formatCitationTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function citationSenderLabel(sender: Citation["sender"]): string {
  return sender === "a" ? "A" : "B";
}

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiClientError && error.message) return error.message;
  return "질문을 보내지 못했어요. 잠시 후 다시 시도해주세요.";
}

type ChatIconName = "message" | "quote" | "compass" | "sparkle" | "send";

function ChatIcon({ name }: { name: ChatIconName }) {
  if (name === "quote") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 7.5h5.5v5H8.4c.1 2 1.1 3.3 3.1 4v1.5C7.7 17.5 6 15.1 6 11.5zM13.5 7.5H19v5h-3.1c.1 2 1.1 3.3 3.1 4v1.5c-3.8-.5-5.5-2.9-5.5-6.5z" /></svg>;
  }
  if (name === "compass") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="m15.7 8.3-2.1 5.3-5.3 2.1 2.1-5.3z" /></svg>;
  }
  if (name === "sparkle") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.4 5.6L19 10l-5.6 1.4L12 17l-1.4-5.6L5 10l5.6-1.4z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6z" /></svg>;
  }
  if (name === "send") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 4 16 8-16 8 3.2-8z" /><path d="M7.2 12H20" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6.5h16v10H9l-4 3v-3H4z" /><path d="M8 10h8M8 13h5" /></svg>;
}

function CitationCards({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <Card className="chat-citations">
      <div className="chat-citations__heading">
        <div className="chat-citations__title"><span className="chat-icon-bubble chat-icon-bubble--lavender"><ChatIcon name="quote" /></span><h3>근거가 된 대화</h3></div>
        <Badge tone="neutral" className="chat-citations__count">{citations.length}개</Badge>
      </div>
      <div className="chat-citations__list">
        {citations.map((citation, index) => (
          <div key={`${citation.session_id}-${citation.at}-${index}`} className="chat-citation">
            <div className="chat-citation__meta">
              <Badge who={citation.sender}>발화자 {citationSenderLabel(citation.sender)}</Badge>
              <span>세션 {citation.session_id}</span>
              <time dateTime={citation.at}>{formatCitationTime(citation.at)}</time>
            </div>
            <p className="chat-citation__snippet">
              “{citation.snippet}”
            </p>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function ChatPanel({ coupleId }: { coupleId: string }) {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isLoading) return;

    const userMessageId = `${Date.now()}-user`;
    const assistantMessageId = `${Date.now()}-assistant`;
    const history: ChatTurn[] = messages
      .filter((entry): entry is ChatEntry & { content: string } => Boolean(entry.content))
      .map(({ role, content }) => ({ role, content }))
      .slice(-6);

    setMessages((current) => [...current, { id: userMessageId, role: "user", content: message }]);
    setDraft("");
    setError(null);
    setIsLoading(true);

    try {
      const response = await api.post<ChatResponse>(
        `/api/couples/${encodeURIComponent(coupleId)}/chat`,
        { message, history },
      );

      setMessages((current) => [
        ...current,
        {
          id: assistantMessageId,
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          redirect: response.redirect,
        },
      ]);
    } catch (requestError) {
      setMessages((current) => current.filter((entry) => entry.id !== userMessageId));
      setDraft(message);
      setError(getErrorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section aria-labelledby="chat-panel-title" className="chat-panel">
      <Card className="chat-panel__card">
        <header className="chat-panel__header">
          <div className="chat-panel__header-icon"><ChatIcon name="message" /></div>
          <div>
            <p className="chat-panel__eyebrow">대화 기록 검색</p>
            <h2 id="chat-panel-title">
            우리 대화에 대해 물어보세요
            </h2>
            <p>대화 기록에 근거한 답변과 인용을 보여드려요.</p>
          </div>
        </header>

        <div className="chat-panel__body">
          <div aria-live="polite" className="chat-thread">
            {messages.length === 0 && !isLoading ? (
              <div className="chat-empty-state">
                <div className="chat-empty-state__content">
                  <div className="chat-empty-state__icon" aria-hidden="true">
                    <ChatIcon name="message" />
                  </div>
                  <h3>궁금한 대화 기록을 질문해보세요</h3>
                  <p>
                    예: “지난달에 우리가 가장 많이 이야기한 주제는 뭐야?”
                  </p>
                </div>
              </div>
            ) : (
              messages.map((entry) => {
                const hasAssistantContent = Boolean(
                  entry.content || entry.redirect || entry.citations?.length,
                );
                if (entry.role === "assistant" && !hasAssistantContent) return null;

                return (
                  <div key={entry.id} className={entry.role === "user" ? "chat-message-row chat-message-row--user" : "chat-message-row chat-message-row--assistant"}>
                    <div className={entry.role === "user" ? "chat-message chat-message--user" : "chat-message chat-message--assistant"}>
                      <p className="chat-message__label">
                        {entry.role === "assistant" && <span className="chat-message__label-icon"><ChatIcon name="message" /></span>}
                        {entry.role === "user" ? "나" : "챗봇"}
                      </p>
                      {entry.content && (
                        <div
                          className={[
                            "chat-bubble",
                            entry.role === "user"
                              ? "chat-bubble--user"
                              : "chat-bubble--assistant",
                          ].join(" ")}
                        >
                          {entry.content}
                        </div>
                      )}
                      {entry.role === "assistant" && entry.redirect && (
                        <div role="status" className="chat-redirect">
                          <span aria-hidden="true" className="chat-redirect__icon"><ChatIcon name="compass" /></span>
                          <div>
                            <p className="chat-redirect__title">이 질문은 안내가 필요해요</p>
                            <p className="chat-redirect__copy">{entry.redirect}</p>
                          </div>
                        </div>
                      )}
                      {entry.role === "assistant" && entry.citations && (
                        <CitationCards citations={entry.citations} />
                      )}
                    </div>
                  </div>
                );
              })
            )}

            {isLoading && (
              <div className="chat-message-row chat-message-row--assistant" role="status" aria-label="답변을 불러오는 중">
                <div className="chat-message chat-message--assistant">
                  <p className="chat-message__label"><span className="chat-message__label-icon"><ChatIcon name="sparkle" /></span>챗봇</p>
                  <div className="chat-bubble chat-bubble--loading">
                    답변을 찾고 있어요…
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="chat-composer">
            {error && (
              <div role="alert" className="chat-error">
                {error}
              </div>
            )}
            <form onSubmit={handleSubmit} className="chat-composer__form">
              <div className="chat-composer__field">
                <label htmlFor="chat-message" className="sr-only">질문</label>
                <textarea
                  id="chat-message"
                  value={draft}
                  maxLength={CHAT_MAX_LENGTH}
                  rows={2}
                  placeholder="대화 기록에 대해 질문해보세요"
                  disabled={isLoading}
                  onChange={(event) => setDraft(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      event.currentTarget.form?.requestSubmit();
                    }
                  }}
                  className="chat-composer__textarea"
                />
                <p className="chat-composer__counter">
                  {draft.length}/{CHAT_MAX_LENGTH}
                </p>
              </div>
              <Button type="submit" size="sm" className="chat-send-button" disabled={isLoading || !draft.trim()}>
                <span>{isLoading ? "검색 중…" : "보내기"}</span>
                <ChatIcon name="send" />
              </Button>
            </form>
            <p className="chat-composer__hint">Shift + Enter로 줄바꿈할 수 있어요.</p>
          </div>
        </div>
      </Card>
    </section>
  );
}
