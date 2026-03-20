import type { ReactNode } from "react"
import { useId, useMemo } from "react"

import type { UploadHookControl } from "@better-upload/client"
import { Loader2, Upload } from "lucide-react"
import { useDropzone, type Accept } from "react-dropzone"

import { cn } from "@/lib/utils"

type UploadDropzoneProps = {
  control?: UploadHookControl<true>;
  onFilesSelected?: (files: File[]) => void;
  id?: string;
  accept?: string;
  metadata?: Record<string, unknown>;
  description?:
    | {
        fileTypes?: string;
        maxFileSize?: string;
        maxFiles?: number;
      }
    | string;
  title?: string;
  icon?: ReactNode;
  multiple?: boolean;
  disabled?: boolean;
  uploadOverride?: (
    ...args: Parameters<UploadHookControl<true>["upload"]>
  ) => void;
}

function toAcceptConfig(accept?: string): Accept | undefined {
  if (!accept) return undefined

  const tokens = accept
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean)

  if (tokens.length === 0) return undefined

  const config: Accept = {}
  for (const token of tokens) {
    if (token === ".pdf") {
      config["application/pdf"] = [".pdf"]
      continue
    }
    if (token.startsWith(".")) {
      const current = config["image/*"] ?? []
      config["image/*"] = [...current, token]
      continue
    }
    config[token] = []
  }
  return config
}

export function UploadDropzone({
  control,
  onFilesSelected,
  id: _id,
  accept,
  metadata,
  description,
  title = "Drag and drop files here",
  icon,
  multiple = true,
  disabled = false,
  uploadOverride,
}: UploadDropzoneProps) {
  const id = useId()
  const upload = control?.upload
  const isPending = control?.isPending ?? false
  const isDisabled = disabled || isPending
  const acceptConfig = useMemo(() => toAcceptConfig(accept), [accept])

  const { getRootProps, getInputProps, isDragActive, inputRef } = useDropzone({
    onDrop: (files) => {
      if (files.length > 0 && !isDisabled) {
        const nextFiles = multiple ? files : files.slice(0, 1)
        if (upload) {
          if (uploadOverride) {
            uploadOverride(nextFiles, { metadata })
          } else {
            upload(nextFiles, { metadata })
          }
        } else {
          onFilesSelected?.(nextFiles)
        }
      }
      if (inputRef.current) {
        inputRef.current.value = ""
      }
    },
    noClick: false,
    multiple,
    disabled: isDisabled,
    accept: acceptConfig,
  })

  return (
    <div
      className={cn(
        "border-input text-foreground relative rounded-[var(--layout-outer-radius)] border bg-background p-[var(--layout-inner-padding)] transition-colors duration-200",
        {
          "border-primary/70 bg-muted/30": isDragActive,
          "opacity-70": isDisabled,
        },
      )}
    >
      <div
        {...getRootProps()}
        className={cn(
          "flex w-full min-w-72 cursor-pointer flex-col items-center justify-center rounded-[var(--layout-inner-radius)] bg-transparent px-[calc(var(--layout-inner-padding)*0.9)] py-[calc(var(--layout-inner-padding)*2.2)] text-center transition-colors duration-200",
          {
            "text-muted-foreground cursor-not-allowed": isDisabled,
            "hover:bg-muted/20": !isDisabled,
            "opacity-0": isDragActive,
          },
        )}
      >
        <div className="mb-3 text-foreground">
          {isPending ? (
            <Loader2 className="size-6 animate-spin" />
          ) : (
            icon ?? <Upload className="size-6" />
          )}
        </div>

        <div className="space-y-1 text-center">
          <p className="text-sm font-semibold">{title}</p>

          <p className="text-muted-foreground max-w-72 text-xs leading-relaxed">
            {typeof description === 'string' ? (
              description
            ) : (
              <>
                {description?.maxFiles &&
                  `You can upload ${description.maxFiles} file${description.maxFiles !== 1 ? 's' : ''}.`}{' '}
                {description?.maxFileSize &&
                  `${description.maxFiles !== 1 ? 'Each u' : 'U'}p to ${description.maxFileSize}.`}{' '}
                {description?.fileTypes && `Accepted ${description.fileTypes}.`}
              </>
            )}
          </p>
        </div>

        <input
          {...getInputProps()}
          type="file"
          multiple={multiple}
          id={_id || id}
          accept={accept}
          disabled={isDisabled}
        />
      </div>

      {isDragActive && (
        <div className="pointer-events-none absolute inset-[var(--layout-inner-padding)] rounded-[var(--layout-inner-radius)]">
          <div className="bg-muted/85 flex size-full flex-col items-center justify-center rounded-[var(--layout-inner-radius)]">
            <div className="my-2">
              <Upload className="size-6" />
            </div>

            <p className="mt-3 text-sm font-semibold">Drop files here</p>
          </div>
        </div>
      )}
    </div>
  )
}
