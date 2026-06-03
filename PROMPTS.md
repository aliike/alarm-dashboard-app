# PROMPTS.md — Claude Code Prompt'ları

Her milestone için hazır prompt. Kopyala → Claude Code terminaline yapıştır.
Her prompt öncesinde Claude Code'un proje kök dizininde olduğundan emin ol.

---

## Başlamadan Önce

```bash
# Repo'yu oluştur ve Claude Code'u başlat
mkdir alarm-dashboard && cd alarm-dashboard
git init
claude  # Claude Code'u başlat
```

---

## M1 Prompt — Proje İskeleti

```
CLAUDE.md ve PLAN.md dosyalarını oku. M1 milestone'unu implement et.

Yapılacaklar:
1. CLAUDE.md'deki klasör yapısını tam olarak oluştur
2. backend/Dockerfile: Python 3.12-slim, non-root user, uvicorn ile çalışsın
3. backend/requirements.txt: fastapi, uvicorn[standard], sqlalchemy, boto3, apscheduler, python-dotenv — tüm versiyonlar pinned olsun
4. backend/database.py: SQLite bağlantısı, CLAUDE.md'deki 3 tabloyu oluştur (customers, accounts, alarms)
5. backend/models.py: SQLAlchemy ORM modelleri, CLAUDE.md'deki şemaya birebir uy
6. backend/main.py: FastAPI app, lifespan ile DB init, GET /health endpoint
7. nginx/nginx.conf: /api/ → http://backend:8000 proxy, / → /usr/share/nginx/html static
8. docker-compose.yml: backend servisi (./backend), nginx servisi, ./data:/data volume, ./frontend:/usr/share/nginx/html volume
9. frontend/index.html: Sadece "Dashboard — Coming Soon" yazısı, siyah arka plan
10. .env.example: Boş ama açıklamalı örnek dosya

Bittikten sonra `docker compose up --build` çalıştır ve `curl http://localhost/health` ile test et. Hata varsa düzelt.
```

---

## M2 Prompt — Müşteri Yönetimi

```
CLAUDE.md ve PLAN.md dosyalarını oku. M1 tamamlandı. Şimdi M2'yi implement et.

Yapılacaklar:
1. backend/routers/customers.py:
   - GET /api/customers → tüm müşteriler + her birinin account sayısı ve toplam alarm sayısı
   - POST /api/customers → yeni müşteri ekle (name, account_type, root_account_id, role_arn, external_id)
   - GET /api/customers/{id} → müşteri detayı + accounts listesi
   - DELETE /api/customers/{id} → müşteriyi ve cascade ile accounts+alarms'ı sil
   - Her endpoint JSON döndürsün, hata durumunda {"error": "mesaj"} formatı

2. backend/main.py: customers router'ı include et, prefix="/api"

3. frontend/assets/style.css:
   - CLAUDE.md'deki tasarım kurallarına uy: #0a0a0a arka plan, beyaz metin
   - Font: JetBrains Mono (Google Fonts CDN)
   - Navbar, button, table, badge, form, card stilleri
   - State badge renkleri: ALARM=#ef4444, INSUFFICIENT_DATA=#f59e0b, OK=#22c55e
   - Tam bir design system oluştur, diğer sayfalar bunu kullanacak

4. frontend/assets/app.js:
   - apiGet(path), apiPost(path, body), apiDelete(path) — fetch wrapper'lar
   - showToast(message, type) — success/error toast
   - formatDateTime(utcString) — UTC'yi local time'a çevir, "X dk önce" formatı
   - Navbar active link logic

5. frontend/customers.html:
   - Müşteri kartları grid layout
   - Her kartta: müşteri adı, tip badge (PAYER/STANDALONE), hesap sayısı, alarm sayısı, son sync
   - "Yeni Müşteri Ekle" butonu → add_customer.html
   - Müşteri kartına tıklayınca → customer_detail.html?id=X
   - Silme butonu (confirm dialog ile)
   - Yüklenirken skeleton loader

6. frontend/add_customer.html:
   - Form: Müşteri adı, Hesap Tipi (radio: Payer/Standalone), Root Account ID, Role ARN, External ID (opsiyonel)
   - Role ARN format validasyonu: arn:aws:iam::[0-9]{12}:role/.+
   - Account ID format validasyonu: 12 hane
   - CLAUDE.md'deki IAM guide'ını adım adım göster (JSON blokları kopyalanabilir olsun)
   - Payer seçilince ek uyarı: "Alt hesaplarda da aynı role gereklidir"

