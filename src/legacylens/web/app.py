"""Flask app for the LegacyLens web dashboard."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request


def create_app():
    app = Flask(__name__)

    data_file = Path.home() / ".legacylens" / "function_data.json"
    repo_root_file = Path.home() / ".legacylens" / "repo_root.txt"

    # ── helpers ──────────────────────────────────────────────────────────────

    def _load_functions():
        if data_file.exists():
            with open(data_file) as f:
                return json.load(f)
        return []

    def _get_repo_root():
        if repo_root_file.exists():
            return Path(repo_root_file.read_text().strip())
        return None

    def _risk_band(v):
        if v is None:
            return "unknown"
        if v <= 3:
            return "low"
        if v <= 6:
            return "medium"
        return "high"

    def _risk_label(e, d, s):
        """Human-readable narrative label for a function's CodeBalance position."""
        e, d, s = (e or 0), (d or 0), (s or 0)
        if e >= 7 and d >= 7:
            return "Critical Complexity"
        if e >= 7 and s >= 7:
            return "Complex + Unsafe"
        if e >= 7:
            return "High Energy Hotspot"
        if d >= 7 and s >= 7:
            return "Indebted + Risky"
        if d >= 7:
            return "High Debt Hotspot"
        if s >= 7:
            return "Safety Risk"
        if max(e, d, s) <= 3:
            return "Clean Code"
        return "Moderate Risk"

    def _grade(e, d, s):
        """Simplified A-F grade mirroring CodeBalance scorer logic."""
        worst = max(e or 0, d or 0, s or 0)
        if worst <= 2:
            return "A"
        if worst <= 4:
            return "B"
        if worst <= 6:
            return "C"
        if worst <= 8:
            return "D"
        return "F"

    def _hist_bins(values, bins=5):
        """Return counts for equal-width bins from 0 to 10."""
        step = 10 / bins
        labels, counts = [], []
        for i in range(bins):
            lo, hi = round(i * step), round((i + 1) * step)
            labels.append(f"{lo}–{hi}")
            counts.append(sum(1 for v in values if lo <= (v or 0) < hi))
        return {"labels": labels, "counts": counts}

    # ── routes ───────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/functions")
    def functions_view():
        return render_template("functions.html")

    @app.route("/search")
    def search_view():
        return render_template("search.html")

    @app.route("/heatmap")
    def heatmap_view():
        return render_template("heatmap.html")

    @app.route("/executive")
    def executive_view():
        return render_template("executive.html")

    # ── CodeBalance API (3D scatter data with full detail) ─────────────────────
    @app.route("/api/codebalance")
    def api_codebalance():
        fns = _load_functions()
        return jsonify(
            [
                {
                    "name": f.get("name", ""),
                    "file": f.get("file", ""),
                    "energy": f.get("energy", 0),
                    "debt": f.get("debt", 0),
                    "safety": f.get("safety", 0),
                    "line_start": f.get("line_start", 0),
                    "line_end": f.get("line_end", 0),
                }
                for f in fns
                if f.get("energy") is not None
            ]
        )

    @app.route("/api/functions")
    def api_functions():
        file_filter = request.args.get("file")
        functions = _load_functions()
        if file_filter:
            functions = [f for f in functions if f.get("file") == file_filter]
        return jsonify(functions)

    # ── Executive Summary API ─────────────────────────────────────────────────
    @app.route("/api/executive")
    def api_executive():
        fns = _load_functions()
        if not fns:
            return jsonify({"error": "No data. Run legacylens index first."}), 404

        items = []
        for f in fns:
            e = f.get("energy") or 0
            d = f.get("debt") or 0
            s = f.get("safety") or 0

            # Synthetic Tech Debt ROI Cost (example synthetic metric)
            cost = (d * 500) + (e * 200)

            # Risk factor prioritizes poor safety, then debt and energy
            risk_score = ((10 - s) * 10) + d + e

            items.append(
                {
                    "name": f.get("name", ""),
                    "file": f.get("file", ""),
                    "energy": e,
                    "debt": d,
                    "safety": s,
                    "cost": cost,
                    "risk_score": risk_score,
                }
            )

        return jsonify(
            {
                "expensive": sorted(items, key=lambda x: x["cost"], reverse=True)[:5],
                "risk": sorted(items, key=lambda x: x["risk_score"], reverse=True)[:5],
            }
        )

    # ── summary KPIs ──────────────────────────────────────────────────────────
    @app.route("/api/summary")
    def api_summary():
        fns = _load_functions()
        if not fns:
            return jsonify({"error": "No data. Run legacylens index first."}), 404

        energies = [f.get("energy") for f in fns if f.get("energy") is not None]
        debts = [f.get("debt") for f in fns if f.get("debt") is not None]
        safeties = [f.get("safety") for f in fns if f.get("safety") is not None]

        def avg(lst):
            return round(sum(lst) / len(lst), 2) if lst else 0

        # High-risk if ANY metric is >= 7
        high_risk = sum(
            1
            for f in fns
            if (f.get("energy") or 0) >= 7
            or (f.get("debt") or 0) >= 7
            or (f.get("safety") or 0) >= 7
        )

        # Files with at least one high-risk function
        risky_files = len(
            set(
                f.get("file", "")
                for f in fns
                if (f.get("energy") or 0) >= 7
                or (f.get("debt") or 0) >= 7
                or (f.get("safety") or 0) >= 7
            )
        )

        # Module breakdown (top-level directory after repo root)
        repo_root = _get_repo_root()
        module_scores = defaultdict(list)
        for fn in fns:
            fpath = fn.get("file", "")
            try:
                rel = Path(fpath).relative_to(repo_root) if repo_root else Path(fpath)
                module = rel.parts[0] if len(rel.parts) > 1 else "(root)"
            except ValueError:
                module = "(other)"
            module_scores[module].append(
                {
                    "energy": fn.get("energy", 0),
                    "debt": fn.get("debt", 0),
                    "safety": fn.get("safety", 0),
                }
            )

        module_summary = {
            m: {
                "count": len(scores),
                "avg_energy": avg([s["energy"] for s in scores]),
                "avg_debt": avg([s["debt"] for s in scores]),
                "avg_safety": avg([s["safety"] for s in scores]),
            }
            for m, scores in sorted(module_scores.items(), key=lambda x: -len(x[1]))
        }

        mtime = data_file.stat().st_mtime if data_file.exists() else None
        analysed_at = (
            datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "unknown"
        )

        return jsonify(
            {
                "total_functions": len(fns),
                "analysed_at": analysed_at,
                "avg_energy": avg(energies),
                "avg_debt": avg(debts),
                "avg_safety": avg(safeties),
                "high_risk_count": high_risk,
                "risky_files": risky_files,
                "module_summary": module_summary,
            }
        )

    # ── distribution histograms ───────────────────────────────────────────────
    @app.route("/api/distribution")
    def api_distribution():
        fns = _load_functions()
        return jsonify(
            {
                "energy": _hist_bins([f.get("energy") for f in fns if f.get("energy") is not None]),
                "debt": _hist_bins([f.get("debt") for f in fns if f.get("debt") is not None]),
                "safety": _hist_bins([f.get("safety") for f in fns if f.get("safety") is not None]),
            }
        )

    # ── top N functions by metric ─────────────────────────────────────────────
    @app.route("/api/top")
    def api_top():
        _VALID_METRICS = {"energy", "debt", "safety"}
        metric = request.args.get("metric", "debt")
        if metric not in _VALID_METRICS:
            return jsonify({"error": f"Invalid metric '{metric}'. Choose from: {sorted(_VALID_METRICS)}"}), 400
        try:
            limit = min(int(request.args.get("limit", 15)), 50)
        except ValueError:
            limit = 15
        reverse = request.args.get("order", "desc") == "desc"
        fns = _load_functions()
        valid = [f for f in fns if f.get(metric) is not None]
        ranked = sorted(valid, key=lambda f: f[metric], reverse=reverse)[:limit]
        # Strip code to keep payload small
        slim = [
            {
                "name": f.get("name", ""),
                "file": f.get("file", ""),
                "line_start": f.get("line_start", 0),
                "line_end": f.get("line_end", 0),
                "energy": f.get("energy"),
                "debt": f.get("debt"),
                "safety": f.get("safety"),
            }
            for f in ranked
        ]
        return jsonify(slim)

    # ── 3-D scatter data (enriched with grade + risk_label) ──────────────────
    @app.route("/api/scatter")
    def api_scatter():
        fns = _load_functions()
        return jsonify(
            [
                {
                    "name": f.get("name", ""),
                    "file": f.get("file", ""),
                    "energy": f.get("energy", 0),
                    "debt": f.get("debt", 0),
                    "safety": f.get("safety", 0),
                    "grade": _grade(f.get("energy"), f.get("debt"), f.get("safety")),
                    "risk_label": _risk_label(f.get("energy"), f.get("debt"), f.get("safety")),
                }
                for f in fns
                if f.get("energy") is not None
            ]
        )

    # ── file tree / file content (Explorer mode kept) ─────────────────────────
    @app.route("/api/tree")
    def api_tree():
        repo_root = _get_repo_root()
        if repo_root is None or not repo_root.exists():
            return jsonify({"error": "No repository indexed."}), 404
        fns = _load_functions()
        indexed_files = sorted(set(f.get("file", "") for f in fns if f.get("file")))
        tree = {}
        for file_path in indexed_files:
            try:
                rel = Path(file_path).relative_to(repo_root)
            except ValueError:
                rel = Path(file_path)
            parts = rel.parts
            node = tree
            for part in parts[:-1]:
                node = node.setdefault(part, {})
            node[parts[-1]] = file_path

        def _to_list(node, name="root"):
            if isinstance(node, str):
                return {"type": "file", "name": name, "path": node}
            children = [_to_list(v, k) for k, v in sorted(node.items())]
            return {"type": "dir", "name": name, "children": children}

        return jsonify(_to_list(tree))

    @app.route("/api/file")
    def api_file():
        file_path = request.args.get("path")
        if not file_path:
            abort(400)
        p = Path(file_path).resolve()
        # Security: only serve files that belong to the indexed repository.
        # This prevents path traversal attacks (e.g. ?path=/etc/passwd).
        repo_root = _get_repo_root()
        if repo_root is None:
            abort(403)  # No repo indexed — nothing safe to serve
        try:
            p.relative_to(repo_root.resolve())
        except ValueError:
            abort(403)  # Path escapes the repo root
        if not p.exists():
            abort(404)
        ext = p.suffix.lstrip(".")
        lang_map = {
            "py": "python",
            "java": "java",
            "js": "javascript",
            "ts": "typescript",
            "md": "markdown",
            "json": "json",
        }
        return jsonify(
            {
                "content": p.read_text(encoding="utf-8", errors="replace"),
                "language": lang_map.get(ext, "plaintext"),
                "path": file_path,
            }
        )

    @app.route("/api/repo_root")
    def api_repo_root():
        r = _get_repo_root()
        return jsonify({"root": str(r) if r else None})

    # ── Regen iteration trace ─────────────────────────────────────────────────
    @app.route("/api/regen_trace")
    def api_regen_trace():
        """Return the latest iteration log for a given function name.

        Query params:
          ?fn=<function_name>   (e.g. processFindForm)
        Returns the JSON written by faculty_demo.py --log-iterations.
        """
        fn = request.args.get("fn", "")
        traces_dir = Path.home() / ".legacylens" / "regen_traces"

        if fn:
            # Look for exact match first, then partial match
            candidates = list(traces_dir.glob(f"{fn}.json"))
            if not candidates:
                candidates = list(traces_dir.glob(f"*{fn}*.json"))
        else:
            # Return the most recently modified trace
            candidates = sorted(
                traces_dir.glob("*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

        if not candidates or not candidates[0].exists():
            return jsonify({"error": "No trace found. Run faculty_demo.py first."}), 404

        try:
            return jsonify(json.loads(candidates[0].read_text()))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── Persistent Explanation Cache ──────────────────────────────────────────
    @app.route("/api/explanation")
    def api_explanation():
        """Retrieve a cached high-confidence explanation.

        Query params:
          ?fn=<qualified_name>   (e.g. petclinic.Owner.processFindForm)
        """
        fn = request.args.get("fn", "")
        if not fn:
            return jsonify({"error": "Missing fn parameter"}), 400

        try:
            from legacylens.agents.explanation_store import ExplanationStore, current_fingerprint

            store = ExplanationStore()
            # Pass current fingerprint to ensure we don't return stale records
            # if the codebase has been re-indexed.
            record = store.get(fn, codebase_version=current_fingerprint())

            if not record:
                return jsonify({"error": "Not found or stale"}), 404

            return jsonify(record)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return app
