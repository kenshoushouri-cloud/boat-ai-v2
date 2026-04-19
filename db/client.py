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


def select(table):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()
    return res.json()


def select_where(table, filters, order_by=None, limit=None):
    query = ["select=*"]

    for k, v in filters.items():
        query.append(f"{k}=eq.{urllib.parse.quote(str(v))}")

    if order_by:
        query.append(f"order={urllib.parse.quote(order_by)}")

    if limit:
        query.append(f"limit={int(limit)}")

    url = f"{SUPABASE_URL}/rest/v1/{table}?" + "&".join(query)
    res = requests.get(url, headers=HEADERS, timeout=15)
    res.raise_for_status()
    return res.json()


def insert(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    res = requests.post(url, headers=HEADERS, json=data, timeout=15)
    res.raise_for_status()
    return res.json() if res.text else []


def upsert(table, data, on_conflict):
    if isinstance(on_conflict, (list, tuple)):
        on_conflict = ",".join(on_conflict)

    headers = dict(HEADERS)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
    res = requests.post(url, headers=headers, json=data, timeout=15)
    res.raise_for_status()
    return res.json() if res.text else []
