"""Flask app for the LegacyLens web dashboard."""

from flask import Flask, jsonify, render_template, request, abort
import json
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def create_app():
    app = Flask(__name__)

    data_file    = Path.home() / '.legacylens' / 'function_data.json'
    repo_root_file = Path.home() / '.legacylens' / 'repo_root.txt'

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
            return 'unknown'
        if v <= 3:
            return 'low'
        if v <= 6:
            return 'medium'
        return 'high'

    def _hist_bins(values, bins=5):
        """Return counts for equal-width bins from 0 to 10."""
        step = 10 / bins
        labels, counts = [], []
        for i in range(bins):
            lo, hi = round(i * step), round((i + 1) * step)
            labels.append(f'{lo}–{hi}')
            counts.append(sum(1 for v in values if lo <= (v or 0) < hi))
        return {'labels': labels, 'counts': counts}

    # ── routes ───────────────────────────────────────────────────────────────

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/functions')
    def functions_view():
        return render_template('functions.html')

    @app.route('/search')
    def search_view():
        return render_template('search.html')

    @app.route('/heatmap')
    def heatmap_view():
        return render_template('heatmap.html')

    # ── CodeBalance API (3D scatter data with full detail) ─────────────────────
    @app.route('/api/codebalance')
    def api_codebalance():
        fns = _load_functions()
        return jsonify([
            {
                'name':   f.get('name', ''),
                'file':   f.get('file', ''),
                'energy': f.get('energy', 0),
                'debt':   f.get('debt', 0),
                'safety': f.get('safety', 0),
                'line_start': f.get('line_start', 0),
                'line_end':   f.get('line_end', 0),
            }
            for f in fns
            if f.get('energy') is not None
        ])

    @app.route('/api/functions')
    def api_functions():
        file_filter = request.args.get('file')
        functions = _load_functions()
        if file_filter:
            functions = [f for f in functions if f.get('file') == file_filter]
        return jsonify(functions)

    # ── summary KPIs ──────────────────────────────────────────────────────────
    @app.route('/api/summary')
    def api_summary():
        fns = _load_functions()
        if not fns:
            return jsonify({'error': 'No data. Run legacylens index first.'}), 404

        energies = [f.get('energy') for f in fns if f.get('energy') is not None]
        debts    = [f.get('debt')   for f in fns if f.get('debt')   is not None]
        safeties = [f.get('safety') for f in fns if f.get('safety') is not None]

        def avg(lst): return round(sum(lst) / len(lst), 2) if lst else 0

        # High-risk if ANY metric is >= 7
        high_risk = sum(
            1 for f in fns
            if (f.get('energy') or 0) >= 7 or (f.get('debt') or 0) >= 7 or (f.get('safety') or 0) >= 7
        )

        # Files with at least one high-risk function
        risky_files = len(set(
            f.get('file', '') for f in fns
            if (f.get('energy') or 0) >= 7 or (f.get('debt') or 0) >= 7 or (f.get('safety') or 0) >= 7
        ))

        # Module breakdown (top-level directory after repo root)
        repo_root = _get_repo_root()
        module_scores = defaultdict(list)
        for fn in fns:
            fpath = fn.get('file', '')
            try:
                rel = Path(fpath).relative_to(repo_root) if repo_root else Path(fpath)
                module = rel.parts[0] if len(rel.parts) > 1 else '(root)'
            except ValueError:
                module = '(other)'
            module_scores[module].append({
                'energy': fn.get('energy', 0),
                'debt':   fn.get('debt', 0),
                'safety': fn.get('safety', 0),
            })

        module_summary = {
            m: {
                'count': len(scores),
                'avg_energy': avg([s['energy'] for s in scores]),
                'avg_debt':   avg([s['debt']   for s in scores]),
                'avg_safety': avg([s['safety'] for s in scores]),
            }
            for m, scores in sorted(module_scores.items(), key=lambda x: -len(x[1]))
        }

        mtime = data_file.stat().st_mtime if data_file.exists() else None
        analysed_at = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M') if mtime else 'unknown'

        return jsonify({
            'total_functions': len(fns),
            'analysed_at': analysed_at,
            'avg_energy': avg(energies),
            'avg_debt':   avg(debts),
            'avg_safety': avg(safeties),
            'high_risk_count': high_risk,
            'risky_files': risky_files,
            'module_summary': module_summary,
        })

    # ── distribution histograms ───────────────────────────────────────────────
    @app.route('/api/distribution')
    def api_distribution():
        fns = _load_functions()
        return jsonify({
            'energy': _hist_bins([f.get('energy') for f in fns if f.get('energy') is not None]),
            'debt':   _hist_bins([f.get('debt')   for f in fns if f.get('debt')   is not None]),
            'safety': _hist_bins([f.get('safety') for f in fns if f.get('safety') is not None]),
        })

    # ── top N functions by metric ─────────────────────────────────────────────
    @app.route('/api/top')
    def api_top():
        metric  = request.args.get('metric', 'debt')
        limit   = min(int(request.args.get('limit', 15)), 50)
        reverse = request.args.get('order', 'desc') == 'desc'
        fns = _load_functions()
        valid = [f for f in fns if f.get(metric) is not None]
        ranked = sorted(valid, key=lambda f: f[metric], reverse=reverse)[:limit]
        # Strip code to keep payload small
        slim = [
            {
                'name':       f.get('name', ''),
                'file':       f.get('file', ''),
                'line_start': f.get('line_start', 0),
                'line_end':   f.get('line_end', 0),
                'energy':     f.get('energy'),
                'debt':       f.get('debt'),
                'safety':     f.get('safety'),
            }
            for f in ranked
        ]
        return jsonify(slim)

    # ── 3-D scatter data ─────────────────────────────────────────────────────
    @app.route('/api/scatter')
    def api_scatter():
        fns = _load_functions()
        return jsonify([
            {
                'name':   f.get('name', ''),
                'file':   f.get('file', ''),
                'energy': f.get('energy', 0),
                'debt':   f.get('debt', 0),
                'safety': f.get('safety', 0),
            }
            for f in fns
            if f.get('energy') is not None
        ])

    # ── file tree / file content (Explorer mode kept) ─────────────────────────
    @app.route('/api/tree')
    def api_tree():
        repo_root = _get_repo_root()
        if repo_root is None or not repo_root.exists():
            return jsonify({'error': 'No repository indexed.'}), 404
        fns = _load_functions()
        indexed_files = sorted(set(f.get('file', '') for f in fns if f.get('file')))
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
        def _to_list(node, name='root'):
            if isinstance(node, str):
                return {'type': 'file', 'name': name, 'path': node}
            children = [_to_list(v, k) for k, v in sorted(node.items())]
            return {'type': 'dir', 'name': name, 'children': children}
        return jsonify(_to_list(tree))

    @app.route('/api/file')
    def api_file():
        file_path = request.args.get('path')
        if not file_path:
            abort(400)
        p = Path(file_path)
        if not p.exists():
            abort(404)
        ext = p.suffix.lstrip('.')
        lang_map = {'py': 'python', 'java': 'java', 'js': 'javascript',
                    'ts': 'typescript', 'md': 'markdown', 'json': 'json'}
        return jsonify({
            'content':  p.read_text(encoding='utf-8', errors='replace'),
            'language': lang_map.get(ext, 'plaintext'),
            'path':     file_path,
        })

    @app.route('/api/repo_root')
    def api_repo_root():
        r = _get_repo_root()
        return jsonify({'root': str(r) if r else None})

    return app
