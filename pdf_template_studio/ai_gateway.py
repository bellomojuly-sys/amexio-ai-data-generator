"""Small chat adapter for direct OpenAI and the Portkey gateway."""
import json
import re
import urllib.error
import urllib.request


PORTKEY_MODELS = ("fontys-haiku-5-5", "claude-opus-5-5", "fontys-claude-sonnet-5-5")


def portkey_error_detail(error, api_key):
    """Expose the gateway's structured reason, never a raw response or key."""
    try:
        raw = error.read(16384).decode("utf-8", errors="replace")
    except (OSError, AttributeError, TypeError):
        raw = ""
    try:
        body = json.loads(raw)
    except ValueError:
        # Edge security/proxy errors may be plain text or HTML, not API JSON.
        code = re.search(r"(?i)error\s+code\s*:\s*(\d{3,5})", raw)
        if code:
            return f"Non-JSON response, error code {code.group(1)}. The request may have been blocked before reaching the model API."
        return "No JSON error details were returned. A gateway or network restriction may be involved."
    if not isinstance(body, dict):
        return ""
    detail = body.get("error", body)
    message = (detail.get("message") or detail.get("detail") or detail.get("error_description") or "") if isinstance(detail, dict) else detail
    if not isinstance(message, str):
        return ""
    message = message.replace(api_key, "[redacted]")
    message = re.sub(r"(?i)(bearer\s+|(?:x-portkey-api-key|api[_ -]?key)\s*[:=]\s*)[^\s,;\"']+",
                     r"\1[redacted]", message)
    return " ".join(message.split())[:500]


def chat_json(messages, api_key, model, provider="OpenAI", config_id=""):
    api_key, model = api_key.strip(), model.strip()
    if not api_key or not model:
        raise ValueError("Enter an API key and model slug first.")
    if provider == "Portkey":
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "User-Agent": "PDFTemplateStudio/1.0", "x-portkey-api-key": api_key}
        if config_id.strip():
            headers["x-portkey-config"] = config_id.strip()
        # Claude aliases do not necessarily support OpenAI's JSON response_format.
        # Request JSON in the prompt and validate the returned content instead.
        payload = {"model": model, "messages": messages, "max_tokens": 4096}
        request = urllib.request.Request(
            "https://api.portkey.ai/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            explanations = {
                401: "API key was rejected", 403: "request forbidden; check workspace/model permissions and routing config",
                404: "model slug or route was not found", 429: "rate limit or quota reached"}
            detail = portkey_error_detail(exc, api_key)
            summary = f"Portkey HTTP {exc.code}: {explanations.get(exc.code, 'request failed; check the model slug and config')}."
            if detail:
                summary += f" Gateway message: {detail}"
            raise ValueError(summary) from None
        except (urllib.error.URLError, TimeoutError):
            raise ValueError("Unable to reach Portkey. Check your connection and try again.") from None
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("Portkey returned no chat completion. Check the model slug and config.") from None
    elif provider == "OpenAI":
        from openai import OpenAI
        with OpenAI(api_key=api_key) as client:
            response = client.chat.completions.create(
                model=model, temperature=0, response_format={"type": "json_object"}, messages=messages)
            content = response.choices[0].message.content
    else:
        raise ValueError("Unknown AI provider.")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("The model returned no text. Try again or choose another model.")
    content = content.strip()
    if content.startswith("```") and content.endswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("The model did not return valid JSON. Try again or choose another model.") from None
    if not isinstance(data, dict) or not isinstance(data.get("fields"), list) or any(
            not isinstance(field, dict) for field in data["fields"]):
        raise ValueError("The model returned an invalid field list. Try again or choose another model.")
    return data
