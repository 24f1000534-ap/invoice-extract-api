# Invoice Extraction API — Beginner's Walkthrough

This solves the "Fixed Schema Invoice Extraction API" assignment. Here's
everything explained like you've never touched FastAPI before.

## 1. What are we actually building?

A tiny web server with ONE door (endpoint): `POST /extract`.

- You knock on that door with some raw invoice text.
- It reads the text, pulls out 6 pieces of information, and hands them
  back to you as JSON.
- If it can't find something, it says `null` instead of guessing.

That's it. No database, no login, no fancy UI.

## 2. The 3 files that make this work

```
invoice-api/
├── extractor.py      <- the "brain": regex rules that find each field
├── main.py           <- the "front door": FastAPI app + the /extract route
└── requirements.txt   <- list of Python packages needed to run it
```

### extractor.py — how field-finding actually works

Real invoices are messy — different labels, different date formats,
Indian-style number commas (like `1,40,000.00`). Instead of using an
LLM (slower, needs an API key, costs money), this uses **regex
patterns** tried in order until one matches:

- `invoice_no`: looks for "Invoice No:", "Ref:", or a bare pattern like
  `INV-2026-0041`.
- `date`: looks for "Date:" or "Issued:", then converts whatever it
  finds (`15 March 2026`, `2026-01-22`, `15/03/2026`, etc.) into
  `YYYY-MM-DD`.
- `vendor`: looks for "Vendor:" or a company name sitting right before
  the words "Tax Invoice".
- `amount`: looks specifically for the line labelled **"Subtotal"**
  (never the grand total — rule 3 of the assignment).
- `tax`: looks for "GST", "IGST", "CGST", "SGST", "VAT" or "Tax" lines.
- `currency`: reads an explicit "Currency:" line, or guesses from
  symbols like `Rs.`, `₹`, `$`.

Every amount string first has its commas stripped (`1,40,000.00` →
`140000.00`) before being turned into a number, so Indian lakh-style
grouping doesn't break anything.

If nothing matches, the field is simply `None` → shows up as `null` in
the JSON response, exactly as rule 1 requires.

### main.py — the actual API

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # <- rule 4: lets a Cloudflare Worker call this API
    ...
)

@app.post("/extract", response_model=InvoiceResponse)
def extract(payload: InvoiceRequest):
    fields = extract_invoice_fields(payload.invoice_text)
    return fields
```

`CORSMiddleware` is the piece that stops browsers from blocking
cross-origin requests. Without it, the grader's Cloudflare Worker
would get a CORS error and every test would fail — even if your logic
is perfect. `allow_origins=["*"]` just means "anyone can call this,"
which is fine since this is a public grading endpoint with no secrets.

I already tested this locally against both sample invoices from your
JSON file and it returns the correct 6 keys for both — including the
exact subtotal/tax split (`2199.00` / `395.82`) the assignment
describes as the expected output.

## 3. Run it on your own machine (optional, to double check)

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Then test it:

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{"invoice_text": "Invoice No: INV-2026-0041\nDate: 15 March 2026\nVendor: TechParts Pvt Ltd\nSubtotal: Rs. 2,199.00\nGST (18%): Rs. 395.82"}'
```

You should get back:
```json
{"invoice_no":"INV-2026-0041","date":"2026-03-15","vendor":"TechParts Pvt Ltd","amount":2199.0,"tax":395.82,"currency":"INR"}
```

## 4. Deploying it publicly (Step 2 of the assignment)

The grader needs a public URL it can POST to. Pick whichever is easiest
for you — all are free:

### Option A: Render.com (easiest, no terminal needed)
1. Push this folder to a new GitHub repo.
2. Go to render.com → New → Web Service → connect your repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Click Deploy. Render gives you a URL like
   `https://your-app.onrender.com`.
6. Your endpoint is `https://your-app.onrender.com/extract`.

### Option B: Railway.app
Same idea as Render — connect GitHub repo, it auto-detects Python,
same start command as above. Very beginner-friendly UI.

### Option C: Cloudflare Tunnel (run it from your own laptop)
If you don't want to use a hosting site, you can expose your own
machine:
```bash
# Terminal 1: run your API
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: install cloudflared, then:
cloudflared tunnel --url http://localhost:8000
```
This prints a public URL like `https://random-words.trycloudflare.com`
that forwards straight to your laptop. Your endpoint becomes
`https://random-words.trycloudflare.com/extract`. Keep both terminals
open while grading happens — if you close them, the tunnel dies.

### Option D: ngrok (alternative to cloudflared)
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
ngrok http 8000
```
Same idea, different tool.

## 5. Submitting (Step 3)

Whatever public URL you got, submit the **base URL** (no trailing
`/extract`), e.g.:
```
https://your-app.onrender.com
```
The grader appends `/extract` itself and POSTs hidden invoice texts to
it — your regex rules need to generalize a bit beyond the 2 samples
you were given, which is why the patterns above try several label
variants (Ref/Invoice No, Vendor/Supplier/From, GST/IGST/CGST/SGST,
several date formats) instead of hard-coding to just the 2 samples.

## 6. If the hidden invoices don't match well

If you get partial credit and want to improve recall, the easiest
lever is adding more regex alternatives to `extractor.py`'s
`find_first([...])` lists for whichever field is failing — no need to
touch `main.py` at all.
