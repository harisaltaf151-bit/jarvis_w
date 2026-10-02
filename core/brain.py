"""
JARVIS AI Brain
Translates natural language commands into structured tool calls.
Uses Groq (free, fast) as the AI engine — llama-3.3-70b.
"""

import json
import os
import re

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("JARVIS_MODEL", "llama-3.3-70b-versatile")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are JARVIS, a Personal AI Operating System.

You receive natural language commands and must respond with a JSON object 
specifying what tool(s) to call to fulfill the command.

Available tools and actions:
- app:      open(app, args?), close(app), list_running(), open_url(url), open_file(path), set_volume(level)
- files:    list_dir(path?, show_hidden?), search(query, path?, file_type?), read_file(path), 
            write_file(path, content, mode?), create_folder(path), copy(src, dst), 
            move(src, dst), delete(path, confirm), recent_files(path?, days?, limit?), get_info(path)
- browser:  navigate(url), search(query, engine?), get_page_text(url?), screenshot(save_path?),
            new_tab(url?), close_tab(), scroll(direction, amount?)
- email:    send(to, subject, body, cc?, bcc?), fetch_inbox(count?, unread_only?),
            search_emails(query), reply(original_subject, to, body), draft(to, subject, context)
- system:   snapshot(), top_processes(n?), disk_usage(), battery(), kill_process(pid)
- terminal: run(command), run_python(code), run_script(path), cd(path), pwd(),
            install_package(package, manager?), open_terminal_window()
- screen:   screenshot(save_path?), hotkey(*keys), type_text(text), press_key(key), 
            click(x?, y?), scroll(clicks)
- calendar: list_events(days?), today(), create_event(title, start, end?, location?, notes?),
            delete_event(id), search(query), quick_add(natural)

Respond ONLY with valid JSON — no markdown, no explanation, just raw JSON:
{
  "speech": "What JARVIS says to the user (1-2 sentences, in-character)",
  "actions": [
    { "tool": "tool_name", "action": "action_name", "params": { ... } }
  ],
  "followup": "Optional follow-up question or status message"
}

Rules:
- Be decisive. For "open Chrome" → app.open. For "search X" → browser.search.
- For "files modified today" → files.recent_files with days=1.
- For "write email to X about Y" → email.draft first.
- Chain multiple actions when needed.
- NEVER wrap JSON in ```code blocks```. Return raw JSON only.
"""


async def interpret_command(user_input: str, history: list = None) -> dict:
    """
    Send user command to Groq, get back structured tool calls.
    Returns { speech, actions: [{tool, action, params}], followup }
    """
    import urllib.request

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if history:
        for h in history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": user_input})

    payload = json.dumps({
        "model":       GROQ_MODEL,
        "messages":    messages,
        "max_tokens":  1024,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(
        GROQ_URL,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())

        raw = data["choices"][0]["message"]["content"].strip()

        # strip markdown fences if model added them anyway
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*",     "", raw)
        raw = re.sub(r"\s*```$",     "", raw)

        return json.loads(raw)

    except Exception as exc:
        return {
            "speech":  f"Neural link error: {exc}",
            "actions": [],
        }


async def interpret_and_execute(user_input: str, tools: dict,
                                history: list = None) -> dict:
    """Full pipeline: interpret → execute all actions → return combined result."""
    plan    = await interpret_command(user_input, history)
    results = []

    for action_spec in plan.get("actions", []):
        tool_name   = action_spec.get("tool", "")
        action_name = action_spec.get("action", "")
        params      = action_spec.get("params", {})

        tool = tools.get(tool_name)
        if not tool:
            results.append({"error": f"Tool not found: {tool_name}"})
            continue

        handler = getattr(tool, action_name, None)
        if not handler:
            results.append({"error": f"Action not found: {tool_name}.{action_name}"})
            continue

        try:
            import asyncio
            if asyncio.iscoroutinefunction(handler):
                r = await handler(**params)
            else:
                r = await asyncio.to_thread(handler, **params)
            results.append({"tool": tool_name, "action": action_name, "result": r})
        except Exception as exc:
            results.append({"error": str(exc)})

    return {
        "speech":   plan.get("speech", ""),
        "actions":  plan.get("actions", []),
        "results":  results,
        "followup": plan.get("followup", ""),
    }
