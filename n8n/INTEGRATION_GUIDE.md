# Integrasi n8n ke API (Opsi B — Notifikasi Discord)

## Cara Pakai Workflow

1. Import `n8n/workflow.json` ke n8n cloud kamu (Workflows -> Import from File)
2. Buka node **"Send Discord Notification"**, ganti URL placeholder dengan Discord
   Webhook URL asli kamu (dari Discord -> Channel Settings -> Integrations -> Webhooks)
3. Klik **Activate** (toggle di kanan atas workflow)
4. Buka node **"Webhook - Receive from FastAPI"**, salin **Production URL**-nya
   (bentuknya seperti `https://xxxx.app.n8n.cloud/webhook/notify-score`)

## Cara Menghubungkan ke main.py

Tambahkan kode berikut ke `app/main.py`. Ini akan memanggil n8n **setiap kali**
data berhasil di-ingest (tidak mengganggu response utama walau n8n gagal/lambat).

### 1. Install dependency tambahan
```bash
pip install httpx --break-system-packages
```

### 2. Tambahkan import di bagian atas main.py
```python
import httpx

N8N_WEBHOOK_URL = "https://xxxx.app.n8n.cloud/webhook/notify-score"  # ganti dengan URL kamu
```

### 3. Tambahkan pemanggilan n8n di dalam fungsi ingest_score,
   setelah baris `DB.append(record)` dan sebelum `return record`:

```python
    # Panggil n8n webhook untuk notifikasi (best-effort, tidak boleh gagalkan response utama)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(N8N_WEBHOOK_URL, json=record.model_dump())
    except Exception as e:
        logger.warning(f"[{correlation_id}] Gagal kirim notifikasi ke n8n: {e}")
```

## Kenapa dibungkus try-except?

Ini prinsip penting dalam desain sistem: **notifikasi adalah fitur tambahan (nice-to-have),
bukan inti sistem**. Kalau n8n sedang down atau lambat, API ingestion utama harus tetap
jalan dan tetap mengembalikan response sukses ke client. Ini juga bisa jadi poin bagus
di laporan bagian "reliability" — menunjukkan kamu paham prinsip *graceful degradation*.

## Evidence yang perlu di-screenshot untuk bagian ini

1. Konfigurasi node Discord webhook di n8n (URL disamarkan/blur sebagian saat screenshot)
2. Execution history di n8n yang menunjukkan workflow berhasil trigger
3. Screenshot notifikasi yang muncul di Discord
4. Log di terminal FastAPI yang menunjukkan pemanggilan ke n8n (jika ditambahkan logging)

## Diagram update

Tambahkan 2 komponen baru ke architecture canvas kamu:
```
FastAPI (setelah data sukses tersimpan)
        |
        v (HTTP POST)
   n8n Webhook
        |
        v (HTTP POST)
  Discord Webhook -> Channel notifikasi
```