7. Her iki HTML sayfasında da navbar olsun: "⚡ Alarm Dashboard" logo, Dashboard ve Customers linkleri

Bittikten sonra docker compose up --build yap. UI'dan bir test müşterisi ekle, sil. API çağrılarını kontrol et.
```

---

## M3 Prompt — AWS Entegrasyonu

```
CLAUDE.md ve PLAN.md dosyalarını oku. M2 tamamlandı. Şimdi M3'ü implement et.

Yapılacaklar:
1. backend/aws_client.py — Tüm AWS işlemleri bu dosyada:

   get_boto3_session(role_arn: str, external_id: str | None, session_name: str = "AlarmDashboard") -> boto3.Session
   - sts:AssumeRole yap, dönen credentials ile yeni session oluştur
   - external_id varsa Condition'a ekle
   - Hata: ClientError, NoCredentialsError → raise ValueError ile anlamlı mesaj

   get_active_regions(session: boto3.Session) -> list[str]
   - ec2.describe_regions(Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}])
   - Region name listesi döndür

   get_cloudwatch_alarms(session: boto3.Session, region: str) -> list[dict]
   - cloudwatch.describe_alarms() — tüm state'ler (StateValue filtresi yok)
   - Pagination handle et (NextToken)
   - Her alarm için: AlarmName, AlarmArn, AlarmDescription, StateValue, Namespace, MetricName, StateUpdatedTimestamp
   - Hata: return [] (region erişilemezse devam et)

   get_organization_accounts(session: boto3.Session) -> list[dict]
   - organizations.list_accounts() — pagination handle et
   - Her hesap için: Id, Name, Status
   - Sadece Status == "ACTIVE" olanları döndür
   - Hata: raise ValueError (bu kritik, sessizce geçme)

2. backend/routers/sync.py:
   - POST /api/sync/test-assume-role — body: {role_arn, external_id} → AssumeRole test et, region listesi döndür (geçici debug endpoint)

3. backend/main.py: sync router'ı include et

Bittikten sonra docker compose up --build yap.
Test: curl -X POST http://localhost/api/sync/test-assume-role -H "Content-Type: application/json" -d '{"role_arn":"arn:aws:iam::123456789012:role/AlarmDashboardRole"}'
(Gerçek ARN yoksa mock ARN ile hata mesajının anlamlı olduğunu kontrol et)
```

---

## M4 Prompt — Sync Engine

```
CLAUDE.md ve PLAN.md dosyalarını oku. M3 tamamlandı. Şimdi M4'ü implement et.

Yapılacaklar:
1. backend/scheduler.py:

   sync_account(db_account_id: int) -> None
   - accounts tablosundan hesabı çek
   - aws_client.get_boto3_session() ile session al
   - aws_client.get_active_regions() ile region listesi al
   - Her region için aws_client.get_cloudwatch_alarms() çalıştır
   - BAŞARILI: o hesabın alarmlarını DELETE et, yeni alarmları INSERT et, sync_status='ok', last_sync_at=UTC now
   - BAŞARISIZ: except bloğunda sync_status='error', sync_error=str(e) — eski alarmlar korunur
   - Her adımı logla (print veya logging, DEBUG seviyesinde)

   sync_customer(customer_id: int) -> None
   - customers + accounts tablosunu çek
   - Eğer account_type == 'payer':
     - root hesaba AssumeRole yap
     - get_organization_accounts() ile alt hesapları al
     - Her hesap için: accounts tablosunda yoksa INSERT et
     - Alt hesapların role_arn'ı: arn:aws:iam::{account_id}:role/AlarmDashboardRole (CLAUDE.md'deki standart isim)
   - Tüm accounts için sync_account() çalıştır (bağımsız try/except)

   sync_all_customers() -> None
   - Tüm customer'ları çek, her biri için sync_customer() çalıştır

   setup_scheduler(app: FastAPI) -> None
   - APScheduler BackgroundScheduler, interval 5 dakika
   - FastAPI lifespan'e entegre et (startup'ta başlat, shutdown'da durdur)
   - Uygulama başlarken 10 saniye sonra ilk sync'i tetikle (immediate=False, delay=10)

