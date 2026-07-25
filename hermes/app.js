(function () {
  "use strict";

  // Dumb client: no model-specific logic. Just sends whatever the user
  // types as an OpenAI-format chat message and renders whatever comes
  // back. Conversation history lives only in this page's memory.

  var conversationEl = document.getElementById("conversation");
  var statusEl = document.getElementById("status-bar");
  var formEl = document.getElementById("composer");
  var inputEl = document.getElementById("message-input");
  var sendButtonEl = document.getElementById("send-button");

  /** @type {{role: string, content: string}[]} */
  var history = [];

  function renderMessage(role, content) {
    var el = document.createElement("div");
    el.className = "message " + role;
    el.textContent = content;
    conversationEl.appendChild(el);
    conversationEl.scrollTop = conversationEl.scrollHeight;
    return el;
  }

  function setBusy(busy) {
    sendButtonEl.disabled = busy;
    inputEl.disabled = busy;
    statusEl.textContent = busy ? "Waiting for a response..." : "";
  }

  function extractAssistantText(payload) {
    try {
      var choice = payload && payload.choices && payload.choices[0];
      var content = choice && choice.message && choice.message.content;
      if (typeof content === "string") {
        return content;
      }
      // Some responses may return content as an array of parts.
      if (Array.isArray(content)) {
        return content
          .map(function (part) {
            return typeof part === "string" ? part : part && part.text;
          })
          .filter(Boolean)
          .join("");
      }
    } catch (err) {
      // fall through to null
    }
    return null;
  }

  async function sendMessage(text) {
    history.push({ role: "user", content: text });
    renderMessage("user", text);

    setBusy(true);
    try {
      var response = await fetch(
        window.BACKEND_URL.replace(/\/+$/, "") + "/v1/chat/completions",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: history }),
        }
      );

      var data = await response.json().catch(function () {
        return null;
      });

      if (!response.ok) {
        var message =
          (data && data.error && data.error.message) ||
          "Request failed (" + response.status + ").";
        renderMessage("error", message);
        return;
      }

      var assistantText = extractAssistantText(data);
      if (assistantText === null) {
        renderMessage("error", "Received an unexpected response from the server.");
        return;
      }

      history.push({ role: "assistant", content: assistantText });
      renderMessage("assistant", assistantText);
    } catch (err) {
      renderMessage("error", "Could not reach the backend.");
    } finally {
      setBusy(false);
    }
  }

  formEl.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = inputEl.value.trim();
    if (!text) {
      return;
    }
    inputEl.value = "";
    sendMessage(text);
  });

  inputEl.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      formEl.requestSubmit();
    }
  });
})();
