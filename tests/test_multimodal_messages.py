"""Tests for AG-UI multimodal message validation (PDF attachments from CopilotKit)."""

from ag_ui.core import DocumentInputContent, InputContentDataSource, RunAgentInput, TextInputContent, UserMessage


def test_run_agent_input_accepts_document_multimodal_user_message():
    """CopilotKit sends type=document with source.type=data — must not 422 on the backend."""
    message = UserMessage(
        id="msg-1",
        role="user",
        content=[
            TextInputContent(type="text", text="Summarize this pdf"),
            DocumentInputContent(
                type="document",
                source=InputContentDataSource(
                    type="data",
                    value="JVBERi0xLjQK",
                    mime_type="application/pdf",
                ),
            ),
        ],
    )
    payload = RunAgentInput(
        thread_id="thread-1",
        run_id="run-1",
        state={},
        messages=[message],
        tools=[],
        context=[],
        forwarded_props={},
    )
    assert payload.messages[0].content[1].type == "document"


def test_document_content_converts_to_adk_part():
    from ag_ui_adk.utils.converters import convert_message_content_to_parts

    content = [
        TextInputContent(type="text", text="Summarize this pdf"),
        DocumentInputContent(
            type="document",
            source=InputContentDataSource(
                type="data",
                value="JVBERi0xLjQK",
                mime_type="application/pdf",
            ),
        ),
    ]
    parts = convert_message_content_to_parts(content)
    assert len(parts) == 2
    assert parts[0].text == "Summarize this pdf"
    assert parts[1].inline_data is not None
    assert parts[1].inline_data.mime_type == "application/pdf"
