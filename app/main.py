"""
API Ingestion Dataset - Mini Project Communication Protocol
Use Case: Ingestion data nilai mahasiswa (student scores)

Menjalankan:
    uvicorn app.main:app --reload --port 8000

Dokumentasi otomatis:
    http://127.0.0.1:8000/docs
"""

import logging
import os
import uuid
import time
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# 1. LOGGING SETUP (Observability Evidence)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("api-ingestion")

# ---------------------------------------------------------------------------
# 1.5 n8n INTEGRATION (Opsi B - notifikasi Discord, opsional & non-blocking)
# ---------------------------------------------------------------------------
# Diisi lewat environment variable, BUKAN hardcode di kode (menghindari
# credential/URL live ikut ter-commit ke repo publik - lihat larangan di
# soal UAS bagian "Ketentuan Akademik dan Keamanan").
#
# Cara pakai:
#   export N8N_WEBHOOK_URL="https://xxxx.app.n8n.cloud/webhook/notify-score"
#   uvicorn app.main:app --reload --port 8000
#
# Kalau env var ini kosong, notifikasi otomatis di-skip (server tetap jalan
# normal) - ini contoh nyata prinsip graceful degradation.
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")


async def notify_n8n(correlation_id: str, payload: dict) -> None:
    """Kirim notifikasi best-effort ke n8n. Kegagalan di sini TIDAK BOLEH
    menggagalkan response utama API (lihat main flow di ingest_score)."""
    if not N8N_WEBHOOK_URL:
        logger.info(f"[{correlation_id}] n8n notif dilewati (N8N_WEBHOOK_URL belum di-set)")
        return
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=payload)
        logger.info(f"[{correlation_id}] n8n notif terkirim, status={resp.status_code}")
    except Exception as e:
        logger.warning(f"[{correlation_id}] Gagal kirim notifikasi ke n8n: {e}")

app = FastAPI(
    title="Student Scores Ingestion API",
    description="Mini project: API Ingestion Dataset - Communication Protocol UAS",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# 2. MIDDLEWARE: CORRELATION ID + REQUEST LOGGING (Observability Evidence)
# ---------------------------------------------------------------------------
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    start_time = time.time()

    logger.info(
        f"[{correlation_id}] --> {request.method} {request.url.path} | "
        f"client={request.client.host if request.client else 'unknown'}"
    )

    response = await call_next(request)

    duration_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Correlation-ID"] = correlation_id

    logger.info(
        f"[{correlation_id}] <-- status={response.status_code} "
        f"duration={duration_ms}ms"
    )
    return response


# ---------------------------------------------------------------------------
# 3. DATA MODEL & VALIDATION (Pydantic)
# ---------------------------------------------------------------------------
class ScoreIn(BaseModel):
    nim: str = Field(..., min_length=8, max_length=15, description="Nomor Induk Mahasiswa")
    nama: str = Field(..., min_length=1, description="Nama mahasiswa")
    mata_kuliah: str = Field(..., min_length=1)
    nilai: float = Field(..., ge=0, le=100, description="Nilai 0-100")
    semester: int = Field(..., ge=1, le=14)

    @field_validator("nim")
    @classmethod
    def nim_must_be_numeric(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("nim harus berupa digit angka")
        return v


class ScoreOut(ScoreIn):
    id: str


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    correlation_id: Optional[str] = None


# ---------------------------------------------------------------------------
# 4. IN-MEMORY "DATABASE" (list) - cukup untuk mini project
# ---------------------------------------------------------------------------
DB: List[ScoreOut] = []


# ---------------------------------------------------------------------------
# 5. ENDPOINTS (minimal 4 sesuai requirement)
# ---------------------------------------------------------------------------

@app.post(
    "/api/scores",
    response_model=ScoreOut,
    status_code=status.HTTP_201_CREATED,
    responses={422: {"model": ErrorResponse}},
)
async def ingest_score(payload: ScoreIn, request: Request):
    """Endpoint utama ingestion: menerima 1 record nilai mahasiswa."""
    # cek duplikat nim (contoh validasi bisnis tambahan)
    if any(s.nim == payload.nim for s in DB):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Data dengan nim {payload.nim} sudah ada",
        )

    record = ScoreOut(id=str(uuid.uuid4()), **payload.model_dump())
    DB.append(record)

    correlation_id = getattr(request.state, "correlation_id", "n/a")
    logger.info(f"[{correlation_id}] Data ingested: nim={record.nim} nilai={record.nilai}")

    # Notifikasi ke n8n -> Discord (best-effort, tidak boleh gagalkan response utama)
    await notify_n8n(correlation_id, record.model_dump())

    return record


@app.get("/api/scores", response_model=List[ScoreOut])
async def get_all_scores():
    """Melihat semua data yang sudah masuk."""
    return DB


@app.get(
    "/api/scores/{nim}",
    response_model=ScoreOut,
    responses={404: {"model": ErrorResponse}},
)
async def get_score_by_nim(nim: str):
    """Melihat detail data satu mahasiswa berdasarkan NIM."""
    for record in DB:
        if record.nim == nim:
            return record
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Data dengan nim {nim} tidak ditemukan",
    )


@app.delete("/api/scores/{nim}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_score(nim: str):
    """Menghapus data mahasiswa berdasarkan NIM."""
    global DB
    before = len(DB)
    DB = [s for s in DB if s.nim != nim]
    if len(DB) == before:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data dengan nim {nim} tidak ditemukan, tidak ada yang dihapus",
        )
    return None


# ---------------------------------------------------------------------------
# 6. CUSTOM ERROR HANDLER (supaya error contract konsisten -> requirement UAS)
# ---------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    correlation_id = getattr(request.state, "correlation_id", "n/a")
    logger.error(f"[{correlation_id}] HTTPException: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": f"ERR_{exc.status_code}",
            "message": exc.detail,
            "correlation_id": correlation_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    correlation_id = getattr(request.state, "correlation_id", "n/a")
    errors = exc.errors()
    logger.error(f"[{correlation_id}] ValidationError: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error_code": "ERR_422",
            "message": "Data tidak valid, cek kembali field yang dikirim",
            "details": errors,
            "correlation_id": correlation_id,
        },
    )


@app.get("/health")
async def health_check():
    """Endpoint tambahan untuk cek server hidup (opsional, memudahkan demo)."""
    return {"status": "ok", "total_records": len(DB)}