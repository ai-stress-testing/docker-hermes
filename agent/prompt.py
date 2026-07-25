"""The Hermes-2-Pro / Hermes-3 function-calling system prompt template and
the JSON-schema tool definitions it embeds.

This follows NousResearch's documented Hermes function-calling format: the
system prompt describes the calling convention in prose, then lists the
available tools as JSON schemas inside <tools></tools> tags. The model is
expected to reply with zero or more <tool_call>{"name": ..., "arguments":
...}</tool_call> blocks.
"""

from __future__ import annotations

import json

# Tool schemas in the "OpenAI function" shape, which is what the Hermes
# prompt format expects to see embedded in <tools>.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Create or overwrite a file inside the sandboxed workspace. "
                "Creates parent directories as needed. Paths are relative to "
                "the workspace root; absolute paths and '..' traversal are "
                "rejected."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path within the workspace to write to.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full text content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read and return the contents of a file inside the sandboxed "
                "workspace. Paths are relative to the workspace root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path within the workspace to read.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files and directories at a path inside the sandboxed "
                "workspace. Paths are relative to the workspace root."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path within the workspace to list. Defaults to the workspace root.",
                    },
                },
                "required": [],
            },
        },
    },
]

_SYSTEM_PROMPT_TEMPLATE = """You are a function calling AI model. You are provided with function signatures within <tools></tools> XML tags. You may call one or more functions to assist with the user query. Don't make assumptions about what values to plug into functions. For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags as follows:
<tool_call>
{{"name": <function-name>, "arguments": <args-dict>}}
</tool_call>

Here are the available tools:
<tools>
{tools_json}
</tools>

When you have gathered enough information to answer the user's request, respond with a normal message containing no <tool_call> tags — that message is treated as your final answer and ends the conversation. Only call tools that are listed above, and only with arguments the user's request actually justifies; never assume file paths or content that weren't given to you."""


def build_system_prompt() -> str:
    """Render the Hermes function-calling system prompt with the tool
    schemas embedded as JSON.
    """
    tools_json = json.dumps(TOOL_SCHEMAS, indent=2)
    return _SYSTEM_PROMPT_TEMPLATE.format(tools_json=tools_json)
