import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import type { ChatMessage as ChatMessageType, ActiveTool, ChatStatus } from "../types";
import { streamChat } from "../lib/sse";
import ChatMessage from "../components/shared/ChatMessage";
import ImageUpload from "../components/shared/ImageUpload";
import ToolStatus from "../components/shared/ToolStatus";

export default function VetChat() {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [status, setStatus] = useState<ChatStatus>("idle");
  const [activeTools, setActiveTools] = useState<ActiveTool[]>([]);
  const [input, setInput] = useState("");
  const [pendingImage, setPendingImage] = useState<{
    previewUrl: string;
    base64: string;
  } | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const assistantIdRef = useRef<string>("");

  // Auto-scroll when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, activeTools]);

  // Cleanup on unmount
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  function appendToken(content: string) {
    const targetId = assistantIdRef.current;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === targetId ? { ...m, content: m.content + content } : m,
      ),
    );
  }

  function handleSubmit() {
    const text = input.trim();
    if (!text || status !== "idle") return;

    // User message
    const userMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      imagePreviewUrl: pendingImage?.previewUrl,
      timestamp: new Date(),
    };

    // Assistant placeholder — added before stream starts (avoids race condition)
    const assistantMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      timestamp: new Date(),
    };
    assistantIdRef.current = assistantMsg.id;

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput("");
    setStatus("waiting");
    setActiveTools([]);

    abortRef.current = streamChat(
      {
        message: text,
        image_b64: pendingImage?.base64,
        history: [],
      },
      {
        onToolStatus(tool, toolStatus) {
          setStatus("streaming");
          setActiveTools((prev) => {
            const existing = prev.find((t) => t.name === tool);
            if (existing) {
              return prev.map((t) =>
                t.name === tool ? { ...t, status: toolStatus } : t,
              );
            }
            return [...prev, { name: tool, status: toolStatus }];
          });
        },
        onToken(content) {
          setStatus("streaming");
          appendToken(content);
        },
        onDone() {
          setActiveTools([]);
          setPendingImage(null);
          setStatus("idle");
        },
        onError(message) {
          console.error("[VetChat]", message);
          setStatus("error");
          setTimeout(() => setStatus("idle"), 3000);
        },
      },
    );
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  const busy = status !== "idle" && status !== "error";

  return (
    <div className="flex flex-col h-[calc(100vh-1px)]">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {messages.length === 0 && status === "idle" && (
          <div className="flex-1 flex flex-col items-center justify-center opacity-40">
            <img src="/logo-white.svg" alt="" className="w-20 h-20 mb-4" />
            <p className="text-content-secondary text-sm">Start a conversation or upload a clinical image</p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            message={msg}
            streaming={
              msg.id === assistantIdRef.current && status === "streaming"
            }
          />
        ))}

        {status === "waiting" && (
          <div className="flex gap-1.5 px-4 py-3">
            <div className="w-2 h-2 rounded-full bg-teal animate-bounce" style={{ animationDelay: "0ms" }} />
            <div className="w-2 h-2 rounded-full bg-teal animate-bounce" style={{ animationDelay: "150ms" }} />
            <div className="w-2 h-2 rounded-full bg-teal animate-bounce" style={{ animationDelay: "300ms" }} />
          </div>
        )}

        {activeTools.length > 0 && (
          <div className="mb-4">
            <ToolStatus tools={activeTools} />
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-ocean-border px-6 py-3 bg-ocean-deep">
        {pendingImage && (
          <div className="mb-2">
            <ImageUpload
              onImageSelected={() => {}}
              onClear={() => setPendingImage(null)}
              currentPreview={pendingImage.previewUrl}
              disabled={busy}
            />
          </div>
        )}

        <div className="flex items-end gap-2">
          {!pendingImage && (
            <ImageUpload
              onImageSelected={(previewUrl, base64) =>
                setPendingImage({ previewUrl, base64 })
              }
              onClear={() => setPendingImage(null)}
              disabled={busy}
            />
          )}

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe symptoms, ask about dosages, or upload a clinical image..."
            disabled={busy}
            rows={1}
            className="flex-1 bg-ocean-elevated border border-ocean-border rounded-lg px-4 py-2.5 text-sm text-content-primary placeholder:text-content-secondary focus:outline-none focus:border-teal-light resize-none disabled:opacity-40"
          />

          <button
            onClick={handleSubmit}
            disabled={busy || !input.trim()}
            className="p-2.5 bg-teal hover:bg-teal-hover disabled:bg-ocean-border disabled:text-content-muted text-white rounded-lg transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        {status === "error" && (
          <p className="text-red-400 text-xs mt-1">
            Error connecting to the AI. Please try again.
          </p>
        )}
      </div>
    </div>
  );
}
