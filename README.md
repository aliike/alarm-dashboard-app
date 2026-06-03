# AWS CloudWatch Alarm Dashboard

Birden fazla AWS hesabının CloudWatch alarmlarını tek ekranda gösteren,
EC2 üzerinde Docker ile çalışan web uygulaması.

---

## Gereksinimler

| Gereksinim | Detay |
|---|---|
| EC2 instance | t3.small veya üzeri, Amazon Linux 2023 |
| IAM Instance Profile | `sts:AssumeRole` yetkisi (aşağıya bakın) |
| Docker | 20.x veya üzeri |
| Docker Compose | v2.x veya üzeri |
| Port | 80 (inbound, security group'ta açık olmalı) |

### EC2 Instance Profile (Gerekli IAM Policy)

EC2'nun kendi IAM role'üne şu policy eklenmelidir:

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

---

## Kurulum

```bash
# 1. Docker kurulum (Amazon Linux 2023)
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
newgrp docker

# 2. Docker Compose kurulum
COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep tag_name | cut -d'"' -f4)
sudo curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
     -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 3. Repoyu klonla
git clone https://github.com/aliike/alarm-dashboard-app.git
cd alarm-dashboard-app

# 4. Environment dosyasını oluştur
cp .env.example .env
# .env dosyasını gerekirse düzenle (genellikle değişiklik gerekmez)

# 5. Uygulamayı başlat
docker-compose up -d

# 6. Logları kontrol et
docker-compose logs -f backend
```

---

## Erişim

```
http://<EC2-Public-IP>
```

**Sayfalar:**
- `/` — Ana dashboard (tüm alarmlar)
- `/customers.html` — Müşteri listesi
- `/add_customer.html` — Müşteri ekle (IAM kurulum rehberi dahil)
- `/customer_detail.html?id=X` — Müşteri detayı

**API:**
- `GET /health` — Uygulama durumu
- `GET /api/customers` — Müşteri listesi
- `GET /api/alarms` — Tüm alarmlar
- `POST /api/sync` — Manuel sync tetikle

---

## Müşteri Ekleme

1. `/add_customer.html` sayfasını açın
2. Sayfadaki **IAM Kurulum Rehberi**'ni takip edin
3. Müşteri AWS hesabında `AlarmDashboardRole` oluşturun
4. Formu doldurup **Müşteri Ekle**'ye tıklayın
5. Sync otomatik başlar (10 saniye içinde)

---

## Güncelleme

```bash
cd alarm-dashboard-app
git pull
docker-compose up --build -d
```

---

## Sorun Giderme

```bash
# Servis durumu
docker-compose ps

# Backend logları
docker-compose logs backend

# Nginx logları
docker-compose logs nginx

# Uygulama sağlık kontrolü
curl http://localhost/health

# Servisleri yeniden başlat
docker-compose restart
```

### Yaygın Sorunlar

| Sorun | Çözüm |
|---|---|
| `sync_status: error` | AWS hesabında `AlarmDashboardRole` var mı? Trust Policy doğru mu? |
| Dashboard boş | Müşteri eklenmemiş veya henüz sync olmamış — 5 dk bekleyin |
| Container başlamıyor | `docker-compose logs backend` ile hata mesajına bakın |
| Port 80 erişilemiyor | EC2 Security Group'ta port 80 inbound kuralı açık mı? |
