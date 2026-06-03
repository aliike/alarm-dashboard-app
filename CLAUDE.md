# AWS CloudWatch Alarm Dashboard — CLAUDE.md

Bu dosya Claude Code için proje context'idir. Her prompt öncesinde bu dosyayı oku.

---

## Projenin Amacı

Birden fazla AWS hesabının (Payer/Organization veya Standalone) CloudWatch alarmlarını
tek bir dashboard'da gösteren, EC2 üzerinde Docker ile çalışan bir web uygulaması.

---

## Teknik Kararlar (Değiştirme)

| Karar | Seçim | Neden |
|---|---|---|
| Backend | FastAPI (Python) | Async, hızlı, sade |
| Frontend | Vanilla HTML + JS + CSS | Sıfır build adımı, sade |
| Veritabanı | SQLite | Sıfır bağımlılık, dosya tabanlı |
| AWS Erişim | AssumeRole | Cross-account best practice |
| Containerization | Docker Compose | EC2'da kolay çalıştırma |
| Reverse Proxy | Nginx | Static dosya + API proxy |
| Background Jobs | APScheduler (in-process) | Sade, FastAPI ile entegre |

---

## Klasör Yapısı

```
alarm-dashboard/
├── CLAUDE.md
├── PLAN.md
├── PROMPTS.md
├── docker-compose.yml
├── nginx/
│   └── nginx.conf
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                  # FastAPI app entry point
│   ├── database.py              # SQLite init + connection
│   ├── models.py                # SQLAlchemy models
│   ├── scheduler.py             # APScheduler background jobs
│   ├── aws_client.py            # AssumeRole + boto3 helpers
│   └── routers/
│       ├── customers.py         # Müşteri CRUD endpointleri
│       ├── alarms.py            # Alarm sorgulama endpointleri
│       └── sync.py              # Manuel sync tetikleme
└── frontend/
    ├── index.html               # Dashboard (ana sayfa)
    ├── customers.html           # Müşteri listesi + ekleme
    ├── customer_detail.html     # Tekil müşteri alarm sayfası
    ├── add_customer.html        # Hesap ekleme formu + guide
    └── assets/
        ├── style.css            # Global stiller
        └── app.js               # Shared JS utilities
```

---

## Veritabanı Şeması

### `customers` tablosu
```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                        -- Görünen müşteri adı
    account_type TEXT NOT NULL,                -- 'payer' veya 'standalone'
    root_account_id TEXT NOT NULL,             -- Ana hesap ID (12 hane)
    role_arn TEXT NOT NULL,                    -- AssumeRole ARN (ana hesap)
    external_id TEXT,                          -- Opsiyonel External ID
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### `accounts` tablosu
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    account_id TEXT NOT NULL,                  -- AWS Account ID (12 hane)
    account_name TEXT,                         -- AWS'den gelen hesap adı
    role_arn TEXT NOT NULL,                    -- Bu hesap için AssumeRole ARN
    is_root INTEGER DEFAULT 0,                 -- 1 ise root/payer hesap
    last_sync_at DATETIME,                     -- Son başarılı sync zamanı
    sync_status TEXT DEFAULT 'pending',        -- 'ok', 'error', 'pending'
    sync_error TEXT,                           -- Hata mesajı (varsa)
    UNIQUE(customer_id, account_id)
);
```

### `alarms` tablosu
```sql
CREATE TABLE alarms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id_fk INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    alarm_name TEXT NOT NULL,
    alarm_arn TEXT,
    alarm_description TEXT,
    state TEXT NOT NULL,                       -- 'ALARM', 'OK', 'INSUFFICIENT_DATA'
    region TEXT NOT NULL,
    namespace TEXT,                            -- CloudWatch namespace (AWS/EC2 vs.)
    metric_name TEXT,
    updated_at DATETIME,                       -- AWS'deki StateUpdatedTimestamp
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id_fk, alarm_name, region)
);
```

---

## AWS Erişim Mimarisi

### EC2 Instance Profile (Gereken Permissions)
EC2'nun kendi IAM role'ü şu izinlere sahip olmalı:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::*:role/AlarmDashboardRole"
    }
  ]
}
```

### Müşteri Hesaplarında Oluşturulacak IAM Role
Role adı: `AlarmDashboardRole` (standart, tüm hesaplarda aynı)

Trust Policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::BURAYA_EC2_ACCOUNT_ID:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {}
    }
  ]
}
```

