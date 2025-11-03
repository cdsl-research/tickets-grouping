# tickets-grouping

# 概要
Prometheu・Alertmanagerからのアラート通知を受信し、Redmineにチケットを作成・集約するプログラムです。

# 主な機能
・Alertmanagerからのアラートを受信し、Redmineにチケットを作成<br>
・同一アラート名（alertname）で複数ホスト (instance) の場合、親チケット [Root] を作成し階層化<br>
・再発時は既存チケットにコメント追記<br>
・対処されなかったチケットは「持ち越し」ステータスに自動更新<br>

# 環境
・Ubuntu 24.04.2<br>
・Python（3.12.3）<br>
・Redmine（6.0.4）<br>
・Prometheus（2.53.1）<br>
・Alertmanager（0.27.0）<br>

# パッケージ・ライブラリ
・Fast API<br>
・uvicorn<br>
・requests<br>

# ディレクトリ構成
```bash
~/tickets_grouping/
├── tickets_grouping.py
└── .env
```

# 準備
## パッケージインストール<br>
FastAPI、uvicorn、requestsをインストールします
```bash
sudo apt update
sudo apt install -y python3-fastapi python3-uvicorn python3-requests
```

```bash
hoge@test:~/tickets_grouping$ sudo apt update
sudo apt install -y python3-fastapi python3-uvicorn python3-requests
Hit:1 http://jp.archive.ubuntu.com/ubuntu noble InRelease
Hit:2 http://security.ubuntu.com/ubuntu noble-security InRelease
Hit:3 http://jp.archive.ubuntu.com/ubuntu noble-updates InRelease
Hit:4 http://jp.archive.ubuntu.com/ubuntu noble-backports InRelease
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
102 packages can be upgraded. Run 'apt list --upgradable' to see them.
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
python3-requests is already the newest version (2.31.0+dfsg-1ubuntu1.1).
The following additional packages will be installed:
  python3-aiofiles python3-anyio python3-h11 python3-itsdangerous python3-multipart python3-pydantic python3-simplejson
  python3-sniffio python3-starlette python3-typing-extensions python3-uvloop python3-wsproto
Suggested packages:
  python3-databases python-uvicorn-doc
The following NEW packages will be installed:
  python3-aiofiles python3-anyio python3-fastapi python3-h11 python3-itsdangerous python3-multipart python3-pydantic
  python3-simplejson python3-sniffio python3-starlette python3-typing-extensions python3-uvicorn python3-uvloop
  python3-wsproto
0 upgraded, 14 newly installed, 0 to remove and 102 not upgraded.
Need to get 2,863 kB of archives.
After this operation, 12.1 MB of additional disk space will be used.
Get:1 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-aiofiles all 23.2.1-2 [10.6 kB]
Get:2 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-sniffio all 1.3.0-2 [7,216 B]
Get:3 http://jp.archive.ubuntu.com/ubuntu noble/main amd64 python3-typing-extensions all 4.10.0-1 [60.7 kB]
Get:4 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-anyio all 4.2.0-1 [56.5 kB]
Get:5 http://jp.archive.ubuntu.com/ubuntu noble/main amd64 python3-pydantic amd64 1.10.14-1 [1,856 kB]
Get:6 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-starlette all 0.31.1-1 [49.4 kB]
Get:7 http://jp.archive.ubuntu.com/ubuntu noble-updates/universe amd64 python3-h11 all 0.14.0-1ubuntu0.24.04.1 [51.7 kB]
Get:8 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-wsproto all 1.2.0-1 [23.6 kB]
Get:9 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-uvloop amd64 0.19.0+ds1-2.1 [561 kB]
Get:10 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-uvicorn all 0.27.1-1 [39.6 kB]
Get:11 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-fastapi all 0.101.0-3 [55.5 kB]
Get:12 http://jp.archive.ubuntu.com/ubuntu noble/main amd64 python3-itsdangerous all 2.1.2-4 [14.6 kB]
Get:13 http://jp.archive.ubuntu.com/ubuntu noble/universe amd64 python3-multipart all 0.0.9-1 [21.8 kB]
Get:14 http://jp.archive.ubuntu.com/ubuntu noble/main amd64 python3-simplejson amd64 3.19.2-1build2 [54.5 kB]
Fetched 2,863 kB in 2s (1,186 kB/s)
Selecting previously unselected package python3-aiofiles.
(Reading database ... 137463 files and directories currently installed.)
Preparing to unpack .../00-python3-aiofiles_23.2.1-2_all.deb ...
Unpacking python3-aiofiles (23.2.1-2) ...
Selecting previously unselected package python3-sniffio................................................................]
Preparing to unpack .../01-python3-sniffio_1.3.0-2_all.deb ............................................................]
Unpacking python3-sniffio (1.3.0-2) ...................................................................................]
Selecting previously unselected package python3-typing-extensions......................................................]
Preparing to unpack .../02-python3-typing-extensions_4.10.0-1_all.deb .................................................]
Unpacking python3-typing-extensions (4.10.0-1) ........................................................................]
Selecting previously unselected package python3-anyio..................................................................]
Preparing to unpack .../03-python3-anyio_4.2.0-1_all.deb ..............................................................]
Unpacking python3-anyio (4.2.0-1) ...
Selecting previously unselected package python3-pydantic.
Preparing to unpack .../04-python3-pydantic_1.10.14-1_amd64.deb ...
Unpacking python3-pydantic (1.10.14-1) ...
Selecting previously unselected package python3-starlette.
Preparing to unpack .../05-python3-starlette_0.31.1-1_all.deb ...
Unpacking python3-starlette (0.31.1-1) ...
Selecting previously unselected package python3-h11.
Preparing to unpack .../06-python3-h11_0.14.0-1ubuntu0.24.04.1_all.deb ...
Unpacking python3-h11 (0.14.0-1ubuntu0.24.04.1) ...
Selecting previously unselected package python3-wsproto.
Preparing to unpack .../07-python3-wsproto_1.2.0-1_all.deb ...
Unpacking python3-wsproto (1.2.0-1) ...
Selecting previously unselected package python3-uvloop.
Preparing to unpack .../08-python3-uvloop_0.19.0+ds1-2.1_amd64.deb ...
Unpacking python3-uvloop (0.19.0+ds1-2.1) ...
Selecting previously unselected package python3-uvicorn.
Preparing to unpack .../09-python3-uvicorn_0.27.1-1_all.deb ...
Unpacking python3-uvicorn (0.27.1-1) ...
Selecting previously unselected package python3-fastapi.
Preparing to unpack .../10-python3-fastapi_0.101.0-3_all.deb ...
Unpacking python3-fastapi (0.101.0-3) ...
Selecting previously unselected package python3-itsdangerous.
Preparing to unpack .../11-python3-itsdangerous_2.1.2-4_all.deb ...
Unpacking python3-itsdangerous (2.1.2-4) ...
Selecting previously unselected package python3-multipart.
Preparing to unpack .../12-python3-multipart_0.0.9-1_all.deb ...
Unpacking python3-multipart (0.0.9-1) ...
Selecting previously unselected package python3-simplejson.
Preparing to unpack .../13-python3-simplejson_3.19.2-1build2_amd64.deb ...
Unpacking python3-simplejson (3.19.2-1build2) ...
Setting up python3-sniffio (1.3.0-2) ...
Setting up python3-aiofiles (23.2.1-2) ...
Setting up python3-anyio (4.2.0-1) ...
Setting up python3-itsdangerous (2.1.2-4) ...
Setting up python3-starlette (0.31.1-1) ...
Setting up python3-simplejson (3.19.2-1build2) ...
Setting up python3-h11 (0.14.0-1ubuntu0.24.04.1) ...
Setting up python3-typing-extensions (4.10.0-1) ...
Setting up python3-uvloop (0.19.0+ds1-2.1) ...
Setting up python3-multipart (0.0.9-1) ...
Setting up python3-wsproto (1.2.0-1) ...
Setting up python3-pydantic (1.10.14-1) ...
Setting up python3-uvicorn (0.27.1-1) ...
Setting up python3-fastapi (0.101.0-3) ...
Scanning processes...
Scanning linux images...

Running kernel seems to be up-to-date.

No services need to be restarted.

No containers need to be restarted.

No user sessions are running outdated binaries.

No VM guests are running outdated hypervisor (qemu) binaries on this host.
c0117304@c0117304-test:~/alert-webhook$
```

