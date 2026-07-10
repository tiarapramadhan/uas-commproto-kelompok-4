# UAS Communication Protocol — API Ingestion Dataset (Kelompok 4)

Mini project mata kuliah **Communication Protocol** — Sains Data Reguler 3.

Membangun REST API untuk ingestion data nilai mahasiswa, dilengkapi observability (logging & correlation ID), error handling yang konsisten, serta integrasi otomasi ke **n8n** untuk mengirim notifikasi hasil (Lulus/Perlu Perbaikan) ke **Discord**.

---

## 📌 Ringkasan Use Case

> Proses input nilai mahasiswa sering dilakukan secara manual, sehingga rawan kesalahan data dan sulit dilacak jika terjadi masalah. Project ini membangun REST API yang menerima, memvalidasi, menyimpan, dan mengembalikan response data nilai mahasiswa — lengkap dengan correlation ID dan logging supaya seluruh proses dapat ditelusuri end-to-end.

## 🏗️ Arsitektur

```
Postman (Client)
      │  HTTP POST /api/scores (JSON)
      ▼
FastAPI Server
  ├─ Validasi data (Pydantic)
  ├─ Simpan data
  ├─ Generate Correlation ID
  ├─ Logging (server.log)
      │  (opsional, jika data valid & tersimpan)
      ▼
n8n Webhook
  ├─ Set: format data & tentukan predikat
  ├─ IF: nilai ≥ 80 ?
      │
      ├─ True  → Discord #prestasi
      └─ False → Discord #bimbingan
```

Diagram lengkap: [`docs/architecture.png`](docs/architecture.png) · [`docs/data-flow.png`](docs/data-flow.png)

## 🔌 Protocol Selection

| Protocol | Alasan |
|---|---|
| HTTP REST | Komunikasi client-server |
| JSON | Format pertukaran data |
| Webhook HTTP | Komunikasi satu arah FastAPI → n8n |
| TCP | Transport layer |

## 🚀 Cara Menjalankan

### 1. Install dependency
```bash
pip install -r requirements.txt
```

### 2. (Opsional) Jalankan n8n untuk notifikasi Discord
```bash
docker run -d --name n8n --restart unless-stopped -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n
```
Buka `http://localhost:5678`, import `n8n/workflow.json`, pasang Discord Webhook URL di kedua node Discord, lalu **Save** dan **Activate**.

### 3. Set environment variable (jika n8n dipakai)
```bash
export N8N_WEBHOOK_URL="http://localhost:5678/webhook/notify-score"
```

### 4. Jalankan server
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Buka dokumentasi API
```
http://127.0.0.1:8000/docs
```

## 📮 Endpoint

| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/api/scores` | Ingest data nilai mahasiswa |
| GET | `/api/scores` | Lihat semua data |
| GET | `/api/scores/{nim}` | Lihat detail data by NIM |
| DELETE | `/api/scores/{nim}` | Hapus data by NIM |
| GET | `/health` | Cek status server |

Contoh request body:
```json
{
  "nim": "2201234567",
  "nama": "Budi Santoso",
  "mata_kuliah": "Communication Protocol",
  "nilai": 85,
  "semester": 2
}
```

## 🔍 Observability

Setiap request diberi **Correlation ID** unik (header `X-Correlation-ID`), dicatat di `server.log`, dan bisa ditelusuri lintas layer — mulai dari capture jaringan (Wireshark), log aplikasi, hingga eksekusi workflow n8n. Bukti korelasi ID yang identik di ketiga layer ada di [`evidence/wireshark/`](evidence/wireshark/).

## ⚠️ Error Handling

Semua error dikembalikan dalam format seragam lewat custom exception handler:
```json
{
  "error_code": "ERR_409",
  "message": "Data dengan nim 2201234567 sudah ada",
  "correlation_id": "..."
}
```

Skenario yang teruji: `422` (nilai di luar range), `409` (NIM duplikat), `422` (NIM kosong). Bukti: [`evidence/postman/`](evidence/postman/).

## 📁 Struktur Folder

```
├── app/main.py              # Kode utama FastAPI
├── docs/                    # Diagram arsitektur & laporan
├── n8n/                     # Workflow otomasi n8n
├── postman/                 # Koleksi testing Postman
├── evidence/                # Bukti pengujian (screenshot, log)
├── presentation/            # Slide deck presentasi
└── reflection/              # Refleksi & pembagian kontribusi tim
```

## ⚠️ Limitation

- Data disimpan **in-memory** (list Python) — hilang saat server di-restart, bukan database permanen
- Belum ada sistem autentikasi/login
- Kerentanan sistem yang masih menggunakan HTTP
- Notifikasi Discord belum memiliki mekanisme retry otomatis jika gagal terkirim

## 🔧 Improvement ke Depan

- Migrasi penyimpanan ke database permanen (PostgreSQL/SQLite)
- Menambahkan retry otomatis untuk notifikasi yang gagal
- Menambahkan sistem autentikasi (API key/JWT)
- Menerapan Protokol HTTPS untuk memastikan koneksi aman

## 👥 Kontribusi Tim

Lihat [`reflection/kontribusi-anggota.md`](reflection/kontribusi-anggota.md) untuk detail pembagian peran.

| Role | Tanggung Jawab |
|------|-----------------|
| API & Integration Engineer | Membangun FastAPI, integrasi n8n |
| Protocol Analyst & Postman Tester | Testing endpoint, dokumentasi skenario error |
| Documentation & Presentation Lead | Laporan, slide, evidence |

---

**UAS Mini Project — Communication Protocol, Sains Data Reguler, Kelompok 4**
