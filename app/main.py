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


# Buyer-agent-facing chat view, styled to match the Traverum design system used
# by the provider dashboard (frontend/): warm white, olive primary, DM Sans,
# borders not shadows, no emojis. Stateless — each question hits /ask on its own.
PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Löyly — booking agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root{
    --background:#fefcf9; --accent:#f4efe6;
    --foreground:rgb(55,53,47); --secondary:rgba(55,53,47,0.65);
    --muted:rgba(55,53,47,0.4); --border:rgba(55,53,47,0.09);
    --primary:#5a6b4e; --primary-fg:#fefcf9; --walnut:#5d4631;
    --destructive:#b8866b; --beige:rgba(242,241,238,0.6);
  }
  *{box-sizing:border-box}
  html,body{height:100%}
  body{
    margin:0; background:var(--background); color:var(--foreground);
    font-family:"DM Sans",sans-serif; font-weight:300; font-size:15px;
  }
  main{max-width:680px; height:100dvh; margin:0 auto; padding:40px 24px 24px;
       display:flex; flex-direction:column}
  h1{margin:0; font-size:20px; font-weight:300}
  .sub{margin:4px 0 0; font-size:14px; color:var(--muted)}
  header{padding-bottom:16px; border-bottom:1px solid var(--border)}

  #log{flex:1; overflow-y:auto; padding:20px 0; display:flex;
       flex-direction:column; gap:12px}
  .msg{max-width:85%; padding:10px 14px; border-radius:8px; line-height:1.5;
       white-space:pre-wrap; overflow-wrap:break-word}
  .msg.user{align-self:flex-end; background:var(--beige)}
  .msg.agent{align-self:flex-start; border:1px solid var(--border)}
  .msg.err{border-color:var(--destructive); color:var(--destructive)}

  .msg details{margin-top:8px; border-top:1px solid var(--border); padding-top:8px}
  .msg summary{cursor:pointer; font-size:12px; color:var(--muted);
               list-style:none; user-select:none}
  .msg summary::before{content:"› "; display:inline-block; transition:transform .15s}
  .msg details[open] summary::before{transform:rotate(90deg)}
  .msg .work{margin:8px 0 0; padding:8px 10px; border-radius:3px; background:var(--beige);
             font-family:ui-monospace,monospace; font-size:11.5px; color:var(--secondary);
             white-space:pre-wrap; overflow-wrap:break-word}

  .dots{display:inline-flex; gap:4px; padding:4px 0}
  .dots span{width:6px; height:6px; border-radius:50%; background:var(--muted);
             animation:pulse 1.2s ease-in-out infinite}
  .dots span:nth-child(2){animation-delay:.2s}
  .dots span:nth-child(3){animation-delay:.4s}
  @keyframes pulse{0%,80%,100%{opacity:.25}40%{opacity:1}}

  #chips{display:flex; flex-wrap:wrap; gap:8px; padding-bottom:12px}
  .chip{border:1px solid var(--border); background:transparent; border-radius:8px;
        padding:6px 12px; font:inherit; font-size:13px; color:var(--secondary);
        cursor:pointer; transition:background-color .15s}
  .chip:hover{background:var(--accent)}

  #composer{display:flex; gap:8px}
  #q{flex:1; border:0; border-radius:3px; background:var(--beige); padding:10px 14px;
     font:inherit; color:var(--foreground); outline:none; transition:background-color .15s}
  #q::placeholder{color:var(--muted)}
  #q:focus{background:rgba(242,241,238,1)}
  #send{display:flex; align-items:center; justify-content:center; width:40px;
        border:0; border-radius:3px; background:var(--primary); color:var(--primary-fg);
        cursor:pointer; transition:background-color .15s}
  #send:hover{background:var(--walnut)}
  #send:disabled,#q:disabled{opacity:.4}
</style>
</head>
<body>
<main>
  <header>
    <h1>Löyly</h1>
    <p class="sub">Ask the booking agent about sauna experiences.</p>
  </header>

  <div id="log"></div>

  <div id="chips">
    <button class="chip">What's available next week?</button>
    <button class="chip">Book the earliest open session for the raft cruise</button>
    <button class="chip">How much revenue is in booked sessions?</button>
  </div>

  <form id="composer">
    <input id="q" placeholder="Ask anything, or ask to book a session" autocomplete="off" autofocus>
    <button id="send" type="submit" title="Send" aria-label="Send">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="m5 12 14 0"></path><path d="m13 6 6 6-6 6"></path>
      </svg>
    </button>
  </form>
</main>

<script>
const log = document.getElementById('log');
const chips = document.getElementById('chips');
const form = document.getElementById('composer');
const input = document.getElementById('q');
const send = document.getElementById('send');

function bubble(cls){
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function showAnswer(el, d, isError){
  // textContent first (escapes any HTML), then upgrade markdown bold only
  el.textContent = d.answer || JSON.stringify(d);
  el.innerHTML = el.innerHTML.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
  if (isError) el.classList.add('err');
  if (d.queries && d.queries.length){
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = 'Show work · ' + d.queries.length +
      (d.queries.length === 1 ? ' step' : ' steps');
    details.appendChild(summary);
    for (const q of d.queries){
      const pre = document.createElement('div');
      pre.className = 'work';
      pre.textContent = q.trim();
      details.appendChild(pre);
    }
    el.appendChild(details);
  }
  log.scrollTop = log.scrollHeight;
}

async function ask(question){
  if (!question.trim()) return;
  chips.style.display = 'none';
  input.value = '';
  input.disabled = send.disabled = true;

  bubble('user').textContent = question;
  const pending = bubble('agent');
  pending.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';

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
    showAnswer(pending, d, isError);
  } catch (e) {
    showAnswer(pending, {answer: 'Request failed: ' + e}, true);
  } finally {
    input.disabled = send.disabled = false;
    input.focus();
  }
}

form.addEventListener('submit', e => { e.preventDefault(); ask(input.value); });
chips.addEventListener('click', e => {
  if (e.target.classList.contains('chip')) ask(e.target.textContent);
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
