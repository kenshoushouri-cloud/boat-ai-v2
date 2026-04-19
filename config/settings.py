# -*- coding: utf-8 -*-
import os

# =========================
# LINE
# =========================
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_USER_ID = os.environ.get("LINE_USER_ID", "").strip()

# =========================
# Supabase
# =========================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

# =========================
# モデル
# =========================
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v2.0.0").strip()

# =========================
# 設定値
# =========================
TICKET_UNIT_YEN = 100
