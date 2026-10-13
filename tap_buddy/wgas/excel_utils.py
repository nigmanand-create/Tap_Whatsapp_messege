from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any

HEADER_ALIASES = {
	"date": ("date", "schedule date", "send date"),
	"time": ("time", "schedule time", "send time"),
	"groups": (
		"whatsapp group",
		"whatsapp groups",
		"group",
		"groups",
		"wa group",
		"wa groups",
	),
	"message": ("message", "text", "body", "content"),
	"flow": ("flow", "glific flow", "flow name", "flow id"),
}


def normalize_header(value: Any) -> str:
	text = str(value or "").strip().lower()
	text = re.sub(r"\s+", " ", text)
	return text


def map_headers(header_row: list[Any]) -> dict[str, int]:
	mapping: dict[str, int] = {}
	for idx, cell in enumerate(header_row):
		norm = normalize_header(cell)
		if not norm:
			continue
		for key, aliases in HEADER_ALIASES.items():
			if norm in aliases or norm.replace("/", " ") in aliases:
				mapping[key] = idx
				break
	return mapping


def split_groups(raw: Any) -> list[str]:
	if raw is None:
		return []
	text = str(raw).strip()
	if not text:
		return []
	parts = re.split(r"[,;|\n]+", text)
	return [p.strip() for p in parts if p.strip()]


def combine_schedule_local(row_date, row_time, tz_name: str) -> datetime:
	from datetime import date as date_cls

	if hasattr(row_date, "year"):
		d = row_date
	else:
		d = date_cls.fromisoformat(str(row_date)[:10])
	if row_time:
		if hasattr(row_time, "hour"):
			t = row_time
		else:
			parts = str(row_time).split(":")
			t = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
	else:
		t = time(9, 0)
	naive = datetime.combine(d, t)
	try:
		from zoneinfo import ZoneInfo

		tz = ZoneInfo(tz_name or "Asia/Kolkata")
		return naive.replace(tzinfo=tz).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
	except Exception:
		return naive
