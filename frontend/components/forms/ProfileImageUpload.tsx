"use client";

import * as React from "react";
import Image from "next/image";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useApi } from "@/lib/api/useApi";
import { publicFileUrl } from "@/lib/api/client";

interface UploadedFile {
  id: string;
}

interface ProfileImageUploadProps {
  fileId: string | null;
  onChange: (fileId: string | null) => void;
  onUploadingChange?: (uploading: boolean) => void;
  label: string;
}

export function ProfileImageUpload({
  fileId,
  onChange,
  onUploadingChange,
  label,
}: ProfileImageUploadProps) {
  const api = useApi();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  async function upload(file?: File) {
    if (!file) return;
    setError(null);
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Choose a JPG, PNG, or WebP image.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The image must be 10 MB or smaller.");
      return;
    }

    setPreviewUrl(URL.createObjectURL(file));
    setProgress(0);
    const formData = new FormData();
    formData.append("file", file);
    setUploading(true);
    onUploadingChange?.(true);
    try {
      const saved = await api.postWithProgress<UploadedFile>(
        "/files/profile-image",
        formData,
        setProgress,
      );
      onChange(saved.id);
      setProgress(100);
      setPreviewUrl(null);
    } catch (e) {
      setPreviewUrl(null);
      setError(e instanceof Error ? e.message : "Could not upload the image.");
    } finally {
      setUploading(false);
      onUploadingChange?.(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  const imageSrc = previewUrl ?? (fileId ? publicFileUrl(fileId) : null);
  return (
    <div className="flex flex-col gap-3">
      {imageSrc ? (
        <Image
          src={imageSrc}
          alt={label}
          width={112}
          height={112}
          unoptimized
          className="h-28 w-28 rounded-full border border-slate-200 object-cover"
        />
      ) : (
        <div
          aria-label={`${label} preview`}
          className="flex h-28 w-28 items-center justify-center rounded-full bg-slate-100 text-sm text-slate-500"
        >
          No image
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <input
          ref={inputRef}
          className="sr-only"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label={`Choose ${label.toLowerCase()}`}
          onChange={(event) => void upload(event.currentTarget.files?.[0])}
        />
        <Button
          type="button"
          variant="outline"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? "Uploading…" : fileId ? "Change image" : `Add ${label}`}
        </Button>
        {fileId ? (
          <Button
            type="button"
            variant="ghost"
            disabled={uploading}
            onClick={() => onChange(null)}
          >
            Remove
          </Button>
        ) : null}
      </div>
      <p className="text-xs text-slate-500">
        JPG, PNG, or WebP. Maximum file size: 10 MB.
      </p>
      {uploading ? (
        <div className="max-w-xs">
          <progress
            className="w-full"
            value={progress}
            max={100}
            aria-label="Image upload progress"
          />
          <span className="text-xs text-slate-600">{progress}% uploaded</span>
        </div>
      ) : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}
    </div>
  );
}
