import { createHash } from "node:crypto";

function canonical(value: any): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  return (
    "{" +
    Object.keys(value)
      .sort()
      .map((k) => JSON.stringify(k) + ":" + canonical(value[k]))
      .join(",") +
    "}"
  );
}
export function verify(receipt: any) {
  let previous = "0".repeat(64);
  for (const [index, entry] of receipt.entries.entries()) {
    const { hash, ...payload } = entry;
    if (
      entry.sequence !== index + 1 ||
      entry.session_id !== receipt.session_id ||
      entry.prev_hash !== previous
    )
      return false;
    if (createHash("sha256").update(canonical(payload)).digest("hex") !== hash)
      return false;
    previous = hash;
  }
  return previous === receipt.head;
}