## 環境変数ファイルを設定
環境変数ファイルに、Redmineの各種情報を設定します
```bash
sudo tee .env <<'EOF'
REDMINE_URL=https://redmine.example.com
REDMINE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
REDMINE_PROJECT_ID=123
REDMINE_TRACKER_ID=1
REDMINE_STATUS_CARRYOVER=9
EOF
```
REDMINE_URL：RedmineのホームのURL</br>
REDMINE_API_KEY：個人設定にあるAPIキー</br>
REDMINE_PROJECT_ID：チケットを登録するプロジェクトのIDまたはプロジェクト名</br>
REDMINE_TRACKER_ID：チケットを登録するトラッカーのID</br>
REDMINE_STATUS_DONE：完了ステータスID</br>
REDMINE_STATUS_CARRYOVER：持越しステータスID

## systemdサービス設定
今回はsystemdで動かします</br>
`/etc/systemd/system/alert-webhook.service` を作成します<br>
```bash
sudo nano /etc/systemd/system/alert-webhook.service
```

```bash
hoge@test:/etc/systemd/system$ ls
alert-webhook.service                       graphical.target.wants          sockets.target.wants
cloud-config.target.wants                   hibernate.target.wants          sshd.service
cloud-final.service.wants                   hybrid-sleep.target.wants       ssh.service.requires
cloud-init.target.wants                     iscsi.service                   suspend.target.wants
dbus-org.freedesktop.ModemManager1.service  mdmonitor.service.wants         suspend-then-hibernate.target.wants
dbus-org.freedesktop.resolve1.service       multi-user.target.wants         sysinit.target.wants
dbus-org.freedesktop.thermald.service       network-online.target.wants     syslog.service
dbus-org.freedesktop.timesync1.service      oem-config.service.wants        sysstat.service.wants
display-manager.service.wants               open-vm-tools.service.requires  timers.target.wants
emergency.target.wants                      paths.target.wants              vmtoolsd.service
final.target.wants                          rescue.target.wants
getty.target.wants                          sleep.target.wants
hoge@test:/etc/systemd/system$
```
↓alert-webhook.serviceの内容<br>
```ini
[Unit]
Description=Alert Webhook FastAPI Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/hoge/tickets_grouping
EnvironmentFile/home/hoge/alert-webhook/.env
ExecStart=/usr/bin/uvicorn app:app --host 0.0.0.0 --port 5005
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

##  systemdサービスの起動
systemdを起動します
```bash
sudo systemctl daemon-reload
sudo systemctl enable alert-webhook
sudo systemctl start alert-webhook
sudo systemctl status alert-webhook
```
以下のように表示され、`Active: active (running)`となっていれば動いています
```bash
hoge@test:~/tickets_grouping$ sudo systemctl daemon-reload
sudo systemctl enable alert-webhook
sudo systemctl start alert-webhook
sudo systemctl status alert-webhook
● alert-webhook.service - Alertmanager Webhook Receiver (FastAPI)
     Loaded: loaded (/etc/systemd/system/alert-webhook.service; enabled; preset: enabled)
     Active: active (running) since Mon 2025-11-03 07:08:36 UTC; 1h 1min ago
   Main PID: 1265 (uvicorn)
      Tasks: 1 (limit: 4605)
     Memory: 47.2M (peak: 47.7M)
        CPU: 5.054s
     CGroup: /system.slice/alert-webhook.service
             └─1265 /home/hoge/tickets-grouping/venv/bin/python3 /home/hoge/tickets-grouping/venv/bin/uv>

