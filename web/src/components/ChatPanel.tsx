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

function CitationCards({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <Card className="mt-3 border-rose-100 bg-white p-3 shadow-none">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-gray-700">근거가 된 대화</h3>
        <Badge tone="neutral">{citations.length}개</Badge>
      </div>
      <div className="mt-2 space-y-2">
        {citations.map((citation, index) => (
          <div key={`${citation.session_id}-${citation.at}-${index}`} className="rounded-md border border-gray-200 bg-gray-50 p-3">
            <div className="flex flex-wrap items-center gap-2 text-xs text-gray-500">
              <Badge who={citation.sender}>발화자 {citationSenderLabel(citation.sender)}</Badge>
              <span>세션 {citation.session_id}</span>
              <time dateTime={citation.at}>{formatCitationTime(citation.at)}</time>
            </div>
            <p className="mt-2 border-l-2 border-rose-200 pl-3 text-sm leading-6 text-gray-700">
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
    <section aria-labelledby="chat-panel-title" className="mx-auto w-full max-w-3xl">
      <Card className="overflow-hidden p-0">
        <header className="border-b bg-rose-50/60 px-5 py-4">
          <p className="text-sm font-medium text-rose-600">대화 기록 검색</p>
          <h1 id="chat-panel-title" className="mt-1 text-xl font-bold text-gray-900">
            우리 대화에 대해 물어보세요
          </h1>
          <p className="mt-1 text-sm text-gray-600">대화 기록에 근거한 답변과 인용을 보여드려요.</p>
        </header>

        <div className="flex min-h-[28rem] flex-col">
          <div aria-live="polite" className="min-h-[20rem] flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
            {messages.length === 0 && !isLoading ? (
              <div className="flex min-h-[20rem] items-center justify-center text-center">
                <div className="max-w-sm">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100 text-xl text-rose-600" aria-hidden="true">
                    ?
                  </div>
                  <h2 className="mt-4 font-semibold text-gray-900">궁금한 대화 기록을 질문해보세요</h2>
                  <p className="mt-2 text-sm leading-6 text-gray-500">
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
                  <div key={entry.id} className={entry.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div className={entry.role === "user" ? "max-w-[85%] sm:max-w-[75%]" : "max-w-[95%] sm:max-w-[85%]"}>
                      <p className="mb-1 text-xs font-medium text-gray-500">
                        {entry.role === "user" ? "나" : "챗봇"}
                      </p>
                      {entry.content && (
                        <div
                          className={[
                            "rounded-2xl px-4 py-3 text-sm leading-6",
                            entry.role === "user"
                              ? "rounded-br-md bg-rose-500 text-white"
                              : "rounded-bl-md bg-gray-100 text-gray-800",
                          ].join(" ")}
                        >
                          {entry.content}
                        </div>
                      )}
                      {entry.role === "assistant" && entry.redirect && (
                        <div role="status" className="mt-2 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                          <span aria-hidden="true" className="mt-0.5">↪</span>
                          <div>
                            <p className="font-semibold">이 질문은 안내가 필요해요</p>
                            <p className="mt-1 leading-6">{entry.redirect}</p>
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
              <div className="flex justify-start" role="status" aria-label="답변을 불러오는 중">
                <div>
                  <p className="mb-1 text-xs font-medium text-gray-500">챗봇</p>
                  <div className="rounded-2xl rounded-bl-md bg-gray-100 px-4 py-3 text-sm text-gray-500">
                    답변을 찾고 있어요…
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="border-t bg-white p-4 sm:p-5">
            {error && (
              <div role="alert" className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {error}
              </div>
            )}
            <form onSubmit={handleSubmit} className="flex items-end gap-2">
              <div className="min-w-0 flex-1">
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
                  className="block w-full resize-none rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 outline-none transition focus:border-rose-400 focus:ring-2 focus:ring-rose-200 disabled:bg-gray-100"
                />
                <p className="mt-1 text-right text-xs text-gray-400">
                  {draft.length}/{CHAT_MAX_LENGTH}
                </p>
              </div>
              <Button type="submit" size="sm" disabled={isLoading || !draft.trim()}>
                {isLoading ? "검색 중…" : "보내기"}
              </Button>
            </form>
            <p className="mt-2 text-xs text-gray-400">Shift + Enter로 줄바꿈할 수 있어요.</p>
          </div>
        </div>
      </Card>
    </section>
  );
}
