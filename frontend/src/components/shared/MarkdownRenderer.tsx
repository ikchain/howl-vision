import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  content: string;
  streaming?: boolean;
}

export default function MarkdownRenderer({ content, streaming }: Props) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Clinical section headers in emerald for visual hierarchy
          strong: ({ children }) => (
            <strong className="text-emerald-400 font-semibold">{children}</strong>
          ),
          li: ({ children }) => (
            <li className="text-gray-200 my-0.5">{children}</li>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
      {streaming && (
        <span className="inline-block w-2 h-4 bg-emerald-400 animate-pulse ml-0.5 align-text-bottom" />
      )}
    </div>
  );
}
