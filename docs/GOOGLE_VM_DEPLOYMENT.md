# Triển khai AI-Construction trên Google Compute Engine

Quy trình này dùng một VM Ubuntu 24.04 LTS, Caddy phục vụ frontend đã build và chuyển tiếp API đến FastAPI. SQLite và hồ sơ nằm trên ổ đĩa bền vững của VM. Chuẩn bị một Google Cloud project, zone, VM và tên miền để cấp HTTPS.

## 1. Tạo gói ứng dụng trên máy làm việc

Tại thư mục repository trên Windows, checkout commit cần triển khai rồi build và đóng gói từ cùng commit.

```powershell
npm.cmd --prefix frontend ci
if ($LASTEXITCODE -ne 0) { throw "Cài dependency frontend thất bại" }
npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw "Build frontend thất bại" }
New-Item -ItemType Directory -Force data/storage/release | Out-Null
$sourceTar = 'data/storage/release/ai-construction-source.tar'
# Dùng bản trong Git và giữ LF cho các script chạy trên Linux.
git -c core.autocrlf=false archive --format=tar --output=$sourceTar HEAD -- backend/app backend/alembic backend/alembic.ini backend/requirements.txt deploy/gce scripts/bootstrap_admin.sh scripts/backup.py scripts/restore.py
if ($LASTEXITCODE -ne 0) { throw "Xuất mã từ Git thất bại" }
tar.exe -czf data/storage/release/ai-construction-release.tar.gz "@$sourceTar" frontend/dist
if ($LASTEXITCODE -ne 0) { throw "Tạo gói release thất bại" }
Get-FileHash -Algorithm SHA256 data/storage/release/ai-construction-release.tar.gz
```

Gói này chứa mã và frontend đã build. Database, workbook mẫu, hồ sơ và cấu hình chứa khóa API được chuyển riêng qua kênh riêng đã được phê duyệt. Khi dùng bản DAP, chọn đúng bản sao database và các thư mục hồ sơ đi kèm. Database demo hiện dùng tài khoản thử và có công trình tổng hợp. Rà lại tài khoản, phiên đăng nhập và phạm vi dữ liệu trước khi mở truy cập. Backup mặc định của ứng dụng chạy theo cấu trúc `app.db`, `storage/`, `templates/`. Nếu nguồn ở `data/storage/demo-live`, chuẩn bị một thư mục trung gian theo cấu trúc này trước khi dùng [script backup](../scripts/backup.py).

## 2. Chuẩn bị VM và chuyển gói