Nov 03 07:08:36 test systemd[1]: Started alert-webhook.service - Alertmanager Webhook Receiver (FastAPI).
Nov 03 07:08:37 test uvicorn[1265]: INFO:     Started server process [1265]
Nov 03 07:08:37 test uvicorn[1265]: INFO:     Waiting for application startup.
Nov 03 07:08:37 test uvicorn[1265]: INFO:     Application startup complete.
Nov 03 07:08:37 test uvicorn[1265]: INFO:     Uvicorn running on http://0.0.0.0:5005 (Press CTRL+C to quit)
Nov 03 07:08:40 test uvicorn[1265]: INFO:     192.168.100.61:65370 - "POST /webhook HTTP/1.1" 200 OK
Nov 03 07:09:20 test uvicorn[1265]: INFO:     192.168.100.61:9695 - "POST /webhook HTTP/1.1" 200 OK
Nov 03 07:13:12 test uvicorn[1265]: INFO:     192.168.100.61:4784 - "POST /webhook HTTP/1.1" 200 OK
Nov 03 07:13:12 test uvicorn[1265]: INFO:     192.168.100.61:45367 - "POST /webhook HTTP/1.1" 200 OK
Nov 03 07:26:01 test uvicorn[1265]: INFO:     192.168.100.61:39234 - "POST /webhook HTTP/1.1" 200 OK
lines 1-20/20 (END)
```

## Alertmanagerの設定
`alertmanager.yml`に以下を追加し、チケット作成ソフトに通知が飛ぶようにします
```yaml
 receivers:
      - name: "redmine"
        webhook_configs:
          - url: "http://<マシンのIPアドレスorDNS名:<port番号>/webhook"
            send_resolved: <false OR ture>
