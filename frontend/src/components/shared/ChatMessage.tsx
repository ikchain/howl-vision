import type { ChatMessage as ChatMessageType } from "../../types";
import MarkdownRenderer from "./MarkdownRenderer";

interface Props {
  message: ChatMessageType;
  streaming?: boolean;
}

export default function ChatMessage({ message, streaming }: Props) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[75%] rounded-xl px-4 py-3 ${
          isUser
            ? "bg-gray-800 text-gray-100"
            : "bg-transparent text-gray-100"
        }`}
      >
        {isUser && message.imagePreviewUrl && (
          <img
            src={message.imagePreviewUrl}
            alt="Clinical image"
            className="max-h-48 rounded-lg object-contain mb-2"
          />
        )}
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <MarkdownRenderer content={message.content} streaming={streaming} />
        )}
      </div>
    </div>
  );
}
