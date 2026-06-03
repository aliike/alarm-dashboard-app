# PLAN.md — Geliştirme Yol Haritası

Her milestone bağımsız ve test edilebilir bir birimdir.
Bir milestone tamamlanmadan bir sonrakine geçme.

---

## M1 — Proje İskeleti
**Hedef:** `docker compose up` ayağa kalksın, boş sayfa gelsin.

Yapılacaklar:
- [ ] Klasör yapısını oluştur (`backend/`, `frontend/`, `nginx/`)
- [ ] `backend/Dockerfile` — Python 3.12 slim image
- [ ] `backend/requirements.txt` — fastapi, uvicorn, sqlalchemy, boto3, apscheduler, python-dotenv
- [ ] `backend/main.py` — Minimal FastAPI app, `/health` endpoint
- [ ] `backend/database.py` — SQLite bağlantısı, tablo oluşturma
- [ ] `backend/models.py` — SQLAlchemy ORM modelleri (customers, accounts, alarms)
- [ ] `nginx/nginx.conf` — `/api/` → backend:8000, `/` → frontend static
- [ ] `docker-compose.yml` — backend + nginx servisleri, data volume
- [ ] `frontend/index.html` — "Dashboard coming soon" placeholder
- [ ] `.env.example` — Örnek environment dosyası

**Test:** `curl http://localhost/health` → `{"status": "ok"}` dönmeli

---

## M2 — Müşteri Yönetimi (CRUD)
**Hedef:** UI'dan müşteri ekleyip silebilmek.

Yapılacaklar:
- [ ] `backend/routers/customers.py` — CRUD endpointleri
- [ ] `backend/main.py` — Router'ı include et
- [ ] `frontend/customers.html` — Müşteri listesi sayfası
- [ ] `frontend/add_customer.html` — Ekleme formu + IAM guide
- [ ] `frontend/assets/style.css` — Global siyah/beyaz tema
- [ ] `frontend/assets/app.js` — Shared fetch utility, toast notifications
- [ ] Navbar — Dashboard / Customers linkleri

**Test:**
- UI'dan "Test Müşteri" adında standalone hesap ekle
- `GET /api/customers` → müşteri listede görünsün
- Müşteriyi sil → listeden kaybolsun

---

## M3 — AWS Entegrasyonu
**Hedef:** AssumeRole çalışsın, region ve alarm listesi çekilebilsin.

