from agent.hermes_protocol import (
    format_tool_error_response,
    format_tool_response,
    has_tool_calls,
    parse_tool_calls,
)


def test_no_tool_calls_is_final_answer():
    text = "The answer to your question is 42."
    assert has_tool_calls(text) is False
    assert parse_tool_calls(text) == []


def test_single_well_formed_tool_call():
    text = '<tool_call>\n{"name": "read_file", "arguments": {"path": "notes.txt"}}\n</tool_call>'
    assert has_tool_calls(text) is True
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    call = calls[0]
    assert call.ok
    assert call.name == "read_file"
    assert call.arguments == {"path": "notes.txt"}


def test_tool_call_with_no_arguments_key_defaults_to_empty_dict():
    text = '<tool_call>{"name": "list_files"}</tool_call>'
    calls = parse_tool_calls(text)
    assert calls[0].ok
    assert calls[0].arguments == {}


def test_multiple_tool_calls_in_one_reply():
    text = (
        '<tool_call>{"name": "write_file", "arguments": {"path": "a.txt", "content": "x"}}</tool_call>\n'
        'some stray text between calls\n'
        '<tool_call>{"name": "read_file", "arguments": {"path": "a.txt"}}</tool_call>'
    )
    calls = parse_tool_calls(text)
    assert len(calls) == 2
    assert calls[0].name == "write_file"
    assert calls[1].name == "read_file"


def test_malformed_json_does_not_raise():
    text = "<tool_call>{not valid json at all</tool_call>"
    calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].ok is False
    assert "invalid JSON" in calls[0].error


def test_missing_name_key():
    text = '<tool_call>{"arguments": {"path": "a.txt"}}</tool_call>'
    calls = parse_tool_calls(text)
    assert calls[0].ok is False
    assert "name" in calls[0].error


def test_arguments_not_an_object():
    text = '<tool_call>{"name": "read_file", "arguments": "not-a-dict"}</tool_call>'
    calls = parse_tool_calls(text)
    assert calls[0].ok is False
    assert "arguments" in calls[0].error


def test_top_level_not_an_object():
    text = "<tool_call>[1, 2, 3]</tool_call>"
    calls = parse_tool_calls(text)
    assert calls[0].ok is False


def test_format_tool_response_roundtrip():
    rendered = format_tool_response("read_file", {"content": "hello"})
    assert rendered.startswith("<tool_response>")
    assert rendered.endswith("</tool_response>")
    assert '"name": "read_file"' in rendered


def test_format_tool_error_response_handles_unknown_name():
    rendered = format_tool_error_response(None, "boom")
    assert '"name": "unknown"' in rendered
    assert '"error": "boom"' in rendered
