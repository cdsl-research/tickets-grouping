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

# Pythonで使用したパッケージ・ライブラリ
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
先に`apt update`をします

```shell
hoge@test:~/alert-webhook$ sudo apt update
```

```shell
hoge@test:~/tickets_grouping$ sudo apt update
[sudo] password for c0117304:
Get:1 http://security.ubuntu.com/ubuntu noble-security InRelease [126 kB]
Hit:2 http://jp.archive.ubuntu.com/ubuntu noble InRelease
Get:3 http://jp.archive.ubuntu.com/ubuntu noble-updates InRelease [126 kB]
Get:4 http://security.ubuntu.com/ubuntu noble-security/main amd64 Packages [1,298 kB]
Get:5 http://security.ubuntu.com/ubuntu noble-security/main Translation-en [213 kB]
Get:6 http://security.ubuntu.com/ubuntu noble-security/main amd64 Components [21.5 kB]
Get:7 http://security.ubuntu.com/ubuntu noble-security/main amd64 c-n-f Metadata [9,012 B]
Get:8 http://security.ubuntu.com/ubuntu noble-security/restricted amd64 Packages [2,131 kB]
Get:9 http://jp.archive.ubuntu.com/ubuntu noble-backports InRelease [126 kB]
Get:10 http://security.ubuntu.com/ubuntu noble-security/restricted Translation-en [483 kB]
Get:11 http://security.ubuntu.com/ubuntu noble-security/restricted amd64 Components [212 B]
Get:12 http://security.ubuntu.com/ubuntu noble-security/universe amd64 Packages [906 kB]
Get:13 http://security.ubuntu.com/ubuntu noble-security/universe Translation-en [203 kB]
Get:14 http://security.ubuntu.com/ubuntu noble-security/universe amd64 Components [52.2 kB]
Get:15 http://security.ubuntu.com/ubuntu noble-security/multiverse amd64 Components [208 B]
Get:16 http://jp.archive.ubuntu.com/ubuntu noble-updates/main amd64 Packages [1,578 kB]
Get:17 http://jp.archive.ubuntu.com/ubuntu noble-updates/main Translation-en [297 kB]
Get:18 http://jp.archive.ubuntu.com/ubuntu noble-updates/main amd64 Components [175 kB]
Get:19 http://jp.archive.ubuntu.com/ubuntu noble-updates/main amd64 c-n-f Metadata [15.4 kB]
Get:20 http://jp.archive.ubuntu.com/ubuntu noble-updates/restricted amd64 Packages [2,235 kB]
Get:21 http://jp.archive.ubuntu.com/ubuntu noble-updates/restricted Translation-en [506 kB]
Get:22 http://jp.archive.ubuntu.com/ubuntu noble-updates/restricted amd64 Components [212 B]
Get:23 http://jp.archive.ubuntu.com/ubuntu noble-updates/universe amd64 Components [378 kB]
Get:24 http://jp.archive.ubuntu.com/ubuntu noble-updates/multiverse amd64 Components [940 B]
Get:25 http://jp.archive.ubuntu.com/ubuntu noble-backports/main amd64 Components [7,140 B]
Get:26 http://jp.archive.ubuntu.com/ubuntu noble-backports/restricted amd64 Components [216 B]
Get:27 http://jp.archive.ubuntu.com/ubuntu noble-backports/universe amd64 Components [11.0 kB]
Get:28 http://jp.archive.ubuntu.com/ubuntu noble-backports/multiverse amd64 Components [212 B]
Fetched 10.9 MB in 4s (2,560 kB/s)
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
102 packages can be upgraded. Run 'apt list --upgradable' to see them.
hoge@test:~/alert-webhook$
```
FastAPI、uvicorn、requestsをインストールします
```shell
hoge@test:~/alert-webhook$ sudo apt install -y python3-fastapi python3-uvicorn python3-requests
Reading package lists... Done
Building dependency tree... Done
Reading state information... Done
python3-fastapi is already the newest version (0.101.0-3).
python3-uvicorn is already the newest version (0.27.1-1).
python3-requests is already the newest version (2.31.0+dfsg-1ubuntu1.1).
0 upgraded, 0 newly installed, 0 to remove and 102 not upgraded.
hoge@test:~/alert-webhook$
```
この環境では既にインストール済みなので、出力結果が違うかもしれません

## 環境変数ファイルを設定
環境変数ファイルに、Redmineの各種情報を設定します
```bash
hoge@test:~/alert-webhook$ sudo tee .env <<'EOF'
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
hoge@test:~/tickets-grouping$sudo nano /etc/systemd/system/alert-webhook.service
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

`ls`をすると`alert-webhook.service`が追加されています
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
##  systemdサービスの起動
systemdを起動します
```bash
hoge@test:~/tickets_grouping$ sudo systemctl daemon-reload
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
hoge@test:~/tickets_grouping$ curl -X POST http://localhost:5005/webhook \
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
