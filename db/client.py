# -*- coding: utf-8 -*-
import requests
import urllib.parse
from config.settings import SUPABASE_URL, SUPABASE_KEY


HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


def _build_url(table, query_parts=None):
    base = f"{SUPABASE_URL}/rest/v1/{table}"
    if not query_parts:
        return base
    return base + "?" + "&".join(query_parts)


def _safe_json(res):
    try:
        return res.json()
    except Exception:
        return []


def _print_http_error(prefix, res):
    print(f"❌ {prefix}")
    print("status_code:", res.status_code)
    print("url:", res.url)
    try:
        print("body:", res.text)
    except Exception:
        pass


def select(table):
    url = _build_url(table, ["select=*"])

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            _print_http_error("SELECT ERROR", res)
            return []
        return _safe_json(res)
    except Exception as e:
        print("❌ SELECT EXCEPTION")
        print("url:", url)
        print("error:", e)
        return []


def select_where(table, filters, order_by=None, limit=None):
    query = ["select=*"]

    for k, v in filters.items():
        query.append(f"{k}=eq.{urllib.parse.quote(str(v))}")

    if order_by:
        query.append(f"order={urllib.parse.quote(order_by)}")

    if limit:
        query.append(f"limit={int(limit)}")

    url = _build_url(table, query)

    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            _print_http_error("SELECT_WHERE ERROR", res)
            return []
        return _safe_json(res)
    except Exception as e:
        print("❌ SELECT_WHERE EXCEPTION")
        print("url:", url)
        print("error:", e)
        return []


def insert(table, data):
    url = _build_url(table)

    try:
        res = requests.post(url, headers=HEADERS, json=data, timeout=15)
        if not res.ok:
            _print_http_error("INSERT ERROR", res)
            return []
        return _safe_json(res) if res.text else []
    except Exception as e:
        print("❌ INSERT EXCEPTION")
        print("url:", url)
        print("error:", e)
        return []


def upsert(table, data, on_conflict):
    if isinstance(on_conflict, (list, tuple)):
        on_conflict = ",".join(on_conflict)

    headers = dict(HEADERS)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    url = _build_url(
        table,
        [f"on_conflict={urllib.parse.quote(str(on_conflict))}"]
    )

    try:
        res = requests.post(url, headers=headers, json=data, timeout=15)
        if not res.ok:
            _print_http_error("UPSERT ERROR", res)
            return []
        return _safe_json(res) if res.text else []
    except Exception as e:
        print("❌ UPSERT EXCEPTION")
        print("url:", url)
        print("error:", e)
        return []


def update_where(table, filters, data):
    query = []

    for k, v in filters.items():
        query.append(f"{k}=eq.{urllib.parse.quote(str(v))}")

    url = _build_url(table, query)

    try:
        res = requests.patch(url, headers=HEADERS, json=data, timeout=15)
        if not res.ok:
            _print_http_error("UPDATE ERROR", res)
            return []
        return _safe_json(res) if res.text else []
    except Exception as e:
        print("❌ UPDATE EXCEPTION")
        print("url:", url)
        print("error:", e)
        return []


def delete_where(table, filters):
    query = []

    for k, v in filters.items():
        query.append(f"{k}=eq.{urllib.parse.quote(str(v))}")

    url = _build_url(table, query)

    try:
        res = requests.delete(url, headers=HEADERS, timeout=15)
        if not res.ok:
            _print_http_error("DELETE ERROR", res)
            return False
        return True
    except Exception as e:
        print("❌ DELETE EXCEPTION")
        print("url:", url)
        print("error:", e)
        return False
