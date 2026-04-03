import { useRef } from "react";
import { Paperclip, X } from "lucide-react";
import { fileToBase64, MAX_IMAGE_SIZE_BYTES } from "../../lib/api";

interface Props {
  onImageSelected: (previewUrl: string, base64: string) => void;
  onClear: () => void;
  currentPreview?: string;
  disabled?: boolean;
}

export default function ImageUpload({
  onImageSelected,
  onClear,
  currentPreview,
  disabled,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    if (file.size > MAX_IMAGE_SIZE_BYTES) {
      alert(`Image too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Max 5MB.`);
      return;
    }
    const base64 = await fileToBase64(file);
    const previewUrl = URL.createObjectURL(file);
    onImageSelected(previewUrl, base64);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    // Reset so the same file can be re-selected
    e.target.value = "";
  }

  if (currentPreview) {
    return (
      <div className="relative inline-block">
        <img
          src={currentPreview}
          alt="Selected"
          className="h-16 rounded-lg object-cover border border-gray-700"
        />
        <button
          type="button"
          onClick={onClear}
          disabled={disabled}
          className="absolute -top-1.5 -right-1.5 bg-gray-700 hover:bg-red-600 rounded-full p-0.5 transition-colors"
        >
          <X className="w-3 h-3" />
        </button>
      </div>
    );
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={handleChange}
        className="hidden"
      />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="p-2 text-gray-400 hover:text-emerald-400 disabled:opacity-40 transition-colors"
        title="Upload clinical image"
      >
        <Paperclip className="w-5 h-5" />
      </button>
    </>
  );
}
