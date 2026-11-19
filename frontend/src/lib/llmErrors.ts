/**
 * Shared error formatter for LLM-related backend errors.
 */

export function formatRunError(
  code: string | null | undefined,
  message: string,
): string {
  switch (code) {
    case "llm_timeout":
    case "overall_timeout":
      return message || "The request timed out. Try a narrower scope or retry.";
    case "llm_rate_limited":
      return message || "The LLM provider rate limit was reached. Wait a moment and retry.";
    case "llm_quota_exhausted":
      return (
        message ||
        "The LLM provider reports that credits or the daily limit are exhausted for this API key's project. Check billing and quota, wait for the limit to reset, or use a different key."
      );
    case "llm_model_not_found":
      return (
        message ||
        "The configured LLM_MODEL was not found by the provider. Check the model name in your environment settings."
      );
    case "llm_request_too_large":
    case "notes_too_large":
      return (
        message ||
        "The request exceeded the size or token limit. Please trim the input and retry."
      );
    case "llm_output_truncated":
      return (
        message ||
        "The response exceeded the token limit. Set LLM_DISCOVERY_MAX_OUTPUT_TOKENS to a higher value or select fewer notes."
      );
    case "llm_tool_call_failed":
      return (
        message ||
        "The model produced an invalid tool call. Try the question again."
      );
    case "llm_not_configured":
      return (
        message ||
        "LLM provider is not configured. Set LLM_API_KEY and LLM_MODEL in .env and restart the backend."
      );
    case "no_notes":
      return message || "At least one interview note is required for discovery analysis.";
    case "interrupted":
      return message || "This operation was interrupted before completion. Please retry.";
    case "run_in_progress":
      return message || "An operation is already running for this engagement. Wait for it to finish.";
    default:
      return message || "The operation failed. Please retry.";
  }
}
