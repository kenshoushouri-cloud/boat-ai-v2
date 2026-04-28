# -*- coding: utf-8 -*-
import os

# ==========================================
# Supabase 設定
# ==========================================

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ==========================================
# LINE通知設定
# ==========================================

ENABLE_LINE_NOTIFY = os.environ.get("ENABLE_LINE_NOTIFY", "false").lower() == "true"

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.environ.get("LINE_USER_ID", "")

# ==========================================
# モデル設定
# ==========================================

MODEL_VERSION = "v2.0.0"

# ==========================================
# 予想パラメータ
# ==========================================

MAX_BETS_PER_RACE = 2
MIN_PROB_GAP = 0.001
RACE_SCORE_THRESHOLD = 0.06
MAX_DAILY_BETS = 10

# ==========================================
# デバッグ設定
# ==========================================

DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# ==========================================
# 起動時チェック
# ==========================================

def _validate_settings():
    if not SUPABASE_URL or "supabase.co" not in SUPABASE_URL:
        raise Exception("SUPABASE_URL が不正です")

    if not SUPABASE_KEY or len(SUPABASE_KEY) < 20:
        raise Exception("SUPABASE_KEY が未設定です")

    if ENABLE_LINE_NOTIFY:
        if not LINE_CHANNEL_ACCESS_TOKEN:
            raise Exception("LINE_CHANNEL_ACCESS_TOKEN 未設定")
        if not LINE_USER_ID:
            raise Exception("LINE_USER_ID 未設定")

    print("✅ SETTINGS OK")
    print("SUPABASE_URL:", SUPABASE_URL)
    print("LINE通知:", "ON" if ENABLE_LINE_NOTIFY else "OFF")


_validate_settings()