2. backend/main.py:
   - scheduler.setup_scheduler() lifespan'e ekle

3. backend/routers/sync.py:
   - POST /api/sync → sync_all_customers() tetikle (background task)
   - POST /api/sync/{customer_id} → sync_customer() tetikle (background task)
   - POST /api/sync/account/{account_id} → sync_account() tetikle (background task)
   - Her endpoint hemen {"status": "sync_started"} dönsün (bekletme)

4. backend/routers/customers.py güncelle:
   - POST /api/customers response'unda yeni eklenen müşteri için hemen sync tetikle (background)

Bittikten sonra docker compose up --build yap.
Test:
- docker compose logs -f backend ile logları izle
- 15 sn bekle, sync başladığını gör
- GET /api/customers/{id}/accounts → last_sync_at dolu olmalı
- Yanlış ARN'lı bir müşteri ekle → sync_status='error' olmalı
```

---

## M5 Prompt — Dashboard UI

```
CLAUDE.md ve PLAN.md dosyalarını oku. M4 tamamlandı. Şimdi M5'i implement et.

Yapılacaklar:
1. backend/routers/alarms.py:
   GET /api/alarms
   - Query params: customer_ids (comma-separated), state (comma-separated), region
   - JOIN: alarms → accounts → customers
   - Her alarm için: alarm alanları + account_id, account_name + customer_id, customer_name + last_sync_at
   - Sıralama: state önce (ALARM > INSUFFICIENT_DATA > OK), sonra updated_at desc

2. backend/main.py: alarms router'ı include et

