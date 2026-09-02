import React, { useState } from "react";

export const AIChatSidebar: React.FC = () => {
  const [messages, setMessages] = useState<
    { role: "user" | "assistant"; content: string }[]
  >([
    {
      role: "assistant",
      content:
        "Hello! I am your world-building assistant. Stuck on a name? Need a faction idea? Just ask!",
    },
  ]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages([...messages, { role: "user", content: input }]);
    setInput("");
    // Mock response
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "That's a great idea! Consider expanding on how this affects the local economy.",
        },
      ]);
    }, 1000);
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950 font-sans">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`px-3 py-2 rounded-none max-w-[90%] font-sans text-sm leading-relaxed border ${
                msg.role === "user"
                  ? "bg-zinc-900 text-zinc-300 border-zinc-800"
                  : "bg-zinc-950 text-zinc-100 border-zinc-700"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      <div className="p-3 border-t border-zinc-800 bg-zinc-950">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask anything..."
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-none px-3 py-2 text-sm font-sans text-zinc-300 focus:outline-none focus:border-zinc-400"
          />
          <button
            onClick={handleSend}
            className="p-2 bg-zinc-100 text-zinc-950 hover:bg-white rounded-none transition-colors border border-zinc-100"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
