"""One structured model call for the newer features (discovery planning, assistant).

Uses the same server-side configuration and shared call budget as demo/ai.py. The model returns JSON that
matches a schema; callers validate every field before acting on it.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__:
    from . import ai
    from .engine import PlanError
else:
    import ai
    from engine import PlanError


def call_json(system, payload, schema, *, max_tokens=4000, transport=None, name="respond", wait=False):
    provider, key, model = ai.configuration()
    if not ai.status()["configured"]:
        raise PlanError("Live AI is not configured on the server.")
    ai.reserve_call(wait=wait)
    body = json.dumps(payload)
    if provider == "anthropic":
        url = "https://api.anthropic.com/v1/messages"
        request_body = {"model": model, "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": body}],
                        "tools": [{"name": name, "description": "Return the structured response.", "input_schema": schema}],
                        "tool_choice": {"type": "tool", "name": name}}
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    elif provider == "gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        request_body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": body}]}],
                        "generationConfig": {"maxOutputTokens": max_tokens, "responseMimeType": "application/json", "responseJsonSchema": schema}}
        headers = {"x-goog-api-key": key}
    else:
        raise PlanError("This feature supports the anthropic and gemini providers.")
    req = Request(url, data=json.dumps(request_body).encode(), headers={**headers, "Content-Type": "application/json"}, method="POST")
    try:
        if transport:
            response = transport(req)
        else:
            with urlopen(req, timeout=60) as r:  # nosec B310 - fixed provider hosts
                response = json.load(r)
        if provider == "anthropic":
            return next(c["input"] for c in response["content"] if c.get("type") == "tool_use")
        return json.loads("".join(p.get("text", "") for p in response["candidates"][0]["content"]["parts"]))
    except HTTPError as exc:
        raise PlanError("The model provider returned HTTP %d." % exc.code) from None
    except (URLError, TimeoutError, OSError):
        raise PlanError("Could not reach the model provider.") from None
    except (KeyError, IndexError, StopIteration, TypeError, ValueError):
        raise PlanError("The model returned an unusable response.") from None
