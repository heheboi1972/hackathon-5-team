import { Link } from "react-router-dom";
import ChatPanel from "../components/ChatPanel";

const COUPLE_ID = "00000000-0000-0000-0000-000000000001";

export default function ChatPage() {
  return (
    <main className="space-y-4 p-4 sm:p-8">
      <div className="mx-auto flex w-full max-w-3xl justify-between gap-3 text-sm">
        <Link to="/review" className="font-medium text-rose-600 hover:underline">
          ← 리뷰로
        </Link>
        <Link to="/settings" className="font-medium text-rose-600 hover:underline">
          설정으로 →
        </Link>
      </div>
      <ChatPanel coupleId={COUPLE_ID} />
    </main>
  );
}