3. frontend/index.html — Tam dashboard implementasyonu:

   HEADER BÖLÜMÜ:
   - Sol: "⚡ Alarm Dashboard" başlık
   - Sağ: "Son sync: X dk önce" text + "🔄 Sync" butonu
   - Sync butonuna basınca POST /api/sync, buton disabled+spinner olsun, 3 sn sonra tabloyu yenile

   MÜŞTERİ SEÇİM BÖLÜMÜ:
   - /api/customers'dan yükle
   - Her müşteri için tıklanabilir chip: "Müşteri Adı (alarm_sayısı)"
   - Default: tümü seçili
   - Seçim değişince tabloyu filtrele (API'den yeniden çek)
   - "Tümünü seç / Hiçbirini seçme" shortcut

   FİLTRE BAR:
   - State toggle butonları: ALARM | INSUFFICIENT_DATA | OK | Tümü
   - Default: ALARM + INSUFFICIENT_DATA seçili
   - Region dropdown (opsiyonel, "Tüm Regionlar" default)

   ALARM TABLOSU:
   Kolonlar: Müşteri | Hesap Adı | Account ID | Region | Alarm Adı | Namespace | State | Son Değişim
   - State kolonu: renkli badge (ALARM=kırmızı, INSUFFICIENT_DATA=sarı, OK=yeşil)
   - ALARM state badge'i pulse animasyonu ile
   - Son Değişim: "X dk önce" formatında, hover'da tam tarih tooltip
   - Boş durum: Seçili müşteri yoksa "Müşteri seçin", alarm yoksa "🟢 Seçili hesaplarda aktif alarm yok"
   - Satır sayısı göstergesi: "X alarm gösteriliyor"

   ÖZET KARTLAR (tablonun üstünde, küçük):
   - Toplam ALARM sayısı (kırmızı)
   - Toplam INSUFFICIENT_DATA sayısı (sarı)
   - Toplam OK sayısı (yeşil)
   - Toplam hesap sayısı

   AUTO-REFRESH:
   - Her 30 sn'de /api/alarms'ı yeniden çek (sayfa reload değil)
   - Refresh sırasında tablo donmasın, sadece subtle loading indicator

4. Her sayfanın navbar'ında aktif sayfa vurgusu olsun

Bittikten sonra docker compose up --build yap.
Test: Dashboard'ı aç, alarm sayılarını gör, müşteri chip'lerini toggle et, state filtrelerini değiştir.
```

---

## M6 Prompt — Müşteri Detay + Organizations

```
CLAUDE.md ve PLAN.md dosyalarını oku. M5 tamamlandı. Şimdi M6'yı implement et.

Yapılacaklar:
1. backend/routers/customers.py güncelle:
   GET /api/customers/{id}:
   - Müşteri bilgisi
   - accounts listesi (her biri: id, account_id, account_name, is_root, sync_status, sync_error, last_sync_at, alarm_counts={ALARM:n, INSUFFICIENT_DATA:n, OK:n})
   - Toplam alarm özeti

   GET /api/customers/{id}/alarms:
   - O müşteriye ait tüm alarmlar (accounts join ile)
   - Query params: state, region

2. frontend/customer_detail.html:

   HEADER:
   - Müşteri adı + tip badge (PAYER/STANDALONE)
   - Oluşturma tarihi
   - "← Müşteri Listesi" geri linki
   - "🔄 Sync" butonu (bu müşteriyi sync et)

   ÖZET KARTLAR:
   - Toplam hesap sayısı
   - ALARM sayısı, INSUFFICIENT_DATA sayısı, OK sayısı

   ALT HESAPLAR TABLOSU:
   Kolonlar: Hesap Adı | Account ID | Tip | Sync Durumu | Son Sync | İşlem
   - Tip: ROOT veya MEMBER badge
   - Sync Durumu: ✅ OK, ❌ ERROR (hover'da hata mesajı), ⏳ PENDING
   - İşlem: "Sync Et" butonu → POST /api/sync/account/{id}
   - ERROR durumunda satır subtle kırmızı arka plan

   ALARM TABLOSU:
   - index.html'deki ile aynı yapı (müşteri kolonu olmadan)
   - State filtresi burada da olsun

3. Payer hesap sync logic güncelle (scheduler.py):
   - Alt hesap discovery'de bulunan hesapların role_arn'ı: arn:aws:iam::{account_id}:role/AlarmDashboardRole
   - Eğer bu role zaten accounts tablosundaysa güncelleme, yoksa insert
   - Root hesabı da accounts tablosunda is_root=1 olarak tut

Bittikten sonra docker compose up --build yap.
Test: Payer hesap ekle, organizations'daki alt hesapların otomatik keşfedildiğini doğrula.
```

---

## M7 Prompt — Hesap Ekleme Guide

```
CLAUDE.md ve PLAN.md dosyalarını oku. M6 tamamlandı. Şimdi M7'yi implement et.

Yapılacaklar:
1. frontend/add_customer.html — Tam guide implementasyonu:

   FORM BÖLÜMÜ (sol veya üst):
   - Müşteri Adı (text input)
   - Hesap Tipi (radio: Payer Account / Standalone Account)
   - Root Account ID (text, 12 hane validasyon)
   - Role ARN (text, arn:aws:iam:: format validasyon)
   - External ID (text, opsiyonel)
   - "Müşteri Ekle" butonu

   GUIDE BÖLÜMÜ (sağ veya alt, form ile yan yana veya accordion):

   ADIM 1 — Hesap Tipini Belirle:
   "Bu hesap bir AWS Organization'ın yönetici (Management/Payer) hesabı mı,
   yoksa bağımsız bir AWS hesabı mı?"
   Payer seçilince ek bilgi: "Alt hesaplara da aynı IAM role'ü oluşturmanız gerekecek."

   ADIM 2 — EC2 Instance Profile Notu:
   Dikkat kutusu olarak göster:
   "Bu uygulamanın çalıştığı EC2'nun IAM role'ünün aşağıdaki yetkiye sahip olması gerekir:"
   Kopyalanabilir JSON:
   {
     "Effect": "Allow",
     "Action": "sts:AssumeRole",
     "Resource": "arn:aws:iam::*:role/AlarmDashboardRole"
   }

   ADIM 3 — IAM Role Oluştur:
   "Müşteri AWS hesabında (Account ID: [form'daki değer]) şu adımları takip edin:"
   - AWS Console → IAM → Roles → Create Role
   - Trusted entity: Another AWS account
   - Account ID: [EC2'nun bulunduğu hesap ID'si — burası placeholder, kullanıcı girmeli]
   Trust Policy JSON (kopyalanabilir):
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Principal": {"AWS": "arn:aws:iam::EC2_ACCOUNT_ID:root"},
       "Action": "sts:AssumeRole"
     }]
   }

   ADIM 4 — Permission Policy Ekle:
   "Role'e şu inline policy'i ekleyin:"
   Kopyalanabilir JSON (CLAUDE.md'deki policy):
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "cloudwatch:DescribeAlarms",
         "ec2:DescribeRegions",
         "organizations:ListAccounts",
         "organizations:DescribeAccount"
       ],
       "Resource": "*"
     }]
   }

   ADIM 5 — Role ARN'ı Kopyala:
   "Role oluşturulduktan sonra ARN'ı kopyalayın:"
   Örnek format: arn:aws:iam::123456789012:role/AlarmDashboardRole

   Payer seçilince ADIM 6 göster:
   ADIM 6 — Alt Hesaplar:
   "Tüm Organization üye hesaplarında da aynı role'ü oluşturun (ADIM 2-4'ü tekrar edin).
   Role adı AlarmDashboardRole olarak aynı tutun.
   Alt hesapların role'leri otomatik keşfedilecektir."