```

## 動作確認
ローカルマシンから`curl`でRedmineにチケットがきちんと作成されるか確認します

```bash
curl -X POST http://localhost:5005/webhook \
-H "Content-Type: application/json" \
-d '{
  "alerts": [
    {
      "labels": {
        "alertname": "test",
        "instance": "server01"
      },
      "annotations": {
        "description": "test: server01"
      }
    }
  ]
}'
```

うまくいけば、CUIに`{"status":"ok"}`が表示され、Redmine に [Alert] test (server01) チケットが作成されます</br>
```bash
hoge@test:~/tickets_grouping$ curl -X POST http://localhost:5005/webhook -H "Content-Type: application/json" -d '{
  "alerts": [
    {
      "labels": {
        "alertname": "test",
        "instance": "server01"
      },
      "annotations": {
        "description": "test: server01"
      }
    }
  ]
}'
{"status":"ok"}hoge@test:~/tickets_grouping$
```
![7](https://github.com/user-attachments/assets/79d805ca-ef47-4359-88bb-b273a9fa89b5)


うまくいかない場合は、`.env`ファイルとAlertmanagerの`yaml`ファイルを確認してください。

## チケットグルーピング
Alertmanagerから通知を受け取ると`alertname`と`instance（ホスト名）`に基づいてチケットを登録していきます。

### 初回アラート
`[Alert] <alertname> (<instance>)` 形式でチケットを作成

### 同一ホスト・同一アラート再発
既存チケットに「再発」コメントを追加

### 異なるホストで同一アラートが発生
`[Root] [Alert] <alertname>` の親チケットを自動生成し、各ホストのチケットを子チケットとして、関連付ける。</br>

---
これにより、同じ種類のアラートが複数ホストで発生しても、Redmine上では1つの「Root」チケットを中心に整理できます。
