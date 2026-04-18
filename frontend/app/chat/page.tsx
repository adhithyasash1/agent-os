import { ChatInterface } from "@/components/chat-interface";

export default function ChatPage() {
  return (
    <div className="flex-1 flex flex-col h-full bg-[#0A0A0C]">
      <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b border-[#222224] bg-[#0A0A0C]/80 px-6 backdrop-blur-md shrink-0">
        <h1 className="text-[14px] font-semibold text-[#E4E4E5]">Live Agent Console</h1>
      </header>
      <div className="flex-1 overflow-hidden relative">
        <ChatInterface />
      </div>
    </div>
  );
}
