import unittest
from datetime import date

from .comparison import enrich

DAY = date(2024, 2, 10)


def obs(
	order,
	line=1,
	outcome="On time",
	observed="2024-01-05",
	resolved="2024-01-10",
	due="2024-01-08",
	days=1,
	band="hi",
	company="A",
):
	return {
		"order": order,
		"line": line,
		"company": company,
		"item": "X",
		"days": days,
		"band": band,
		"observed_on": observed,
		"resolved_on": resolved,
		"outcome": outcome,
		"due_date": due,
	}


def row(order="CAND", days=1):
	return {"order": order, "line": 1, "company": "A", "days": days, "band": "hi", "due_date": str(DAY)}


def history(n, **kw):
	return [obs(f"H{i}", **kw) for i in range(n)]


class PeerTests(unittest.TestCase):
	def peer(self, observations, **kw):
		rows = [row(**kw)]
		enrich(rows, observations, DAY)
		return rows[0]["peer"]

	def test_threshold(self):
		self.assertIsNone(self.peer(history(19)))
		self.assertEqual(self.peer(history(20)), {"missed": 0, "total": 20})

	def test_unknown_lead_day_is_none(self):
		self.assertIsNone(self.peer(history(20, days=9), days=9))

	def test_no_leakage_incl_same_day(self):
		base = history(19)
		same_day = obs("S", resolved="2024-02-10")
		later = obs("L", resolved="2024-02-11")
		future_obs = obs("F", observed="2024-02-10", resolved="2024-02-10")
		self.assertIsNone(self.peer([*base, same_day, later, future_obs]))
		self.assertEqual(self.peer([*base, obs("Y", resolved="2024-02-09")])["total"], 20)

	def test_window_and_eligibility(self):
		old = obs("O", resolved="2023-11-01")
		skipped = [obs("P", outcome="Pending", resolved=None), obs("E", outcome="Excluded")]
		self.assertIsNone(self.peer([*history(19), old, *skipped]))

	def test_dedup_revisions(self):
		rev = [obs(f"H{i}", observed="2024-01-06", due="2024-01-09") for i in range(19)]
		self.assertIsNone(self.peer(history(19) + rev))
		latest = obs("H0", outcome="Missed", observed="2024-01-07")
		got = self.peer([*history(20), latest])
		self.assertEqual(got, {"missed": 1, "total": 20})

	def test_own_order_excluded(self):
		own = [obs("CAND", line=i) for i in range(5)]
		self.assertIsNone(self.peer(history(19) + own))
		self.assertEqual(self.peer(history(20) + own)["total"], 20)

	def test_distinct_lead_times_reuse_the_same_resolved_lines(self):
		observations = history(20, days=2) + history(20, days=0, observed="2024-01-07")
		for days in (0, 2):
			self.assertEqual(self.peer(observations, days=days)["total"], 20)

	def test_comparable_keys(self):
		other = history(20, company="B") + history(20, band="lo") + history(20, days=2)
		self.assertIsNone(self.peer(other))

	def test_live_history_ranking_keeps_overdue_and_ranks_unknowns_last(self):
		rows = [row("unknown", 6), row("overdue", -1), row("evidence", 1), row("higher", 3)]
		enrich(rows, history(20, days=1) + history(20, days=3, outcome="Missed"), DAY)
		self.assertEqual([r["history_rank"] for r in rows], [3, 0, 2, 1])


class DiagnosticTests(unittest.TestCase):
	def data(self, n_hist=20, n_each=6):
		hist = [obs(f"X{i}", outcome="Missed", days=1) for i in range(n_hist)]
		hist += [obs(f"Y{i}", days=3) for i in range(n_hist)]
		cand = []
		for i in range(n_each):
			cand.append(
				obs(
					f"CY{i}",
					outcome="On time",
					observed="2024-02-01",
					resolved="2024-02-02",
					due="2024-02-05",
					days=3,
				)
			)
			cand.append(
				obs(
					f"CX{i}",
					outcome="Missed",
					observed="2024-02-01",
					resolved="2024-02-02",
					due="2024-02-09",
					days=1,
				)
			)
		return hist + cand

	def test_known_top_ten(self):
		# Due-date order picks 6 on-time + 4 missed; peer order picks 6 + 4 the other way.
		self.assertEqual(
			enrich([], self.data(), DAY), {"days": 1, "reviewed": 10, "peer_hits": 6, "due_hits": 4}
		)

	def test_insufficient_history_skips(self):
		self.assertEqual(enrich([], self.data(n_hist=19), DAY)["days"], 0)

	def test_needs_more_than_ten_lines(self):
		self.assertEqual(enrich([], self.data(n_each=5), DAY)["days"], 0)

	def test_immature_day_skipped(self):
		data = self.data()
		data.append(obs("P", outcome="Pending", observed="2024-02-01", resolved=None))
		self.assertEqual(enrich([], data, DAY)["days"], 0)
		late = self.data()
		late[-1]["resolved_on"] = "2024-02-10"  # resolved on `day`: not yet safe
		self.assertEqual(enrich([], late, DAY)["days"], 0)

	def test_duplicate_snapshots_do_not_inflate(self):
		data = self.data()
		data += [dict(o, due_date="2024-02-06") for o in data if o["observed_on"] == "2024-02-01"]
		self.assertEqual(enrich([], data, DAY)["reviewed"], 10)

	def test_excluded_line_skips_the_whole_queue(self):
		data = self.data()
		data.append(obs("A", outcome="Excluded", observed="2024-02-01", resolved="2024-02-08"))
		self.assertEqual(enrich([], data, DAY)["days"], 0)


if __name__ == "__main__":
	unittest.main()