Tạo VM Ubuntu, đặt tên DNS trỏ về IP tĩnh, giới hạn SSH theo chính sách của project. Caddy cần cổng 80 và 443 khi dùng tên miền công khai. Giữ hai cổng web chưa mở tới người dùng cho đến bước kiểm tra tài khoản. Cổng 8765 phục vụ trên loopback của VM. [Tạo VM Linux](https://docs.cloud.google.com/compute/docs/create-linux-vm-instance) · [Cấu hình IP tĩnh](https://docs.cloud.google.com/compute/docs/ip-addresses/configure-static-external-ip-address) · [Điều kiện HTTPS của Caddy](https://caddyserver.com/docs/automatic-https#hostname-requirements)

Tải gói lên VM bằng SSH từ thư mục repository. Chạy `gcloud auth login` nếu chưa đăng nhập, rồi thay ba giá trị project, zone và tên VM. [Đăng nhập Google Cloud CLI](https://docs.cloud.google.com/sdk/docs/authenticate) · [Google Cloud CLI](https://docs.cloud.google.com/sdk/gcloud/reference/compute/scp)

```powershell
$gceProject = 'PROJECT_ID'
$gceZone = 'ZONE'
$gceVm = 'VM_NAME'
gcloud compute scp --project $gceProject --zone $gceZone ./data/storage/release/ai-construction-release.tar.gz "${gceVm}:~/"
gcloud compute ssh $gceVm --project $gceProject --zone $gceZone
```

Trên VM, đối chiếu mã SHA-256 trước khi giải nén.

```bash
sha256sum "$HOME/ai-construction-release.tar.gz"
sudo apt-get update
sudo apt-get install -y python3-venv sqlite3 curl
# Cài các gói này khi sử dụng xuất PDF hoặc OCR.
sudo apt-get install -y libreoffice-calc fonts-dejavu-core tesseract-ocr tesseract-ocr-vie
```

Cài Caddy bằng gói systemd theo hướng dẫn chính thức. [Cài Caddy trên Ubuntu](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)

```bash
getent passwd ai-construction >/dev/null || sudo useradd --system --user-group --home-dir /var/lib/ai-construction --shell /usr/sbin/nologin ai-construction
release="/opt/ai-construction/releases/$(date -u +%Y%m%dT%H%M%SZ)"
sudo install -d -m 0755 "$release"
sudo tar --extract --gzip --file "$HOME/ai-construction-release.tar.gz" --directory "$release" --no-same-owner
sudo python3 -m venv "$release/.venv"
sudo "$release/.venv/bin/python" -m pip install -r "$release/backend/requirements.txt"
sudo install -d -m 0750 -o root -g ai-construction /etc/ai-construction
sudo install -m 0640 -o root -g ai-construction "$release/deploy/gce/app.env.example" /etc/ai-construction/app.env
sudo install -d -m 0700 -o ai-construction -g ai-construction /var/lib/ai-construction
```

Bước cài `app.env` ở trên dùng cho lần đầu. Khi cập nhật release, tiếp tục dùng file cấu hình đang vận hành.

## 3. Chuẩn bị dữ liệu và chạy API

Với công trình đang có, khôi phục gói backup đã duyệt vào thư mục dữ liệu trống trước khi tạo các thư mục con. Đối chiếu file đính kèm và các giá trị đường dẫn khi chuyển từ Windows sang Linux. Với database mới, Alembic tạo schema và script bootstrap tạo tài khoản quản trị đầu tiên.

```bash
# Chỉ chạy dòng restore nếu đã có backup riêng và thư mục dữ liệu còn trống.
# sudo -u ai-construction python3 "$release/scripts/restore.py" /duong-dan-rieng/backup.tar.gz /var/lib/ai-construction
sudo install -d -m 0700 -o ai-construction -g ai-construction \
  /var/lib/ai-construction/storage/{site,engineering-ai,acceptance} /var/lib/ai-construction/templates
sudo -u ai-construction bash -c '
  set -a
  source /etc/ai-construction/app.env
  cd "$1/backend"
  "$1/.venv/bin/python" -m alembic upgrade head
' bash "$release"
```

Đặt workbook đã duyệt ở `/var/lib/ai-construction/templates/acceptance-original.xlsx` với quyền đọc cho tài khoản dịch vụ nếu cần xuất PYC/BBNT. Với database mới, tạo admin bằng lệnh sau. Script hỏi mật khẩu qua terminal.

```bash
sudo -u ai-construction bash -c '
  set -a
  source /etc/ai-construction/app.env
  bash "$1/scripts/bootstrap_admin.sh"
' bash "$release"
```

Nếu dùng database từ môi trường demo, kiểm tra tài khoản thử và đổi mật khẩu qua ứng dụng trên kết nối riêng trước khi mở công khai. Ghi nhận phiên và quyền theo chính sách của dự án.

```bash
sudo ln -sfn "$release" /opt/ai-construction/current
sudo install -m 0644 "$release/deploy/gce/ai-construction.service" /etc/systemd/system/ai-construction.service
sudo systemctl daemon-reload
sudo systemctl enable --now ai-construction
curl --fail http://127.0.0.1:8765/health
sudo journalctl -u ai-construction -n 40 --no-pager
```

## 4. Bật HTTPS và kiểm tra

Trên VM dành cho ứng dụng này, cài mẫu Caddyfile rồi sửa `construction.example.com` thành tên miền của VM. Kiểm tra cấu hình, mở 80/443 theo phạm vi đã chọn và reload Caddy. [Caddy HTTPS](https://caddyserver.com/docs/automatic-https#hostname-requirements)

```bash
sudo install -m 0644 "$release/deploy/gce/Caddyfile" /etc/caddy/Caddyfile
sudoedit /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
# Thay tên miền trước khi kiểm tra.
curl --fail https://construction.example.com/health
curl --fail --head https://construction.example.com/
```

Kiểm trên điện thoại và với tài khoản theo vai trò thực tế. Mở Tổng quan, đi qua **Việc nhanh → Cập nhật tiến độ thi công**, đối chiếu cấu kiện DAP và khối lượng thiết kế, rồi thử ghi và xuất ở công trình kiểm thử riêng. Kiểm lại camera, PYC/BBNT PDF, và tải ảnh/PDF theo chức năng được bật.

## 5. Cập nhật và quay lui

Trước mỗi lần cập nhật, tạo release mới trong `releases/`. Dừng API trong khoảng bảo trì trước khi sao lưu để database và file đính kèm khớp nhau. Dùng backup SQLite của repository và lưu một bản ngoài VM. [SQLite Backup API](https://www.sqlite.org/backup.html)

```bash
sudo systemctl stop ai-construction
sudo install -d -m 0700 /var/backups/ai-construction
sudo python3 /opt/ai-construction/current/scripts/backup.py \
  "/var/backups/ai-construction/pre-update-$(date -u +%Y%m%dT%H%M%SZ).tar.gz" \
  --data-dir /var/lib/ai-construction
```

Chạy Alembic bằng release mới, đổi liên kết `current`, khởi động lại API và kiểm tra HTTPS. Giữ release cũ. Nếu schema tương thích, quay lui bằng cách trỏ `current` về release cũ và khởi động lại dịch vụ. Nếu phải khôi phục schema cùng dữ liệu, bảo toàn dữ liệu phát sinh sau lần backup, rồi dùng `restore.py` vào thư mục mới dưới `/var/lib/ai-construction`. Kiểm tra bản khôi phục trước khi đổi các đường dẫn trong `app.env`. Việc khôi phục cần giữ cùng bộ database và hồ sơ.