Yapılacaklar:
- [ ] `backend/aws_client.py`:
  - `get_session(role_arn, external_id)` → boto3 session
  - `get_active_regions(session)` → aktif region listesi
  - `get_alarms(session, region)` → CloudWatch alarmları (tüm state'ler)
  - `get_organization_accounts(session)` → Organizations alt hesaplar
- [ ] Hata yönetimi: `ClientError`, `NoCredentialsError`, timeout
- [ ] `backend/routers/sync.py` — Manuel sync endpoint (tek hesap)
- [ ] Test için: `GET /api/test-assume-role?role_arn=...` geçici debug endpoint

**Test:**
- Gerçek bir role ARN ile AssumeRole yap
- Region listesi dön (en az 10 region beklenir)
- Alarm listesi dön (boş liste de kabul edilir)

---

## M4 — Sync Engine
**Hedef:** Otomatik 5 dk'lık sync çalışsın, veritabanı güncellensin.

Yapılacaklar:
- [ ] `backend/scheduler.py`:
  - APScheduler kurulumu (BackgroundScheduler)
  - `sync_all_customers()` — tüm müşterileri sırayla sync et
  - `sync_customer(customer_id)` — tek müşteri sync
  - `sync_account(account_id)` — tek hesap sync
  - Her hesap bağımsız try/except içinde
- [ ] Payer hesap için Organizations account discovery
- [ ] Accounts tablosuna yeni hesapları ekle, var olanları güncelle
- [ ] Alarm sync mantığı:
  - Başarılı: DELETE eski alarmlar → INSERT yeni alarmlar → UPDATE last_sync_at
  - Başarısız: Eski alarmları koru → UPDATE sync_status='error', sync_error=mesaj
- [ ] `POST /api/sync` — Tüm hesapları manuel tetikle
- [ ] `POST /api/sync/{customer_id}` — Müşteri sync
- [ ] Uygulama başlarken bir kez sync tetikle (startup event)

**Test:**
- Uygulama başlat, 30 sn bekle
- `GET /api/customers/{id}/accounts` → last_sync_at dolu olmalı
- `GET /api/alarms` → alarm kayıtları olmalı
- Kasıtlı yanlış ARN gir → sync_status='error' olmalı, eski alarmlar korunmalı

---

## M5 — Dashboard UI
**Hedef:** Ana dashboard ekranı çalışır hale gelsin.

Yapılacaklar:
- [ ] `frontend/index.html` — Tam dashboard implementasyonu:
  - Müşteri seçim chip'leri (multi-select, default: tümü seçili)
  - State filtresi (ALARM / INSUFFICIENT_DATA / OK / Tümü) — default: ALARM + INSUFFICIENT_DATA
  - Alarm tablosu kolonları: Müşteri | Hesap | Account ID | Region | Alarm Adı | Namespace | State | Son Değişim
  - State badge'leri: kırmızı (ALARM), sarı (INSUFFICIENT_DATA), yeşil (OK)
  - "Son sync: X dk önce" göstergesi (en eski last_sync_at'e göre)
  - Manuel sync butonu + loading spinner
  - Boş durum mesajı ("Tüm alarmlar OK 🟢" veya "Henüz müşteri eklenmedi")
- [ ] `GET /api/alarms?customer_ids=1,2&state=ALARM,INSUFFICIENT_DATA` endpoint'i
- [ ] Auto-refresh: Her 30 sn'de UI otomatik yenilesin (sayfa reload değil, fetch)

**Test:**
- Dashboard'da ALARM state'indeki alarmlar görünsün
- Bir müşteri chip'ini kaldır → o müşterinin alarmları kaybolsun
- OK filtrele → OK alarmlar da görünsün

---

## M6 — Müşteri Detay + Organizations Keşfi
**Hedef:** Müşteri bazlı görünüm ve payer hesap alt hesap keşfi çalışsın.

Yapılacaklar:
- [ ] `frontend/customer_detail.html`:
  - Müşteri başlığı ve metadata (hesap tipi, ekleme tarihi, toplam alarm)
  - Alt hesaplar tablosu: Hesap ID | Hesap Adı | Sync Durumu | Son Sync | Hata Mesajı
  - O müşteriye ait alarm tablosu (index.html ile aynı component)
  - Tek hesap sync butonu (hesap satırında)
- [ ] Payer hesap eklendiğinde Organizations discovery otomatik çalışsın
- [ ] Standalone hesap için organizations sorgusu atlanır
- [ ] `GET /api/customers/{id}` response'una accounts ve alarm summary ekle

**Test:**
- Payer hesap ekle → organizations'daki alt hesaplar otomatik keşfedilsin
- customer_detail.html'de alt hesaplar listede görünsün
- Standalone hesap için sadece o hesap görünsün

---

## M7 — Hesap Ekleme Guide
**Hedef:** Kullanıcı UI üzerinden ne yapması gerektiğini anlayabilsin.

Yapılacaklar:
- [ ] `add_customer.html` — Guide bölümü:
  - **Adım 1:** Hangi AWS hesabında olduğunu belirle (Payer mı, Standalone mı?)
  - **Adım 2:** IAM Role oluşturma talimatları (Console + CLI seçenekleri)
  - **Adım 3:** Trust Policy — kopyalanabilir JSON bloğu (EC2 Account ID placeholder ile)
  - **Adım 4:** Permission Policy — kopyalanabilir JSON bloğu
  - **Adım 5:** Role ARN'ı kopyala, forma gir
  - Payer hesap seçilince ek not: "Alt hesaplarda da aynı role oluşturulmalıdır"
  - EC2 Instance Profile için ayrı not kutusu
- [ ] Form validasyonu: Role ARN format kontrolü (`arn:aws:iam::...`)
- [ ] Account ID format kontrolü (12 hane rakam)

**Test:**
- Guide'daki JSON'ları kopyala, AWS Console'da uygula
- Role ARN'ı forma gir → ekleme başarılı olsun

---

## M8 — Production Hazırlığı
**Hedef:** EC2'da production'a hazır, stabil çalışsın.

Yapılacaklar:
- [ ] `docker-compose.yml` — Production ayarları:
  - `restart: unless-stopped` her iki servis için
  - Data volume kalıcı (`./data:/data`)
  - Log rotation ayarları
- [ ] `nginx/nginx.conf` — Gzip compression, security headers
- [ ] Backend: Exception handler middleware (unhandled error'ları logla)
- [ ] Scheduler: Başlangıçta crash etse de uygulama ayakta kalsın
- [ ] `README.md` — EC2'ya kurulum talimatları (Docker install, git clone, .env ayarları, compose up)
- [ ] `.gitignore` — `*.db`, `.env`, `__pycache__`, `.DS_Store`
- [ ] Health endpoint'i genişlet: scheduler durumu, DB bağlantısı, son sync zamanı

**Test:**
- EC2'da fresh kurulum yap, README'yi takip et
- `docker compose up -d` → servisler ayakta
- Uygulama restart'tan sonra veri kaybolmamalı (volume test)
- Yanlış AWS credentials → uygulama crash etmemeli

---

## Milestone Sırası ve Bağımlılıklar

```
M1 (iskelet) → M2 (müşteri CRUD) → M3 (AWS) → M4 (sync engine)
                                                      ↓
M8 (production) ← M7 (guide) ← M6 (detay) ← M5 (dashboard UI)
```

Her milestone'da `docker compose up --build` çalıştır ve test adımlarını geç.
