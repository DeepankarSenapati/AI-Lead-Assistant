frappe.pages["dispatch-watchlist"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dispatch Watchlist"),
		single_column: true,
	});
	wrapper.dw = new DispatchWatchlist(wrapper, page);
};

frappe.pages["dispatch-watchlist"].on_page_show = function (wrapper) {
	if (wrapper.dw) wrapper.dw.on_show();
};

class DispatchWatchlist {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.page = page;
		this.mode = "live";
		this.tab = "worklist";
		this.day = null; // null all, "overdue", or ISO date
		this.search = "";
		this.sort = "due";
		this.short_only = false;
		this.selected = null;
		this.whatif = {};
		this.req = 0;
		this.state = "pending"; // pending, ready, error
		this.error = "";
		this.data = null;
		this.build();
		this.page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
		this.on_event = () => {
			if (this.mode === "live" && this.wrapper.offsetParent !== null) this.load(true);
		};
		$(document).off("ai-feature-assignments-refresh.dw").on("ai-feature-assignments-refresh.dw", this.on_event);
	}

	on_show() {
		const view = new URLSearchParams(window.location.search).get("view");
		this.mode = view === "sample" ? "sample" : "live";
		this.sync_mode();
		this.load();
	}

	// DOM helpers
	el(tag, cls, text) {
		const e = document.createElement(tag);
		if (cls) e.className = cls;
		if (text !== undefined && text !== null) e.textContent = text;
		return e;
	}

	build() {
		const main = this.page.main[0];
		main.textContent = "";
		const root = (this.root = this.el("div", "dw-root"));
		main.appendChild(root);

		const bar = this.el("div", "dw-bar");
		const seg = this.el("div", "dw-seg");
		seg.setAttribute("role", "group");
		seg.setAttribute("aria-label", __("Data source"));
		this.mode_btns = {};
		[["live", __("Live")], ["sample", __("Sample data")]].forEach(([k, label]) => {
			const b = this.el("button", "dw-seg-btn", label);
			b.type = "button";
			b.addEventListener("click", () => this.set_mode(k));
			this.mode_btns[k] = b;
			seg.appendChild(b);
		});
		bar.appendChild(seg);

		const tabs = this.el("div", "dw-tabs");
		tabs.setAttribute("role", "tablist");
		this.tab_btns = {};
		[["worklist", __("Worklist")], ["history", __("History")]].forEach(([k, label]) => {
			const b = this.el("button", "dw-tab", label);
			b.type = "button";
			b.setAttribute("role", "tab");
			b.addEventListener("click", () => {
				this.tab = k;
				this.render();
			});
			this.tab_btns[k] = b;
			tabs.appendChild(b);
		});
		bar.appendChild(tabs);
		this.asof = this.el("div", "dw-asof");
		bar.appendChild(this.asof);
		root.appendChild(bar);

		this.banner = this.el("div", "dw-banner");
		this.banner.hidden = true;
		root.appendChild(this.banner);

		this.body = this.el("div", "dw-body");
		this.body.setAttribute("aria-live", "polite");
		root.appendChild(this.body);
		this.sync_mode();
	}

	sync_mode() {
		Object.keys(this.mode_btns).forEach((k) => {
			this.mode_btns[k].setAttribute("aria-pressed", String(this.mode === k));
			this.mode_btns[k].classList.toggle("is-active", this.mode === k);
		});
		this.root.classList.toggle("dw-is-sample", this.mode === "sample");
	}

	set_mode(m) {
		if (this.mode === m) return;
		this.mode = m;
		this.whatif = {};
		this.search = "";
		this.sort = "due";
		this.selected = null;
		this.day = null;
		this.short_only = false;
		this.sync_mode();
		const url = new URL(window.location.href);
		if (m === "sample") url.searchParams.set("view", "sample");
		else url.searchParams.delete("view");
		window.history.replaceState(null, "", url.pathname + url.search + url.hash);
		this.load();
	}

	load(silent = false) {
		const id = ++this.req;
		if (!silent || this.state !== "ready") {
			this.state = "pending";
			this.render();
		}
		frappe.call({
			method: "ai_lead_assistant.dispatch.api.get_watchlist",
			type: "GET",
			args: { sample: this.mode === "sample" ? 1 : 0 },
			callback: (r) => {
				if (id !== this.req) return;
				const m = r && r.message;
				if (!m || typeof m !== "object" || !Array.isArray(m.rows)) {
					this.fail(__("The server returned an unexpected response."));
					return;
				}
				if (silent && this.state === "ready" && JSON.stringify(this.data) === JSON.stringify(m)) return;
				this.data = m;
				this.state = "ready";
				this.render();
			},
			error: () => {
				if (id !== this.req) return;
				this.fail(__("The watchlist could not be loaded."));
			},
		});
	}

	fail(msg) {
		this.state = "error";
		this.error = msg;
		this.render();
	}

	// date helpers, all relative to server date
	parse(iso) {
		const p = String(iso).split("-").map(Number);
		return Date.UTC(p[0], p[1] - 1, p[2]);
	}
	add_days(iso, n) {
		const d = new Date(this.parse(iso) + n * 864e5);
		return d.toISOString().slice(0, 10);
	}
	fmt(iso, options = { weekday: "short", day: "numeric", month: "short" }) {
		return new Date(this.parse(iso)).toLocaleDateString(frappe.boot.lang?.replaceAll("_", "-") || undefined, {
			timeZone: "UTC",
			...options,
		});
	}
	rel(days) {
		if (days === 0) return __("Today");
		if (days === 1) return __("Tomorrow");
		if (days === -1) return __("1 day overdue");
		if (days < 0) return __("{0} days overdue", [-days]);
		return __("In {0} days", [days]);
	}
	key(r) {
		return JSON.stringify([r.order, r.line]);
	}

	render() {
		const sample = this.mode === "sample";
		this.banner.hidden = !sample;
		this.banner.textContent = "";
		if (sample) {
			this.banner.appendChild(this.el("strong", "dw-banner-tag", __("Sample data")));
			this.banner.appendChild(
				this.el("span", "", __("Explore a simulated dispatch week. Switch to Live for your ERPNext orders."))
			);
		}
		Object.keys(this.tab_btns).forEach((k) => {
			this.tab_btns[k].setAttribute("aria-selected", String(this.tab === k));
			this.tab_btns[k].classList.toggle("is-active", this.tab === k);
			this.tab_btns[k].tabIndex = 0;
		});
		this.asof.textContent =
			this.state === "ready" && this.data && this.data.as_of ? __("As of {0}", [this.fmt(this.data.as_of)]) : "";

		this.body.textContent = "";
		this.body.setAttribute("aria-busy", String(this.state === "pending"));
		if (this.state === "pending") return this.render_pending();
		if (this.state === "error") return this.render_error();
		const d = this.data;
		if (!d.enabled && !sample) return this.render_disabled();
		if (d.accessible === false && !sample) {
			this.body.appendChild(this.el("p", "dw-state", __("Live dispatch requires read access to Sales Order quantities, units and promised dates.")));
			return;
		}
		if (this.tab === "history") return this.render_history();
		this.render_worklist();
	}

	render_pending() {
		const w = this.el("div", "dw-skel");
		w.setAttribute("role", "status");
		w.appendChild(this.el("span", "dw-sr", __("Loading watchlist")));
		for (let i = 0; i < 5; i++) w.appendChild(this.el("div", "dw-skel-row"));
		this.body.appendChild(w);
	}

	render_error() {
		const box = this.el("div", "dw-state");
		box.setAttribute("role", "alert");
		box.appendChild(this.el("h3", "dw-state-title", __("Could not load")));
		box.appendChild(this.el("p", "dw-muted", this.error));
		const b = this.el("button", "btn btn-primary btn-sm", __("Retry"));
		b.type = "button";
		b.addEventListener("click", () => this.load());
		box.appendChild(b);
		this.body.appendChild(box);
	}

	render_disabled() {
		const box = this.el("div", "dw-state");
		box.appendChild(this.el("h3", "dw-state-title", __("Dispatch Watchlist is not assigned")));
		box.appendChild(this.el("p", "dw-muted", __("A System Manager can enable Dispatch Watchlist for Selling or Sales Order in the AI Feature Dashboard.")));
		const row = this.el("div", "dw-actions");
		const a = this.el("button", "btn btn-primary btn-sm", __("Refresh"));
		a.type = "button";
		a.addEventListener("click", () => this.load());
		const s = this.el("button", "btn btn-default btn-sm", __("View sample data"));
		s.type = "button";
		s.addEventListener("click", () => this.set_mode("sample"));
		row.append(a, s);
		box.appendChild(row);
		this.body.appendChild(box);
	}

	render_worklist() {
		const d = this.data;
		const rows = d.rows;
		if (!rows.length) {
			const box = this.el("div", "dw-state");
			box.appendChild(this.el("h3", "dw-state-title", d.truncated ? __("No open lines in the displayed selection") : __("No open lines to watch")));
			box.appendChild(this.el("p", "dw-muted", d.truncated
				? __("The first 500 matching orders contained no open stock-item lines. Other orders may still be due.")
				: __("No visible stock-item lines are due in the next seven calendar days or overdue in the last 30 days.")));
			if (this.mode === "live") {
				const b = this.el("button", "btn btn-primary btn-sm", __("Open sample data"));
				b.type = "button";
				b.addEventListener("click", () => this.set_mode("sample"));
				box.appendChild(b);
			}
			this.body.appendChild(box);
			return;
		}

		const today = d.as_of;
		const days = [];
		for (let i = 0; i < 7; i++) days.push(this.add_days(today, i));
		const count = { overdue: 0 };
		days.forEach((x) => (count[x] = 0));
		rows.forEach((r) => {
			if (r.due_date < today || r.priority === "Overdue") count.overdue++;
			else if (count[r.due_date] !== undefined) count[r.due_date]++;
		});

		const heading = this.el("div", "dw-week-head");
		heading.append(this.el("h3", "", __("Dispatch horizon")), this.el("span", "dw-muted", __("{0} – {1}", [this.fmt(today), this.fmt(days[6])])));
		this.body.appendChild(heading);
		const strip = this.el("div", "dw-strip");
		strip.setAttribute("role", "group");
		strip.setAttribute("aria-label", __("Filter by due day"));
		const mk = (k, label, sub, n, cls) => {
			const b = this.el("button", "dw-day " + (cls || ""));
			b.type = "button";
			b.setAttribute("aria-pressed", String(this.day === k));
			b.classList.toggle("is-active", this.day === k);
			b.appendChild(this.el("span", "dw-day-label", label));
			b.appendChild(this.el("span", "dw-day-count", String(n)));
			b.appendChild(this.el("span", "dw-day-sub", sub));
			const track = this.el("span", "dw-day-track");
			const fill = this.el("span", "dw-day-fill");
			fill.style.width = String((n / Math.max(1, ...Object.values(count))) * 100) + "%";
			track.appendChild(fill);
			b.appendChild(track);
			b.addEventListener("click", () => {
				this.day = this.day === k ? null : k;
				this.render();
			});
			strip.appendChild(b);
		};
		mk("overdue", __("Overdue"), __("last 30 days"), count.overdue, "dw-day-overdue");
		days.forEach((x, i) => {
			mk(x, i === 0 ? __("Today") : this.fmt(x, {weekday: "short"}), this.fmt(x, {day: "numeric", month: "short"}), count[x]);
		});
		this.body.appendChild(strip);

		const tools = this.el("div", "dw-tools");
		const lab = this.el("label", "dw-sr", __("Search lines"));
		lab.setAttribute("for", "dw-search");
		const inp = this.el("input", "form-control input-sm dw-search");
		inp.id = "dw-search";
		inp.type = "search";
		inp.placeholder = __("Search order, item, customer, warehouse");
		inp.value = this.search;
		tools.append(lab, inp);
		const gap = this.el("input");
		if (rows.some((r) => r.stock)) {
			gap.type = "checkbox";
			gap.checked = this.short_only;
			const label = this.el("label", "dw-gap-toggle");
			label.append(gap, this.el("span", "", __("Stock gaps only")));
			tools.appendChild(label);
		} else {
			this.short_only = false;
		}
		const sort = this.el("select", "form-control input-sm dw-sort");
		if (rows.some((r) => r.peer)) {
			const label = this.el("label", "dw-sort-label", __("Sort by"));
			label.htmlFor = sort.id = "dw-sort";
			for (const [value, title] of [["due", __("Promised date")], ["history", __("Comparable miss rate")]]) {
				const option = this.el("option", "", title);
				option.value = value;
				sort.appendChild(option);
			}
			sort.value = this.sort;
			tools.append(label, sort);
		}
		const meta = this.el("div", "dw-meta");
		tools.appendChild(meta);
		this.body.appendChild(tools);

		if (d.truncated) {
			const t = this.el("div", "dw-note", __("This view checks up to 500 matching orders and displays up to 300 lines. Counts, sorting and filters apply to this selection."));
			this.body.appendChild(t);
		}

		const grid = this.el("div", "dw-grid");
		const list = this.el("ul", "dw-list");
		list.setAttribute("role", "listbox");
		list.setAttribute("aria-label", __("Open order lines"));
		const detail = this.el("section", "dw-detail");
		detail.setAttribute("aria-label", __("Line detail"));
		grid.append(list, detail);
		this.body.appendChild(grid);

		const apply = () => {
			const q = this.search.trim().toLowerCase();
			const vis = rows.filter((r) => {
				if (this.short_only && !r.stock?.short) return false;
				if (this.day === "overdue" && !(r.due_date < today || r.priority === "Overdue")) return false;
				if (this.day && this.day !== "overdue" && r.due_date !== this.day) return false;
				if (!q) return true;
				return [r.order, r.item, r.customer, r.warehouse, r.reason].some((v) => String(v || "").toLowerCase().includes(q));
			});
			if (this.sort === "history") vis.sort((a, b) => a.history_rank - b.history_rank);
			meta.textContent = __("{0} of {1} lines", [vis.length, rows.length]);
			if (!vis.some((r) => this.key(r) === this.selected)) {
				const first = this.mode === "sample" ? vis.find((r) => r.days === 0) || vis[0] : vis[0];
				this.selected = first ? this.key(first) : null;
			}
			this.fill_list(list, vis, detail);
		};
		inp.addEventListener("input", () => {
			this.search = inp.value;
			apply();
		});
		sort.addEventListener("change", () => {
			this.sort = sort.value;
			apply();
		});
		gap.addEventListener("change", () => {
			this.short_only = gap.checked;
			apply();
		});
		apply();
	}

	fill_list(list, vis, detail) {
		list.textContent = "";
		if (!vis.length) {
			const li = this.el("li", "dw-empty", __("No lines match."));
			list.appendChild(li);
		}
		const items = [];
		vis.forEach((r) => {
			const k = this.key(r);
			const li = this.el("li", "dw-row");
			li.setAttribute("role", "option");
			li.tabIndex = k === this.selected ? 0 : -1;
			li.setAttribute("aria-selected", String(k === this.selected));
			li.classList.toggle("is-selected", k === this.selected);
			li.dataset.k = k;
			li.dataset.p = this.prio_class(r.priority);
			const main = this.el("div", "dw-row-main");
			main.appendChild(this.el("div", "dw-row-item", r.item));
			main.appendChild(this.el("div", "dw-row-sub", r.customer + " · " + r.order));
			const side = this.el("div", "dw-row-side");
			side.appendChild(this.el("span", "dw-pill dw-p-" + this.prio_class(r.priority), r.priority));
			side.appendChild(this.el("span", "dw-row-due", this.rel(r.days)));
			side.appendChild(this.el("span", "dw-row-rem", __("{0} {1} open", [r.remaining, r.uom])));
			li.append(main, side);
			const pick = () => {
				this.selected = k;
				items.forEach((x) => {
					const on = x.dataset.k === k;
					x.classList.toggle("is-selected", on);
					x.setAttribute("aria-selected", String(on));
					x.tabIndex = on ? 0 : -1;
				});
				this.fill_detail(detail, r);
			};
			li.addEventListener("click", (e) => {
				pick();
				if (e.detail && window.matchMedia("(max-width: 900px)").matches) detail.scrollIntoView({block: "start"});
			});
			li.addEventListener("keydown", (e) => {
				const i = items.indexOf(li);
				let n = null;
				if (e.key === "ArrowDown") n = items[i + 1];
				else if (e.key === "ArrowUp") n = items[i - 1];
				else if (e.key === "Home") n = items[0];
				else if (e.key === "End") n = items[items.length - 1];
				else if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					pick();
					return;
				}
				if (n) {
					e.preventDefault();
					n.focus();
					n.click();
					n.focus();
				}
			});
			items.push(li);
			list.appendChild(li);
		});
		const sel = vis.find((r) => this.key(r) === this.selected);
		this.fill_detail(detail, sel);
	}

	prio_class(p) {
		return { Overdue: "overdue", "Due today": "today", "Due soon": "soon", Upcoming: "upcoming" }[p] || "upcoming";
	}

	fill_detail(box, r) {
		box.textContent = "";
		if (!r) {
			box.appendChild(this.el("p", "dw-muted", __("Select a line to see details.")));
			return;
		}
		const head = this.el("div", "dw-detail-head");
		head.appendChild(this.el("h3", "dw-detail-title", r.item));
		head.appendChild(this.el("span", "dw-pill dw-p-" + this.prio_class(r.priority), r.priority));
		box.appendChild(head);
		const back = this.el("button", "btn btn-default btn-xs dw-back", __("Back to lines"));
		back.type = "button";
		back.addEventListener("click", () => {
			const selected = this.body.querySelector('.dw-row[aria-selected="true"]');
			selected?.focus({preventScroll:true});
			selected?.scrollIntoView({block:"center"});
		});
		head.appendChild(back);

		const dl = this.el("dl", "dw-dl");
		const add = (t, v) => {
			dl.appendChild(this.el("dt", "", t));
			dl.appendChild(this.el("dd", "", v));
		};
		const progress = this.el("div", "dw-progress");
		progress.appendChild(this.el("strong", "", __("{0} {1} to dispatch", [r.remaining, r.uom])));
		const track = this.el("div", "dw-progress-track");
		const fill = this.el("div", "dw-progress-fill");
		fill.style.width = String(Math.min(100, r.delivered / r.qty * 100)) + "%";
		track.appendChild(fill);
		progress.append(track, this.el("small", "dw-muted", __("{0} of {1} {2} already dispatched", [r.delivered, r.qty, r.uom])));
		box.appendChild(progress);
		add(__("Customer"), r.customer);
		add(__("Warehouse"), r.warehouse);
		add(__("Order line delivery date"), this.fmt(r.due_date) + " · " + this.rel(r.days));
		box.appendChild(dl);

		if (r.stock) {
			const stock = r.stock;
			const check = this.el("div", "dw-stock" + (stock.short ? " dw-stock-short" : ""));
			check.appendChild(this.el("strong", "", stock.short
				? __("Stock gap of {0} {1}", [stock.short, stock.uom]) : __("On-hand stock covers this line")));
			check.appendChild(this.el("small", "", __("{0} {1} on hand here · {2} needed for this line. Other orders may claim this stock.", [stock.on_hand, stock.uom, stock.needed])));
			box.appendChild(check);
		}

		const why = this.el("div", "dw-why");
		if (r.days >= 0) {
			why.appendChild(this.el("h4", "dw-sub", __("Comparable promises")));
			why.appendChild(this.el("p", "", r.peer
				? __("{0} of {1} comparable lines you can access in this company missed the posted dispatch deadline. They had the same time left and similar progress.", [r.peer.missed, r.peer.total])
				: __("A comparison appears after 20 similar lines have known outcomes.")));
		}
		box.appendChild(why);

		if (r.trend?.length) {
			const log = this.el("details", "dw-trend");
			const latest = r.trend[r.trend.length - 1];
			let same = 1;
			for (let i = r.trend.length - 2; i >= 0; i--) {
				if (r.trend[i].delivered !== latest.delivered || this.add_days(r.trend[i].date, 1) !== r.trend[i + 1].date) break;
				same++;
			}
			const title = same > 1 && latest.delivered === r.delivered
				? __("Progress · {0} {1} at the last {2} daily checks", [latest.delivered, r.uom, same])
				: __("Daily dispatch progress");
			log.appendChild(this.el("summary", "", title));
			const chart = this.el("ol", "dw-observations");
			for (const point of r.trend) {
				const bar = this.el("li", "");
				const track = this.el("span", "dw-progress-track");
				const fill = this.el("span", "dw-progress-fill");
				fill.style.width = Math.min(100, 100 * point.delivered / r.qty) + "%";
				track.appendChild(fill);
				bar.append(this.el("span", "", this.fmt(point.date)), track, this.el("span", "", __("{0} {1} dispatched", [point.delivered, r.uom])));
				chart.appendChild(bar);
			}
			log.appendChild(chart);
			box.appendChild(log);
		}

		if (this.mode === "live") {
			const p = this.el("p", "dw-link");
			const a = this.el("a", "", __("Open {0}", [r.order]));
			a.href = frappe.utils.get_form_link("Sales Order", r.order);
			a.addEventListener("click", (e) => {
				if (e.metaKey || e.ctrlKey || e.shiftKey) return;
				e.preventDefault();
				frappe.set_route("Form", "Sales Order", r.order);
			});
			p.appendChild(a);
			box.appendChild(p);
		}

		const wi = this.el("div", "dw-whatif");
		wi.appendChild(this.el("h4", "dw-sub", __("What if")));
		if (r.days < 0 || r.priority === "Overdue") {
			return;
		} else {
			const k = this.key(r);
			const id = "dw-wi-" + this.req;
			const lab = this.el("label", "dw-wi-label", __("Additional {0} dispatched by the promise date", [r.uom]));
			lab.setAttribute("for", id);
			const inp = this.el("input", "form-control input-sm dw-wi-input");
			inp.id = id;
			inp.type = "number";
			inp.min = "0";
			inp.max = String(r.remaining);
			inp.step = "any";
			inp.inputMode = "decimal";
			inp.value = this.whatif[k] || "";
			const out = this.el("p", "dw-wi-out");
			out.setAttribute("aria-live", "polite");
			const needed = this.el("p", "dw-wi-stock");
			const calc = () => {
				this.whatif[k] = inp.value;
				needed.textContent = "";
				const n = inp.value === "" ? 0 : inp.valueAsNumber;
				if (!Number.isFinite(n) || n < 0 || n > r.remaining || inp.validity.badInput) {
					out.textContent = __("Enter an amount from 0 to {0}.", [r.remaining]);
					return;
				}
				const open = Number((r.remaining - n).toFixed(r.precision));
				out.textContent = open ? __("{0} {1} would still be open at the deadline.", [open, r.uom]) : __("The full quantity would be dispatched by the deadline.");
				if (r.stock) {
					const gap = Number(Math.max(0, n * r.factor - Math.max(0, r.stock.on_hand)).toFixed(9));
					if (gap) needed.textContent = __("This scenario needs {0} more {1} than are on hand here today.", [gap, r.stock.uom]);
				}
			};
			inp.addEventListener("input", calc);
			const controls = this.el("div", "dw-scenario-controls");
			const all = this.el("button", "btn btn-default btn-xs", __("Try full dispatch"));
			all.type = "button";
			all.addEventListener("click", () => { inp.value = String(r.remaining); calc(); });
			controls.append(inp, all);
			calc();
			wi.append(lab, controls, out, needed);
		}
		box.appendChild(wi);
	}

	render_history() {
		const h = this.data.history || { observed: 0, on_time: 0, missed: 0, excluded: 0, awaiting: 0, latest: [] };
		const sample = this.mode === "sample";
		const wrap = this.el("div", "dw-hist");
		const head = this.el("div", "dw-hist-head");
		head.appendChild(this.el("h3", "dw-state-title", __("Observed outcomes")));
		if (sample) head.appendChild(this.el("span", "dw-pill dw-p-sample", __("Demo history")));
		wrap.appendChild(head);
		wrap.appendChild(
			this.el("p", "dw-muted", __("Each visible line and promised date counts once. We use the Sales Order line’s Delivery Date as its dispatch deadline and allow one full calendar day for posting. Covers the past 90 days and the current dispatch week."))
		);

		const cards = this.el("div", "dw-cards");
		[
			[__("Observed"), h.observed, ""],
			[__("On time"), h.on_time, "ok"],
			[__("Missed"), h.missed, "bad"],
			[__("Excluded"), h.excluded, "mute"],
			[__("Awaiting"), h.awaiting, "mute"],
		].forEach(([t, n, c]) => {
			const card = this.el("div", "dw-card " + (c ? "dw-card-" + c : ""));
			card.appendChild(this.el("div", "dw-card-n", String(n)));
			card.appendChild(this.el("div", "dw-card-t", t));
			cards.appendChild(card);
		});
		wrap.appendChild(cards);

		const cmp = h.comparison || {};
		const comparison = this.el("section", "dw-benchmark");
		comparison.appendChild(this.el("h4", "", __("Which ten lines would have caught more misses?")));
		if (cmp.days) {
			comparison.appendChild(this.el("p", "dw-muted", __("Replay of {0} completed company queues in the last 30 days. Both methods selected ten lines per queue using only earlier outcomes.", [cmp.days])));
			for (const [title, hits] of [[__("By comparable history"), cmp.peer_hits], [__("By earliest due date"), cmp.due_hits]]) {
				const bar = this.el("div", "dw-bench-row");
				const barTrack = this.el("span", "dw-progress-track");
				const barFill = this.el("span", "dw-progress-fill");
				barFill.style.width = String(100 * hits / cmp.reviewed) + "%";
				barTrack.appendChild(barFill);
				bar.append(this.el("span", "", title), barTrack, this.el("strong", "", __("{0} / {1}", [hits, cmp.reviewed])));
				comparison.appendChild(bar);
			}
			comparison.appendChild(this.el("small", "dw-muted", __("Counts are misses among the ten selections per queue. A line can be selected on more than one day.")));
		} else {
			comparison.appendChild(this.el("p", "dw-muted", __("A daily queue qualifies when every outcome is known, it has more than ten lines, and at least ten have comparable history.")));
		}
		wrap.appendChild(comparison);
		const latest = h.latest || [];
		if (!latest.length) {
			wrap.appendChild(this.el("p", "dw-muted", __("No resolved outcomes yet.")));
		} else {
			const tbl = this.el("div", "dw-table");
			tbl.setAttribute("role", "table");
			tbl.setAttribute("aria-label", __("Latest outcomes"));
			const hr = this.el("div", "dw-tr dw-th");
			hr.setAttribute("role", "row");
			[__("Order"), __("Item"), __("Due"), __("Outcome"), __("Reason")].forEach((t) => {
				const c = this.el("div", "dw-td", t);
				c.setAttribute("role", "columnheader");
				hr.appendChild(c);
			});
			tbl.appendChild(hr);
			latest.forEach((o) => {
				const tr = this.el("div", "dw-tr");
				tr.setAttribute("role", "row");
				const cells = [o.order, o.item, this.fmt(o.due_date), o.outcome, o.reason || ""];
				cells.forEach((t, i) => {
					const c = this.el("div", "dw-td", t);
					c.setAttribute("role", "cell");
					if (i === 3) {
						c.textContent = "";
						const cls = o.outcome === "On time" ? "ok" : o.outcome === "Missed" ? "bad" : "mute";
						c.appendChild(this.el("span", "dw-pill dw-p-" + cls, t));
					}
					tr.appendChild(c);
				});
				tbl.appendChild(tr);
			});
			wrap.appendChild(tbl);
		}
		this.body.appendChild(wrap);
	}
}
