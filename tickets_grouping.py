import os
import re
import requests
from fastapi import FastAPI, Request
from datetime import datetime

app = FastAPI()

# ===== 環境変数からRedmine接続情報を取得 =====
REDMINE_URL = os.getenv("REDMINE_URL")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY")
PROJECT_ID = os.getenv("REDMINE_PROJECT_ID")
TRACKER_ID = os.getenv("REDMINE_TRACKER_ID")
STATUS_DONE = int(os.getenv("REDMINE_STATUS_DONE", 8))       # 完了
STATUS_CARRYOVER = int(os.getenv("REDMINE_STATUS_CARRYOVER", 9))  # 持ち越し

headers = {
    "X-Redmine-API-Key": REDMINE_API_KEY,
    "Content-Type": "application/json"
}

# ===== Redmine操作関数 =====

def find_root_ticket(alertname):
    """[Root]付きの親チケットを検索"""
    url = f"{REDMINE_URL}/issues.json"
    params = {
        "project_id": PROJECT_ID,
        "subject": f"[Root] [Alert] {alertname}",
        "status_id": "*"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    issues = response.json().get("issues", [])
    return issues[0] if issues else None

def search_tickets_by_alertname(alertname):
    """alertnameに紐づくチケットをすべて取得"""
    url = f"{REDMINE_URL}/issues.json"
    params = {
        "project_id": PROJECT_ID,
        "status_id": "*",
        "limit": 100
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    issues = response.json().get("issues", [])
    return [i for i in issues if f"[Alert] {alertname}" in i["subject"]]

def search_child_ticket(parent_id, instance):
    """親チケット配下で、指定ホストの子チケットがあるか確認"""
    url = f"{REDMINE_URL}/issues.json"
    params = {
        "parent_id": parent_id,
        "status_id": "*"
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    issues = response.json().get("issues", [])
    for issue in issues:
        if f"({instance})" in issue.get("subject", ""):
            return issue
    return None

def move_to_root(root_id, issue_id):
    """既存チケットをRoot配下に移動"""
    url = f"{REDMINE_URL}/issues/{issue_id}.json"
    payload = {"issue": {"parent_issue_id": root_id}}
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()

def create_parent_ticket(alertname):
    """親チケットを作成（タイトルに[Root]を付与）"""
    payload = {
        "issue": {
            "project_id": PROJECT_ID,
            "tracker_id": TRACKER_ID,
            "subject": f"[Root] [Alert] {alertname}",
            "description": f"Root ticket for {alertname}"
        }
    }
    url = f"{REDMINE_URL}/issues.json"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["issue"]

def create_child_ticket(alertname, instance, description, parent_id=None):
    """子チケットを作成（subject に instance を含める）"""
    subject = f"[Alert] {alertname} ({instance})"
    payload = {
        "issue": {
            "project_id": PROJECT_ID,
            "tracker_id": TRACKER_ID,
            "subject": subject,
            "description": description
        }
    }
    if parent_id:
        payload["issue"]["parent_issue_id"] = parent_id

    url = f"{REDMINE_URL}/issues.json"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()["issue"]

def add_comment(issue_id, note):
    """既存のチケットにコメント追加"""
    payload = {"issue": {"notes": note}}
    url = f"{REDMINE_URL}/issues/{issue_id}.json"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()

# ===== Pod名抽出ユーティリティ =====

def extract_pod_name(description: str) -> str:
    match = re.search(r":\s*([^\s]+)$", description.strip())
    if match:
        return match.group(1)
    return "UnknownPod"

# ===== Webhookエンドポイント =====

@app.post("/webhook")
async def handle_alert(request: Request):
    """Alertmanager Webhookを受信してチケット作成 or コメント追記"""
    data = await request.json()
    alerts = data.get("alerts", [])

    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        alertname = labels.get("alertname", "Unknown Alert")
        instance = labels.get("instance", "Unknown Instance")
        description = annotations.get("description", "")
        pod_name = extract_pod_name(description)

        full_description = f"Instance {instance}\nPod: {pod_name}\n{description}\n{datetime.now()}"

        # 1. 既存Rootがあるか確認
        root_ticket = find_root_ticket(alertname)

        # 2. 同じ subject のチケットがあるか確認
        existing_tickets = search_tickets_by_alertname(alertname)
        same_subject_ticket = next(
            (i for i in existing_tickets if i["subject"] == f"[Alert] {alertname} ({instance})"),
            None
        )

        if same_subject_ticket:
            # 同じアラート名 + 同じホスト → コメント追記
            add_comment(same_subject_ticket["id"], f"再発: {full_description}")
            continue

        if root_ticket:
            # Rootがある → 子チケット作成
            create_child_ticket(alertname, instance, full_description, root_ticket["id"])
            continue

        # 既存チケットに他ホストがあるか？
        existing_instances = {re.search(r"\((.*?)\)", i["subject"]).group(1)
                              for i in existing_tickets if re.search(r"\((.*?)\)", i["subject"])}

        if existing_instances and instance not in existing_instances:
            # 異なるホストが存在する場合のみ Root 作成
            root_ticket = create_parent_ticket(alertname)

            # 既存チケットをRoot配下に移動
            for issue in existing_tickets:
                move_to_root(root_ticket["id"], issue["id"])

            # 今回のチケットを子チケットとして追加
            create_child_ticket(alertname, instance, full_description, root_ticket["id"])

        else:
            # まだ1件目 → 通常チケット
            create_child_ticket(alertname, instance, full_description)

    return {"status": "ok"}