2. Guide JSON blokları için "📋 Kopyala" butonu → navigator.clipboard.writeText()
3. Form submit başarılıysa customers.html'e yönlendir, toast göster

Bittikten sonra docker compose up --build yap.
Test: add_customer.html aç, guide'ı incele, JSON'ları kopyala, formu doldur ve gönder.
```

---

## M8 Prompt — Production Hazırlığı

```
CLAUDE.md ve PLAN.md dosyalarını oku. M7 tamamlandı. Şimdi M8'i implement et.

Yapılacaklar:
1. docker-compose.yml güncelle:
   - Her iki servis için: restart: unless-stopped
   - Backend için: logging driver json-file, max-size: 10m, max-file: 3
   - Healthcheck: backend için curl /health, nginx için curl /
   - .env dosyasından env_file okusun

2. nginx/nginx.conf güncelle:
   - gzip on, gzip_types text/plain application/json text/css application/javascript
   - Security headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
   - Client max body size: 1m
   - Proxy timeout ayarları

3. backend/main.py güncelle:
   - Global exception handler middleware: unhandled exception'ları logla, {"error": "Internal server error"} döndür
   - GET /health genişlet: {"status": "ok", "scheduler": "running/stopped", "db": "ok/error", "last_sync": "ISO timestamp"}

4. backend/scheduler.py güncelle:
   - Scheduler crash etse bile uygulama ayakta kalsın (try/except setup etrafında)
   - Her sync job'ı için max_instances=1 (aynı anda iki sync çalışmasın)
   - Job exception'larını yakala ve logla

5. README.md oluştur:
   ## AWS Alarm Dashboard
   ### Gereksinimler
   - EC2 instance (t3.small veya üzeri, Amazon Linux 2023)
   - IAM Instance Profile (sts:AssumeRole yetkisi)
   - Docker + Docker Compose

   ### Kurulum
   \`\`\`bash
   # Docker kurulum (Amazon Linux 2023)
   sudo yum install -y docker
   sudo systemctl start docker
   sudo systemctl enable docker
   sudo usermod -aG docker $USER
   # Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   # Uygulamayı çalıştır
   git clone <repo-url>
   cd alarm-dashboard
   cp .env.example .env
   docker-compose up -d
   \`\`\`
   ### Erişim
   http://<EC2-Public-IP>

6. .gitignore oluştur:
   data/
   *.db
   .env
   __pycache__/
   *.pyc
   .DS_Store
   *.egg-info/

Bittikten sonra:
1. docker compose down && docker compose up --build -d
2. docker compose ps → tüm servisler "Up" olmalı
3. docker compose logs backend → hata olmamalı
4. curl http://localhost/health → scheduler ve db durumu kontrol et
5. Uygulama restart test: docker compose restart → veri kaybolmamalı
```

---

## Notlar

- Her prompt'u çalıştırmadan önce bir önceki milestone'un testlerini geçtiğinden emin ol.
- Claude Code bir şeyi yanlış yaparsa veya test geçmezse, hata mesajını Claude Code'a ver ve "düzelt" de.
- Milestone'lar arası ekstra değişiklik olursa CLAUDE.md'yi güncelle.
- Geliştirme bittikten sonra `git add -A && git commit -m "M8 complete"` ile commit at.
