"""Peer-history enrichment and walk-forward check for the dispatch watchlist.

Policy: a row whose peer group has fewer than MIN_PEERS distinct prior order
lines (or whose lead day is outside 0-6) gets peer=None and is ranked by due
date alone, after all rows that have a peer estimate.
"""

from collections import defaultdict
from datetime import date, timedelta

MIN_PEERS, TOP, WINDOW, MIN_KNOWN, MAX_DAYS = 20, 10, 90, 10, 30
ELIGIBLE = ("On time", "Missed")


def _d(value):
	return date.fromisoformat(value) if value else None


def _key(item):
	days = item["days"]
	if not 0 <= days <= 6:
		return None
	return (item["company"], days, item["band"])


def _index(observations, day):
	"""Group maps from outcomes resolved strictly before `day`, last 90 days.

	One vote per order line at each lead time. The latest revised snapshot wins.
	"""
	low, latest = day - timedelta(WINDOW), {}
	for o in observations:
		resolved = _d(o["resolved_on"])
		if o["outcome"] not in ELIGIBLE or resolved is None:
			continue
		if not low <= resolved < day or _d(o["observed_on"]) >= day:
			continue
		rank = (o["observed_on"], o["resolved_on"], o["due_date"])
		ident = (o["company"], o["order"], o["line"], o["days"])
		if ident not in latest or rank > latest[ident][0]:
			latest[ident] = (rank, o)
	groups, by_order = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
	for _, o in latest.values():
		key = _key(o)
		if key is None:
			continue
		missed = o["outcome"] == "Missed"
		for table, k in ((groups, key), (by_order, (*key, o["order"]))):
			table[k][0] += 1
			table[k][1] += missed
	return groups, by_order


def _peer(item, index):
	groups, by_order = index
	key = _key(item)
	if key is None or key not in groups:
		return None
	own = by_order.get((*key, item["order"]), (0, 0))
	total, missed = groups[key][0] - own[0], groups[key][1] - own[1]
	return {"missed": missed, "total": total} if total >= MIN_PEERS else None


def _queue_order(row, peer):
	# Overdue orders have already missed the date and stay above forward-looking comparisons.
	group = 0 if row["days"] < 0 else 1 if peer else 2
	return (group, -peer["missed"] / peer["total"] if peer else 0, row["due_date"], row["order"], row["line"])


def _evaluate(observations, day):
	start = day - timedelta(days=MAX_DAYS)
	groups = defaultdict(dict)
	for o in observations:
		when = _d(o["observed_on"])
		if not start <= when < day:
			continue
		# Keep the first promise actually observed for this line on that day.
		group = groups[(when, o["company"])]
		line = (o["order"], o["line"])
		first = group.get(line)
		if first is None or o.get("captured_at", o["observed_on"]) < first.get(
			"captured_at", first["observed_on"]
		):
			group[line] = o
	dates = sorted({when for when, _ in groups})
	result = {"days": 0, "reviewed": 0, "peer_hits": 0, "due_hits": 0}
	for observed in dates[-MAX_DAYS:]:
		index = None
		for (when, _company), lines in groups.items():
			if when != observed:
				continue
			snaps = list(lines.values())
			# Omitting an excluded line after seeing its outcome would change the historical queue.
			if len(snaps) <= TOP or any(
				o["outcome"] not in ELIGIBLE or not o["resolved_on"] or _d(o["resolved_on"]) >= day
				for o in snaps
			):
				continue
			base = sorted(snaps, key=lambda o: (o["due_date"], o["order"], o["line"]))
			if index is None:
				index = _index(observations, observed)
			peers = {id(o): _peer(o, index) for o in base}
			if sum(p is not None for p in peers.values()) < MIN_KNOWN:
				continue

			ranked = sorted(base, key=lambda o: _queue_order(o, peers[id(o)]))
			result["days"] += 1
			result["reviewed"] += TOP
			result["peer_hits"] += sum(o["outcome"] == "Missed" for o in ranked[:TOP])
			result["due_hits"] += sum(o["outcome"] == "Missed" for o in base[:TOP])
	return result


def enrich(rows, observations, day):
	"""Attach earlier comparisons and daily observations, then replay the ranking."""
	index = _index(observations, day)
	tracked = {(r["order"], r["line"], r["due_date"]): r for r in rows}
	for o in observations:
		row = tracked.get((o["order"], o["line"], o["due_date"]))
		if row and o.get("uom") == row.get("uom") and o.get("ordered") == row.get("qty") and "delivered" in o:
			row.setdefault("trend", []).append({"date": o["observed_on"], "delivered": o["delivered"]})
	for row in rows:
		row["peer"] = _peer(row, index)
		if row.get("trend"):
			row["trend"].sort(key=lambda point: point["date"])
	for place, row in enumerate(sorted(rows, key=lambda r: _queue_order(r, r["peer"]))):
		row["history_rank"] = place
	return _evaluate(observations, day)
