import os
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple

import requests
from fastapi import FastAPI, Request

# =========================
# 設定（環境変数は systemd の EnvironmentFile から）
# =========================

REDMINE_URL = (os.getenv("REDMINE_URL") or "").rstrip("/")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY") or ""
REDMINE_PROJECT_ID = os.getenv("REDMINE_PROJECT_ID") or ""
REDMINE_TRACKER_ID = os.getenv("REDMINE_TRACKER_ID") or ""
# Root用トラッカーを分けたい場合のみ REDMINE_ROOT_TRACKER_ID を設定
REDMINE_ROOT_TRACKER_ID = os.getenv("REDMINE_ROOT_TRACKER_ID") or REDMINE_TRACKER_ID

if not REDMINE_URL or not REDMINE_API_KEY or not REDMINE_PROJECT_ID or not REDMINE_TRACKER_ID:
    raise RuntimeError(
        "REDMINE_URL / REDMINE_API_KEY / REDMINE_PROJECT_ID / REDMINE_TRACKER_ID を環境変数で設定してください"
    )

WINDOW_HOURS = 4
WINDOW_DELTA = timedelta(hours=WINDOW_HOURS)


# =========================
# Redmine helper
# =========================

def _redmine_headers() -> Dict[str, str]:
    return {
        "X-Redmine-API-Key": REDMINE_API_KEY,
        "Content-Type": "application/json",
    }


