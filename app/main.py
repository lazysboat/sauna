"""FastAPI app: a tiny web UI + JSON API in front of the ClickHouse agent."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app import agent
from app.db import get_client

app = FastAPI(title="sauna — ClickHouse + Claude agent")

# The provider dashboard (frontend/, Next.js dev on :3000) calls this API from
# the browser. Wide-open CORS — hackathon demo, no auth.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy, cached ClickHouse client: the app boots (and /health works) even if
# ClickHouse isn't reachable yet — only /ask needs the connection. Shared across
# requests for this demo; recreate per-request if you add real concurrency.
_ch = None


def _client():
    global _ch
    if _ch is None:
        _ch = get_client()
    return _ch


class Ask(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/ask")
def ask(body: Ask):
    try:
        return agent.answer(body.question, _client())
    except Exception as exc:  # noqa: BLE001 - surface a readable message to the UI
        return {"answer": f"Error: {exc}", "queries": []}


# Buyer-agent-facing view: a deliberate, clean dark-terminal aesthetic to signal
# "this is the machine interface" — in contrast to the warm Traverum provider
# dashboard on :3000. Stateless — each question hits /ask on its own.
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>löyly — booking agent</title>
<!-- OpenUI browser bundle: React + the OpenUI Lang parser/renderer + component
     library, served as one IIFE that sets window.__OpenUI. Pinned for repro. -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@openuidev/browser-bundle@0.1.1/dist/openui-styles.css">
<script src="https://cdn.jsdelivr.net/npm/@openuidev/browser-bundle@0.1.1/dist/openui-bundle.min.js"></script>
<style>
  :root{
    --bg:#16150f; --fg:#d6d3cc; --dim:rgba(214,211,204,0.45);
    --line:rgba(214,211,204,0.12); --accent:#8aa37a; --err:#c98a6b;
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; background:var(--bg); color:var(--fg);
    font-family:ui-monospace,"JetBrains Mono","Cascadia Code",Menlo,Consolas,monospace;
    font-size:14px; line-height:1.6;
  }
  ::selection{background:var(--accent); color:var(--bg)}
  main{max-width:760px; height:100dvh; margin:0 auto; padding:28px 24px 20px;
       display:flex; flex-direction:column}

  header{display:flex; align-items:center; gap:8px; padding-bottom:12px;
         border-bottom:1px solid var(--line); color:var(--dim)}
  .led{width:7px; height:7px; border-radius:50%; background:var(--accent)}

  #log{flex:1; overflow-y:auto; padding:16px 0}
  .turn{margin-bottom:14px; white-space:pre-wrap; overflow-wrap:break-word}
  .turn.user .prompt{color:var(--accent)}
  .turn.agent{padding-left:14px}
  .turn.agent strong{color:var(--accent); font-weight:600}
  .turn.agent.err{color:var(--err)}

  .turn details{margin-top:6px}
  .turn summary{cursor:pointer; color:var(--dim); list-style:none; user-select:none}
  .turn summary::before{content:"\\25B8 "}
  .turn details[open] summary::before{content:"\\25BE "}
  .work{color:var(--dim); padding:2px 0 2px 14px; white-space:pre-wrap;
        overflow-wrap:break-word; font-size:12.5px}

  /* OpenUI renders its own (light) card UI; give it room and a rounded frame so
     it reads as a distinct rich block inside the dark transcript. */
  .openui{margin:10px 0 4px; border-radius:10px; overflow:hidden;
          background:#fff; color-scheme:light}
  .openui:empty{display:none}

  #suggested{color:var(--dim); padding-bottom:14px}
  #suggested .cmd{display:block; background:none; border:0; padding:1px 0;
                  font:inherit; color:var(--dim); cursor:pointer; text-align:left}
  #suggested .cmd:hover{color:var(--accent)}

  #composer{display:flex; gap:8px; align-items:baseline; padding-top:12px;
            border-top:1px solid var(--line)}
  #composer .prompt{color:var(--accent)}
  #q{flex:1; background:transparent; border:0; outline:none; font:inherit;
     color:var(--fg); caret-color:var(--accent); padding:0}
  #q::placeholder{color:var(--dim)}
  #q:disabled{opacity:.4}
</style>
</head>
<body>
<main>
  <header>
    <span class="led"></span>
    <span>löyly booking agent v1 — connected</span>
  </header>

  <div id="log"></div>

  <div id="suggested">suggested:
    <button class="cmd">[1] find a smoke sauna in Tampere for 10 people</button>
    <button class="cmd">[2] book the earliest open session for the raft cruise</button>
    <button class="cmd">[3] how much revenue is in booked sessions?</button>
  </div>

  <form id="composer">
    <span class="prompt">$</span>
    <input id="q" placeholder="ask anything, or ask to book a session" autocomplete="off"
           spellcheck="false" autofocus>
  </form>
</main>

<script>
const log = document.getElementById('log');
const suggested = document.getElementById('suggested');
const form = document.getElementById('composer');
const input = document.getElementById('q');
const FRAMES = ['\\u280B','\\u2819','\\u2839','\\u2838','\\u283C','\\u2834','\\u2826','\\u2827','\\u2807','\\u280F'];

function turn(cls){
  const el = document.createElement('div');
  el.className = 'turn ' + cls;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

// When a button inside an OpenUI card is clicked (e.g. "Book Sat 18:00") the
// renderer fires onAction with a @ToAssistant message — we feed it straight back
// into the chat as the next question, closing the loop. Defensive about the
// action object's shape: pull the first plausible message string out of it.
function actionMessage(a){
  let found = null;
  (function walk(o){
    if (found != null || o == null || typeof o !== 'object') return;
    for (const k of ['message','text','content','value','prompt','label']){
      if (typeof o[k] === 'string' && o[k].trim()){ found = o[k]; return; }
    }
    for (const v of Object.values(o)) walk(v);
  })(a);
  return found;
}

function renderUI(container, lang){
  const U = window.__OpenUI;
  if (!U || !U.Renderer){ return false; }
  try {
    const root = U.createRoot(container);
    root.render(U.React.createElement(U.Renderer, {
      response: lang,
      library: U.openuiChatLibrary,
      isStreaming: false,
      onAction: a => { const m = actionMessage(a); if (m) ask(m); },
    }));
    return true;
  } catch (e) {
    console.error('OpenUI render failed', e);
    return false;
  }
}

function showAnswer(el, d, isError){
  el.textContent = '';
  // Plain-text prose (always escaped; only OpenUI Lang bypasses escaping, via
  // the trusted renderer). Upgrade **bold** to <strong> like before.
  const prose = document.createElement('div');
  prose.textContent = d.answer || (d.ui ? '' : JSON.stringify(d));
  prose.innerHTML = prose.innerHTML.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
  if (isError){
    el.classList.add('err');
    prose.textContent = '! ' + prose.textContent;
  }
  if (prose.textContent) el.appendChild(prose);

  // Rich OpenUI sauna cards, when the agent chose to present them.
  if (d.ui && !isError){
    const card = document.createElement('div');
    card.className = 'openui';
    el.appendChild(card);
    if (!renderUI(card, d.ui)) card.remove();  // bundle unavailable -> drop frame
  }

  if (d.queries && d.queries.length){
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'show work \\u00B7 ' + d.queries.length +
      (d.queries.length === 1 ? ' step' : ' steps');
    details.appendChild(summary);
    for (const q of d.queries){
      const w = document.createElement('div');
      w.className = 'work';
      w.textContent = '\\u00B7 ' + q.trim();
      details.appendChild(w);
    }
    el.appendChild(details);
  }
  log.scrollTop = log.scrollHeight;
}

async function ask(question){
  if (!question.trim()) return;
  suggested.style.display = 'none';
  input.value = '';
  input.disabled = true;

  const u = turn('user');
  u.innerHTML = '<span class="prompt">$ </span>';
  u.appendChild(document.createTextNode(question));

  const pending = turn('agent');
  pending.style.color = 'var(--dim)';
  let f = 0;
  pending.textContent = FRAMES[0] + ' thinking\\u2026';
  const spin = setInterval(() => {
    f = (f + 1) % FRAMES.length;
    pending.textContent = FRAMES[f] + ' thinking\\u2026';
  }, 90);

  try {
    const r = await fetch('/ask', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({question}),
    });
    const text = await r.text();
    let d; try { d = JSON.parse(text); } catch { d = {answer: text}; }
    if (!r.ok && !d.answer) d.answer = 'HTTP ' + r.status + ': ' + text;
    const isError = !r.ok || (d.answer || '').startsWith('Error:');
    clearInterval(spin);
    pending.style.color = '';
    showAnswer(pending, d, isError);
  } catch (e) {
    clearInterval(spin);
    pending.style.color = '';
    showAnswer(pending, {answer: 'request failed: ' + e}, true);
  } finally {
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener('submit', e => { e.preventDefault(); ask(input.value); });
suggested.addEventListener('click', e => {
  const b = e.target.closest('.cmd');
  if (b) ask(b.textContent.replace(/^\\[\\d\\]\\s*/, ''));
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


# Marketplace REST API (provider CRUD + agent-facing catalog/book).
# Imported last: crud reaches back into this module for the cached client.
from app.crud import router as crud_router  # noqa: E402

app.include_router(crud_router)
