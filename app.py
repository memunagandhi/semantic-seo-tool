import os
import hmac
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
from datetime import datetime, timedelta
from io import BytesIO
from openpyxl import Workbook
from database import db, AnalysisRun, PassageResult, normalize_database_url
from engine import SemanticIREngine

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY')
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')

if not app.config['SECRET_KEY']:
    raise RuntimeError('FLASK_SECRET_KEY must be configured.')
if not APP_PASSWORD:
    raise RuntimeError('APP_PASSWORD must be configured.')
if len(APP_PASSWORD) < 16:
    raise RuntimeError('APP_PASSWORD must be at least 16 characters long.')

app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', '').lower() == 'true',
)

# Database configuration: PostgreSQL on Render, SQLite locally
_db_url = os.environ.get('DATABASE_URL')
if _db_url:
    app.config['SQLALCHEMY_DATABASE_URI'] = normalize_database_url(_db_url)
    print("[DB] Using PostgreSQL (Render)")
else:
    _db_path = os.path.join(os.path.dirname(__file__), 'semantic_tool.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_db_path}'
    print("[DB] Using SQLite (local)")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()


def get_active_cohere_key():
    return os.environ.get('COHERE_API_KEY', '').strip()


@app.before_request
def require_login():
    if request.endpoint in {'login', 'static'}:
        return None
    if not session.get('authenticated'):
        if request.path == '/api/analyze':
            return jsonify({'success': False, 'error': 'Authentication required.'}), 401
        return redirect(url_for('login'))
    return None


@app.context_processor
def inject_global_status():
    api_key = get_active_cohere_key()
    return {
        'cohere_is_live': bool(api_key),
        'engine_label': 'Cohere v3.5 Cross-Encoder (Live)' if api_key else 'Local Simulation Engine',
        'current_year': datetime.utcnow().year
    }


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('authenticated'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        password = request.form.get('password', '')
        if hmac.compare_digest(password.encode('utf-8'), APP_PASSWORD.encode('utf-8')):
            session.clear()
            session['authenticated'] = True
            session.permanent = True
            return redirect(url_for('dashboard'))
        error = 'Incorrect password.'
    return render_template('login.html', error=error)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def dashboard():
    api_key = get_active_cohere_key()
    total_runs = AnalysisRun.query.count()
    recent_runs = AnalysisRun.query.order_by(AnalysisRun.created_at.desc()).limit(5).all()
    return render_template(
        'dashboard.html',
        total_runs=total_runs,
        recent_runs=recent_runs,
        cohere_is_live=bool(api_key)
    )


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    data = request.get_json() or {}
    query = data.get('query', '').strip()
    passages = data.get('passages', [])

    if not query or not passages:
        return jsonify({'success': False, 'error': 'Query and at least one passage are required.'}), 400

    api_key = get_active_cohere_key()
    engine = SemanticIREngine(api_key=api_key)

    try:
        result = engine.analyze(query, passages)

        # Save to Database
        winner = result['winner']
        run = AnalysisRun(
            search_query=query,
            engine_mode=result['engine_mode'],
            top_score=winner['rerank_score'],
            top_passage_index=winner['original_index'] + 1,
            verdict=result['verdict'],
            missing_entities=', '.join(result['missing_entities']),
            copy_advice=result['copy_advice'],
            total_passages=result['total_passages']
        )
        db.session.add(run)
        db.session.flush()

        for item in result['comparison_table']:
            pr = PassageResult(
                analysis_id=run.id,
                original_index=item['original_index'] + 1,
                content=item['document'],
                dense_similarity=item['dense_similarity'],
                initial_dense_rank=item['initial_dense_rank'],
                rerank_score=item['rerank_score'],
                post_rerank_position=item['post_rerank_position'],
                rank_shift=item['rank_shift']
            )
            db.session.add(pr)

        db.session.commit()
        result['run_id'] = run.id
        result['success'] = True
        return jsonify(result)

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/history')
def history():
    runs = AnalysisRun.query.order_by(AnalysisRun.created_at.desc()).all()
    return render_template('history.html', runs=runs)


@app.route('/history/<int:run_id>')
def history_detail(run_id):
    run = AnalysisRun.query.get_or_404(run_id)
    return render_template('history_detail.html', run=run)


@app.route('/export.xlsx')
def export_excel():
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'SEO Analyses'

    headers = [
        'ID', 'Date (UTC)', 'Search Query', 'Engine Mode', 'Winning Passage', 
        'Relevance Score', 'AEO Verdict', 'Missing Entities', 'Copy Advice'
    ]
    sheet.append(headers)

    runs = AnalysisRun.query.order_by(AnalysisRun.created_at.desc()).all()
    for r in runs:
        sheet.append([
            r.id,
            r.created_at.strftime('%Y-%m-%d %H:%M'),
            r.search_query,
            r.engine_mode,
            f"Passage #{r.top_passage_index}",
            r.top_score,
            r.verdict,
            r.missing_entities or 'None (Fully Aligned)',
            r.copy_advice
        ])

    # Styling
    for cell in sheet[1]:
        cell.font = cell.font.copy(bold=True)
    sheet.freeze_panes = 'A2'

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = f"semantic-seo-evaluations-{datetime.utcnow():%Y%m%d-%H%M}.xlsx"
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@app.route('/settings')
def settings():
    return render_template('settings.html')


if __name__ == '__main__':
    app.run(debug=True, port=5001)