def _parse_redmine_datetime(dt_str: str) -> datetime:
    """Redmineの日時文字列をUTCのdatetimeに変換"""
    if dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_issue_in_redmine(
    subject: str,
    description: str,
    tracker_id: Optional[str] = None,
    parent_issue_id: Optional[int] = None,
) -> int:
    """Redmineにチケットを作成して issue_id を返す"""
    if tracker_id is None:
        tracker_id = REDMINE_TRACKER_ID

    payload: Dict[str, Any] = {
        "issue": {
            "project_id": int(REDMINE_PROJECT_ID),
            "tracker_id": int(tracker_id),
            "subject": subject,
            "description": description,
        }
    }

    if parent_issue_id is not None:
        payload["issue"]["parent_issue_id"] = parent_issue_id

    resp = requests.post(
        f"{REDMINE_URL}/issues.json",
        headers=_redmine_headers(),
        data=json.dumps(payload),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return int(data["issue"]["id"])


def add_comment_to_issue(issue_id: int, comment: str) -> None:
    """既存チケットにコメントを追記"""
    payload = {"issue": {"notes": comment}}
    resp = requests.put(
        f"{REDMINE_URL}/issues/{issue_id}.json",
        headers=_redmine_headers(),
        data=json.dumps(payload),
        timeout=10,
    )
    resp.raise_for_status()


def set_parent_issue(issue_id: int, parent_issue_id: int) -> None:
    """既存チケットの親チケットを設定"""
    payload = {"issue": {"parent_issue_id": parent_issue_id}}
    resp = requests.put(
        f"{REDMINE_URL}/issues/{issue_id}.json",
        headers=_redmine_headers(),
        data=json.dumps(payload),
        timeout=10,
    )
    resp.raise_for_status()


def search_alert_issues(alertname: str) -> List[Dict[str, Any]]:
    """
    指定された alertname に関連する Redmine のチケット一覧を返す。
    project_id などは環境変数の設定を使用。
    """
    issues: List[Dict[str, Any]] = []
    offset = 0
    limit = 100

    # subject=~alertname であいまい検索
    while True:
        params = {
            "project_id": REDMINE_PROJECT_ID,
            "status_id": "*",          # 全ステータス対象
            "subject": f"~{alertname}",
            "offset": offset,
            "limit": limit,
            "sort": "updated_on:desc",
        }
        resp = requests.get(
            f"{REDMINE_URL}/issues.json",
            headers=_redmine_headers(),
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("issues", [])
        issues.extend(batch)

        total_count = data.get("total_count", len(issues))
        offset += len(batch)
        if offset >= total_count or not batch:
            break

    return issues


def classify_issues_for_alert(
    alertname: str,
    event_time: datetime,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Redmineから取得したチケット群を、
      - relevant_root_issue: 4時間以内に更新がある Rootチケット（あれば）
      - relevant_host_issues: {instance: issue} 4時間以内に更新があるホスト別チケット
    に分類する。
    """
    issues = search_alert_issues(alertname)

    relevant_root_issue: Optional[Dict[str, Any]] = None
    relevant_host_issues: Dict[str, Dict[str, Any]] = {}

    for issue in issues:
        updated_str = issue.get("updated_on")
        if not updated_str:
            continue
        updated_at = _parse_redmine_datetime(updated_str)

        # 4時間より古いものは「前のクラスタ」とみなして無視
        if event_time - updated_at > WINDOW_DELTA:
            continue

        subject = issue.get("subject", "")

        # Root判定
        root_subject = f"[Root][Alert] {alertname}"
        if subject.startswith(root_subject):
            # より新しい Root を優先
            if (
                relevant_root_issue is None
                or _parse_redmine_datetime(relevant_root_issue["updated_on"]) < updated_at
            ):
                relevant_root_issue = issue
            continue

        # ホストチケット判定: "[Alert] {alertname} (" で始まり、末尾 ) の中身を instance とみなす
        prefix = f"[Alert] {alertname} ("
        if subject.startswith(prefix) and subject.endswith(")"):
            instance = subject[len(prefix):-1]
            # 同じinstanceなら updated_on が新しい方を採用
            if instance not in relevant_host_issues:
                relevant_host_issues[instance] = issue
            else:
                prev = relevant_host_issues[instance]
                prev_updated = _parse_redmine_datetime(prev["updated_on"])
                if updated_at > prev_updated:
                    relevant_host_issues[instance] = issue

    return relevant_root_issue, relevant_host_issues


# =========================
# アラートの整形
# =========================

def parse_event_time(alert: Dict[str, Any]) -> datetime:
    """AlertmanagerのstartsAtをUTC datetimeに変換（なければ現在時刻）"""
    starts_at = alert.get("startsAt")
    if not starts_at:
        return datetime.now(timezone.utc)
    try:
        if starts_at.endswith("Z"):
            starts_at = starts_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(starts_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def build_issue_description(alert: Dict[str, Any]) -> str:
    """
    Alertmanager UI と同様の構成で Redmine の description を生成する。
    Alert Overview / Labels / Annotations の3ブロックに分ける。
    """
    status = alert.get("status", "")
    receiver = alert.get("receiver", "")
    starts_at = alert.get("startsAt", "")
    ends_at = alert.get("endsAt", "")
    generatorURL = alert.get("generatorURL", "")
    externalURL = alert.get("externalURL", "")

    labels = alert.get("labels", {}) or {}
    annotations = alert.get("annotations", {}) or {}

    labels_json = json.dumps(labels, indent=2, ensure_ascii=False)
    annotations_json = json.dumps(annotations, indent=2, ensure_ascii=False)

    text = (
        "Alert Overview\n"
        "--------------\n"
        f"- status: {status}\n"
        f"- receiver: {receiver}\n"
        f"- startsAt: {starts_at}\n"
        f"- endsAt: {ends_at}\n"
        f"- generatorURL: {generatorURL}\n"
        f"- externalURL: {externalURL}\n\n"
        "Labels\n"
        "------\n"
        f"{labels_json}\n\n"
        "Annotations\n"
        "-----------\n"
        f"{annotations_json}\n"
    )

    return text


def build_reoccurrence_comment(alert: Dict[str, Any]) -> str:
    """再発時に既存チケットへ追記するコメント"""
    labels = alert.get("labels", {}) or {}
    annotations = alert.get("annotations", {}) or {}
    starts_at = alert.get("startsAt")
    instance = labels.get("instance", "unknown")
    alertname = labels.get("alertname", "unknown")
    summary = annotations.get("summary") or annotations.get("description") or ""

    return (
        f"[再発] alertname={alertname}, instance={instance}\n"
        f"startsAt : {starts_at}\n"
        f"summary  : {summary}"
    )


# =========================
# グルーピングロジック
# =========================

def process_single_alert(alert: Dict[str, Any]) -> str:
    """
    ・最後にそのアラートが出てから4時間以内は同じチケットにまとめる
    ・4時間以内になければチケットを作成
    ・同じアラート＋ホスト（instance）はコメント追記
    ・同じアラートでホストが異なる場合は Root＋子チケット
      （状態はすべて Redmine REST API から取得）
    """
    if alert.get("status") != "firing":
        return "skip: status is not firing"

    labels = alert.get("labels", {}) or {}
    alertname = labels.get("alertname")
    instance = labels.get("instance")

    if not alertname or not instance:
        return "skip: alertname or instance is missing"

    event_time = parse_event_time(alert)

    # Redmine から「同じ alertname の最近4時間以内に更新されたチケット」を取得・分類
    root_issue, host_issues = classify_issues_for_alert(alertname, event_time)

    # 4時間以内に関連チケットが1件もない → 完全に新しいクラスタとして単独チケットを作成
    if root_issue is None and not host_issues:
        subject = f"[Alert] {alertname} ({instance})"
        description = build_issue_description(alert)
        issue_id = create_issue_in_redmine(subject, description)
        return f"create_single alertname={alertname} instance={instance} issue_id={issue_id}"

    # 4時間以内に「同じホスト」のチケットがある → コメント追記
    if instance in host_issues:
        issue = host_issues[instance]
        issue_id = issue["id"]
        comment = build_reoccurrence_comment(alert)
        add_comment_to_issue(issue_id, comment)
        return f"add_comment alertname={alertname} instance={instance} issue_id={issue_id}"

    # ここからは「4時間以内に同じ alertname の別ホストのチケットがあるが、このホストは初登場」のケース

    # Root がまだ無い → 今回がこのクラスタの2ホスト目なので Root を作成
    if root_issue is None:
        existing_issues = list(host_issues.values())

        # Rootチケット作成
        root_subject = f"[Root][Alert] {alertname}"
        root_description = f"{alertname} の共通親チケットです。各ホストの発生は子チケットとして管理します。"
        root_issue_id = create_issue_in_redmine(
            root_subject,
            root_description,
            tracker_id=REDMINE_ROOT_TRACKER_ID,
        )

        # 既存ホストチケットを子チケット化
        for issue in existing_issues:
            set_parent_issue(issue["id"], root_issue_id)

        # 新しいホスト用の子チケットを作成
        subject = f"[Alert] {alertname} ({instance})"
        description = build_issue_description(alert)
        child_issue_id = create_issue_in_redmine(
            subject,
            description,
            tracker_id=REDMINE_TRACKER_ID,
            parent_issue_id=root_issue_id,
        )

        return (
            "create_root_and_child "
            f"alertname={alertname} root_issue_id={root_issue_id} "
            f"instance={instance} issue_id={child_issue_id}"
        )

    # 既に Root がある → 新ホスト用の子チケットだけ追加
    root_issue_id = root_issue["id"]
    subject = f"[Alert] {alertname} ({instance})"
    description = build_issue_description(alert)
    child_issue_id = create_issue_in_redmine(
        subject,
        description,
        tracker_id=REDMINE_TRACKER_ID,
        parent_issue_id=root_issue_id,
    )

    return (
        "create_child "
        f"alertname={alertname} root_issue_id={root_issue_id} "
        f"instance={instance} issue_id={child_issue_id}"
    )


# =========================
# FastAPI
# =========================

app = FastAPI()


@app.post("/alert")
async def receive_alert(request: Request):
    payload = await request.json()
    alerts = payload.get("alerts", [])

    results: List[str] = []
    for alert in alerts:
        try:
            msg = process_single_alert(alert)
            results.append(msg)
        except Exception as e:
            # 例外が起きても他のアラート処理は続ける
            results.append(f"error: {e}")

    return {"message": "ok", "results": results}
