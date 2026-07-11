from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from extractor import extract_invoice_fields

app = FastAPI(title="IITM Invoice Extraction API")

# Rule 4: CORS must be enabled so a Cloudflare Worker can call this endpoint.
# allow_origins=["*"] means "any website may call this API" — fine for a
# public grading endpoint like this one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class InvoiceRequest(BaseModel):
    invoice_text: str


class InvoiceResponse(BaseModel):
    invoice_no: str | None
    date: str | None
    vendor: str | None
    amount: float | None
    tax: float | None
    currency: str | None


@app.get("/")
def health_check():
    return {"status": "ok", "message": "POST invoice_text to /extract"}


@app.post("/extract", response_model=InvoiceResponse)
def extract(payload: InvoiceRequest):
    fields = extract_invoice_fields(payload.invoice_text)
    return fields
