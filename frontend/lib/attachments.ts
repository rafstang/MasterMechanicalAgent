const ACCEPTED_EXTENSIONS = new Set(["pdf", "csv", "txt", "xlsx", "xls"]);
const ACCEPTED_MIME_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/csv",
  "application/csv",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]);

export const ATTACHMENT_MAX_SIZE = 5 * 1024 * 1024;

export const ATTACHMENT_ACCEPT =
  ".pdf,.csv,.txt,.xlsx,.xls,text/plain,text/csv,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export type CopilotAttachmentUploadResult = {
  type: "data";
  value: string;
  mimeType: string;
  metadata?: Record<string, unknown>;
};

function extensionOf(filename: string): string {
  const idx = filename.lastIndexOf(".");
  return idx >= 0 ? filename.slice(idx + 1).toLowerCase() : "";
}

function isAcceptedFile(file: File): boolean {
  const ext = extensionOf(file.name);
  if (ACCEPTED_EXTENSIONS.has(ext)) return true;
  if (file.type && ACCEPTED_MIME_TYPES.has(file.type)) return true;
  return false;
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("Failed to read file"));
        return;
      }
      const comma = reader.result.indexOf(",");
      resolve(comma >= 0 ? reader.result.slice(comma + 1) : reader.result);
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

export async function uploadAttachment(file: File): Promise<CopilotAttachmentUploadResult> {
  if (file.size > ATTACHMENT_MAX_SIZE) {
    throw new Error(`File exceeds ${Math.round(ATTACHMENT_MAX_SIZE / (1024 * 1024))} MB limit.`);
  }

  if (!isAcceptedFile(file)) {
    throw new Error("Only PDF, CSV, text, and Excel files are supported.");
  }

  const value = await readFileAsBase64(file);
  const mimeType = file.type || "application/octet-stream";
  return {
    type: "data",
    value,
    mimeType,
    metadata: { filename: file.name },
  };
}

export function attachmentUploadErrorMessage(reason: string): string {
  switch (reason) {
    case "file-too-large":
      return "That file is too large. Maximum size is 5 MB.";
    case "invalid-type":
      return "Unsupported file type. Use PDF, CSV, text, or Excel.";
    case "upload-failed":
      return "Upload failed. Please try again.";
    default:
      return "Upload failed.";
  }
}
