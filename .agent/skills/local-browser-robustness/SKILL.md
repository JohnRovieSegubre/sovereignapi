---
name: local-browser-robustness
description: Strategies for reliable browser interaction when native input tools fail.
---

# Robust Browser Interaction Patterns

## The Problem
Native input tools (`browser_press_key`, `click_browser_pixel`) simulate hardware events. On complex Single Page Applications (SPAs) like Google Gemini, Claude, or ChatGPT, these can:
1.  **Timeout:** The browser connection resets during long typing sequences.
2.  **Desync:** The virtual DOM doesn't register the keystrokes.
3.  **Lose Focus:** UI updates steal focus mid-typing.

## The Solution: Direct DOM Manipulation
Instead of "typing", use `execute_browser_javascript` to programmatically set state and trigger events.

### Pattern 1: Setting ContentAnEda (Rich Text Editors)
For editors like ProseMirror, Quill, or ContentEditable divs:

```javascript
(() => {
  const editor = document.querySelector('.ql-editor'); // or your selector
  if (editor) {
    // 1. Focus
    editor.focus();
    
    // 2. Set Content (Use textContent to avoid TrustedHTML errors, or innerHTML if safe)
    editor.textContent = "Your long prompt here...";
    
    // 3. Trigger Events (Crucial for React/Vue to detect change)
    editor.dispatchEvent(new Event('input', { bubbles: true }));
    return "Content set successfully";
  }
  return "Editor not found";
})()
```

### Pattern 2: Reliable Clicking
If `click_browser_pixel` fails, use JS click:

```javascript
(() => {
  const btn = document.querySelector('button[aria-label="Send message"]');
  if (btn && !btn.disabled) {
    btn.click();
    return "Clicked";
  }
  return "Button not found or disabled";
})()
```

### Pattern 3: Scrolling
Native scroll can be flaky. Use:

```javascript
(() => {
  // Scroll specific container
  const history = document.querySelector('.chat-history');
  if (history) {
    history.scrollTop = history.scrollHeight;
  } else {
    // Scroll window
    window.scrollTo(0, document.body.scrollHeight);
  }
})()
```

## When to use this Skill
*   When `browser_press_key` returns "connection reset".
*   When interacting with complex AI Chat interfaces.
*   When speed is critical (JS instant-paste vs 100ms/char typing).
