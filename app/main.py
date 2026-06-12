"""FastAPI app: a tiny web UI + JSON API in front of the ClickHouse agent."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app import agent
from app.db import get_client

app = FastAPI(title="sauna — ClickHouse + Claude agent")

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


PAGE = """
<!doctype html><meta charset="utf-8">
<title>sauna</title>
<style>
  body{font:16px system-ui;max-width:680px;margin:40px auto;padding:0 16px}
  input{width:100%;padding:10px;font-size:16px}
  button{margin-top:8px;padding:10px 16px;font-size:16px}
  pre{white-space:pre-wrap;background:#f4f1ea;padding:12px;border-radius:6px}
  .q{color:#666;font-size:13px}
</style>
<h1>sauna 🧖</h1>
<p>Ask a question about the data in ClickHouse.</p>
<input id="q" placeholder="top 5 products by total amount" autofocus>
<button onclick="go()">Ask</button>
<div id="out"></div>
<script>
async function go(){
  const q = document.getElementById('q').value;
  const out = document.getElementById('out');
  out.innerHTML = '<p>thinking…</p>';
  try {
    const r = await fetch('/ask', {method:'POST', headers:{'content-type':'application/json'},
                                   body: JSON.stringify({question:q})});
    const text = await r.text();
    let d; try { d = JSON.parse(text); } catch { d = {answer: text}; }
    if (!r.ok && !d.answer) d.answer = 'HTTP '+r.status+': '+text;
    out.innerHTML = '<pre>'+ (d.answer||JSON.stringify(d)) +'</pre>' +
      (d.queries && d.queries.length
        ? '<p class="q">SQL run:</p><pre class="q">'+ d.queries.join('\\n\\n') +'</pre>' : '');
  } catch (e) {
    out.innerHTML = '<pre>Request failed: '+ e +'</pre>';
  }
}
document.getElementById('q').addEventListener('keydown', e=>{ if(e.key==='Enter') go(); });
</script>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
