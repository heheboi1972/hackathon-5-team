import { Link } from "react-router-dom";
import ChatPanel from "../components/ChatPanel";

const COUPLE_ID = "00000000-0000-0000-0000-000000000001";

function ChatPageIcon({ name }: { name: "calendar" | "message" | "settings" }) {
  if (name === "calendar") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5.5" width="16" height="15" rx="2.5" /><path d="M8 3.5v4M16 3.5v4M4 10h16" /></svg>;
  }
  if (name === "settings") {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4.5a2.1 2.1 0 0 1 4.1.8l.2.8 1 .6.8-.2a2.1 2.1 0 0 1 1.8 3.7l-.7.5v1.2l.7.5a2.1 2.1 0 0 1-1.8 3.7l-.8-.2-1 .6-.2.8a2.1 2.1 0 0 1-4.1 0l-.2-.8-1-.6-.8.2a2.1 2.1 0 0 1-1.8-3.7l.7-.5v-1.2l-.7-.5a2.1 2.1 0 0 1 1.8-3.7l.8.2 1-.6z" /><circle cx="12" cy="11.3" r="2.4" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6.5h16v10H9l-4 3v-3H4z" /><path d="M8 10h8M8 13h5" /></svg>;
}

function ChatIllustration() {
  return (
    <div className="chat-hero-art" aria-hidden="true">
      <span className="chat-hero-art__halo" />
      <span className="chat-hero-art__heart chat-hero-art__heart--one">♥</span>
      <span className="chat-hero-art__heart chat-hero-art__heart--two">♡</span>
      <span className="chat-hero-art__sparkle chat-hero-art__sparkle--one">✦</span>
      <span className="chat-hero-art__sparkle chat-hero-art__sparkle--two">✧</span>
      <span className="chat-hero-art__bubble chat-hero-art__bubble--one">기억을<br />찾아봐요</span>
      <span className="chat-hero-art__bubble chat-hero-art__bubble--two">우리</span>
      <svg className="chat-hero-art__phone" viewBox="0 0 270 170" role="img" aria-label="말풍선과 검색 아이콘이 있는 대화 기억 일러스트">
        <defs>
          <linearGradient id="chat-phone-shell" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#d9c6ff" />
            <stop offset="1" stopColor="#ad8deb" />
          </linearGradient>
          <linearGradient id="chat-phone-screen" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#fffefe" />
            <stop offset="1" stopColor="#fff0f5" />
          </linearGradient>
        </defs>
        <path d="M16 124c30-24 52-31 72-24 17 6 26 23 45 20 23-3 29-26 56-29 25-3 43 7 65 27" fill="none" stroke="#ffadc2" strokeWidth="2" strokeDasharray="3 7" />
        <rect x="56" y="22" width="143" height="124" rx="20" fill="url(#chat-phone-shell)" stroke="#9877d0" strokeWidth="2.5" transform="rotate(-5 127 84)" />
        <rect x="67" y="35" width="121" height="97" rx="12" fill="url(#chat-phone-screen)" stroke="#f2b4c5" strokeWidth="2" transform="rotate(-5 127 84)" />
        <path d="M81 58h50a9 9 0 0 1 9 9v9a9 9 0 0 1-9 9H99l-8 6v-6h-10a9 9 0 0 1-9-9v-9a9 9 0 0 1 9-9Z" fill="#ffe1eb" stroke="#f28aaa" strokeWidth="1.8" transform="rotate(-5 104 74)" />
        <path d="M111 91h50a9 9 0 0 1 9 9v9a9 9 0 0 1-9 9h-32l-8 6v-6h-10a9 9 0 0 1-9-9v-9a9 9 0 0 1 9-9Z" fill="#eee5ff" stroke="#b49be8" strokeWidth="1.8" transform="rotate(-5 136 105)" />
        <path d="M104 73h19M126 73h8M129 105h22M126 105h-5" stroke="#ad7890" strokeWidth="2" strokeLinecap="round" transform="rotate(-5 127 84)" />
        <circle cx="206" cy="47" r="19" fill="#fffaf0" stroke="#efb08b" strokeWidth="2" />
        <circle cx="202" cy="43" r="6.5" fill="none" stroke="#d58d69" strokeWidth="2.2" />
        <path d="m207 48 7 7" stroke="#d58d69" strokeWidth="2.2" strokeLinecap="round" />
        <path d="M170 27h13" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" opacity=".8" />
      </svg>
    </div>
  );
}

export default function ChatPage() {
  return (
    <main className="chat-page">
      <div className="chat-background-decor" aria-hidden="true">
        <span className="chat-decor-sparkle chat-decor-sparkle--one">✦</span>
        <span className="chat-decor-sparkle chat-decor-sparkle--two">✧</span>
        <span className="chat-decor-cloud chat-decor-cloud--one" />
        <span className="chat-decor-cloud chat-decor-cloud--two" />
      </div>
      <div className="chat-page__inner">
        <nav className="chat-page__links" aria-label="Chat 페이지 이동">
          <Link to="/review" className="chat-page__link">
            <ChatPageIcon name="calendar" />
          ← 리뷰로
        </Link>
        <Link to="/settings" className="chat-page__link">
          설정으로
          <ChatPageIcon name="settings" />
        </Link>
        </nav>
        <header className="chat-hero">
          <div className="chat-hero__copy">
            <span className="chat-eyebrow">OUR CHAT MEMORY</span>
            <h1>우리의 대화를<br /><span>다시 찾아봐요</span></h1>
            <p>기억하고 싶은 대화나 궁금한 순간을 편하게 물어보세요.</p>
          </div>
          <div className="chat-hero__aside"><ChatIllustration /></div>
        </header>
        <ChatPanel coupleId={COUPLE_ID} />
      </div>
    </main>
  );
}
