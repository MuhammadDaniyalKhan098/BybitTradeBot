import os
import json
import datetime
from threading import Thread
import requests

SHEET_URL = os.getenv("LOG_SHEET_URL")

def _dispatch_log(payload: dict):
    if not SHEET_URL:
        return
    try:
        requests.post(
            SHEET_URL, 
            data=json.dumps(payload), 
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
    except Exception as e:
        print(f"[ERROR] Webhook dispatch failed: {e}")

def log_trade(trade_data: dict, status: str, report_text: str, original_msg: str):
    payload = {
        "timestamp": datetime.datetime.now().isoformat(),
        "symbol": trade_data.get('symbol', 'UNKNOWN'),
        "action": trade_data.get('action', 'UNKNOWN'),
        "status": status,
        "details": report_text,
        "original_msg": original_msg[:250]
    }
    Thread(target=_dispatch_log, args=(payload,), daemon=True).start()