Permission Policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:DescribeAlarms",
        "ec2:DescribeRegions",
        "organizations:ListAccounts",
        "organizations:DescribeAccount"
      ],
      "Resource": "*"
    }
  ]
}
```

> **Not:** `organizations:ListAccounts` yalnızca Payer (Management) hesapta çalışır.
> Standalone hesaplara bu permission gerekli değil ama eklense de zarar vermez.

---

## Sync Mantığı

### Periyodik Sync (Her 5 Dakika)
```
scheduler her 5 dk'da bir çalışır
  → tüm customer'ları çek
  → her customer için:
      → root hesaba AssumeRole yap
      → eğer account_type == 'payer':
          → organizations:ListAccounts ile alt hesapları keşfet
          → yeni hesapları accounts tablosuna ekle (varsa güncelle)
      → her accounts kaydı için:
          → o hesaba AssumeRole yap
          → ec2:DescribeRegions ile aktif region listesi al
          → her region için cloudwatch:DescribeAlarms çalıştır (tüm state'ler)
          → BAŞARILI ise:
              → o hesabın eski alarmlarını sil (DELETE WHERE account_id_fk = ?)
              → yeni alarmları INSERT et
              → accounts.last_sync_at = NOW(), sync_status = 'ok'
          → BAŞARISIZ ise:
              → eski alarmları KORU (silme)
              → accounts.sync_status = 'error', sync_error = hata mesajı
              → accounts.last_sync_at değiştirme
```

### Önemli Kural
- Her hesap bağımsız sync edilir. Biri hata alsa diğerleri etkilenmez.
- Silinen alarm: başarılı sync'te otomatik kaybolur (DELETE + re-INSERT).
- Yeni alarm: başarılı sync'te otomatik görünür.
- OK state'e geçen alarm: veritabanında güncellenir, UI filtreleme ile gösterilmez (default).

---

## API Endpointleri

```
GET  /api/customers                    → Tüm müşterileri listele
POST /api/customers                    → Yeni müşteri ekle
GET  /api/customers/{id}               → Müşteri detayı (accounts dahil)
DELETE /api/customers/{id}             → Müşteri sil

GET  /api/customers/{id}/accounts      → Müşterinin hesaplarını listele
GET  /api/customers/{id}/alarms        → Müşterinin tüm alarmları
     ?state=ALARM,INSUFFICIENT_DATA    → State filtresi
     ?region=us-east-1                 → Region filtresi

GET  /api/alarms                       → Tüm alarmlar (dashboard için)
     ?customer_ids=1,2,3               → Müşteri filtresi
     ?state=ALARM,INSUFFICIENT_DATA    → State filtresi

POST /api/sync                         → Tüm hesapları manuel sync et
POST /api/sync/{customer_id}           → Tek müşteri manuel sync
POST /api/sync/account/{account_id}    → Tek hesap manuel sync
```

---

## Frontend Sayfaları

### `index.html` — Dashboard
- Üstte: müşteri seçim chip'leri (multi-select, tümü default seçili)
- Filtre bar: State filtresi (ALARM / INSUFFICIENT_DATA / OK / Tümü)
- Alarm tablosu: Müşteri Adı | Hesap Adı | Account ID | Region | Alarm Adı | Namespace | State | Son Değişim
- Her satırda state badge (kırmızı/sarı/yeşil)
- Sağ üstte: "Son sync: X dk önce" göstergesi
- Sağ üstte: Manuel sync butonu

### `customers.html` — Müşteri Listesi
- Müşteri kartları: Ad, tip (Payer/Standalone), hesap sayısı, alarm sayısı, son sync
- Yeni müşteri ekle butonu → `add_customer.html`
- Müşteriye tıklayınca → `customer_detail.html?id=X`

### `customer_detail.html` — Müşteri Detay
- Müşteri başlığı + metadata
- Alt hesaplar listesi (hesap ID, ad, son sync, sync status)
- O müşteriye ait alarm tablosu (index.html ile aynı yapı)

### `add_customer.html` — Hesap Ekleme
- Form: Müşteri adı, hesap tipi seçimi (Payer/Standalone), Account ID, Role ARN
- Guide bölümü: Adım adım IAM role nasıl oluşturulur, policy metni kopyalanabilir kod bloğu olarak

---

## UI Tasarım Kuralları

- **Renk paleti:** Siyah (`#0a0a0a`) arka plan, beyaz metin, gri nüanslar
- **Accent:** Sadece state badge'leri renkli (kırmızı/sarı/yeşil)
- **Font:** Monospace ağırlıklı (sistem mono veya JetBrains Mono CDN)
- **Layout:** Full-width tablo, sade header, minimal padding
- **Animasyon:** Sadece sync spinner ve badge pulse (ALARM state)
- **Responsive:** Masaüstü öncelikli, mobile zorunlu değil

---

## Geliştirme Kuralları

1. Her milestone sonunda `docker compose up --build` çalışmalı, hata olmamalı.
2. API endpoint'leri her zaman JSON döndürmeli, hata durumunda `{"error": "mesaj"}`.
3. Frontend API'yi `fetch()` ile çağırır, base URL `/api/` şeklinde (Nginx proxy).
4. SQLite dosyası: `/data/alarm_dashboard.db` (Docker volume olarak mount edilir).
5. Tüm zaman damgaları UTC olarak saklanır, frontend'de local time'a çevrilir.
6. `.env` dosyası ile konfigürasyon yapılır, örnek `.env.example` repo'da bulunur.
7. Loglar stdout'a yazılır (Docker log standardı).
8. `requirements.txt` her zaman pinned version içerir.
