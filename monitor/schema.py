import json


def migrate(db):
    additions = {
      'videos': {'creator_id':"TEXT NOT NULL DEFAULT ''", 'classification_origin':"TEXT NOT NULL DEFAULT ''", 'duration_seconds':'INTEGER',
        'summary_zh':"TEXT NOT NULL DEFAULT ''", 'market_evidence':"TEXT NOT NULL DEFAULT ''",
        'language_evidence':"TEXT NOT NULL DEFAULT ''", 'materials':"TEXT NOT NULL DEFAULT '{}'",
        'baseline_only':'INTEGER NOT NULL DEFAULT 0', 'availability':"TEXT NOT NULL DEFAULT 'active'",
        'last_checked_at':'TEXT', 'evidence_source':"TEXT NOT NULL DEFAULT ''"},
      'snapshots': {'shares':'INTEGER'},
      'trends': {'geo':"TEXT NOT NULL DEFAULT 'US'", 'search_type':"TEXT NOT NULL DEFAULT 'web'",
        'match_type':"TEXT NOT NULL DEFAULT 'search_term'", 'range_label':"TEXT NOT NULL DEFAULT ''",
        'collected_at':"TEXT NOT NULL DEFAULT ''", 'partial':'INTEGER NOT NULL DEFAULT 0'},
    }
    for table, columns in additions.items():
        existing = {r[1] for r in db.execute('PRAGMA table_info('+table+')')}
        for column, kind in columns.items():
            if column not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {kind}')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS creators(platform TEXT NOT NULL, account_id TEXT NOT NULL,
        profile TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(platform,account_id));
      CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, video_id TEXT NOT NULL,
        reviewed_at TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS queries(id INTEGER PRIMARY KEY, run_at TEXT NOT NULL,
        query TEXT NOT NULL, pages INTEGER NOT NULL, discovered INTEGER NOT NULL, status TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS related_queries(series_id TEXT NOT NULL, query TEXT NOT NULL,
        kind TEXT NOT NULL, term TEXT NOT NULL, value TEXT, source TEXT NOT NULL, collected_at TEXT NOT NULL);
    ''')
    # One-time migration of legacy accounts; no identity is merged across platforms.
    for v in db.execute("SELECT * FROM videos WHERE creator_id=''").fetchall():
        account_id = (v['creator_url'].split('/channel/')[-1].strip('/') if '/channel/' in v['creator_url'] else v['creator_url']) or v['creator']
        db.execute('UPDATE videos SET creator_id=? WHERE id=?',(account_id,v['id']))
        profile={k:v[k] for k in ('creator','creator_url','market','language','creator_type','contact','contact_source')}
        db.execute('INSERT OR IGNORE INTO creators VALUES (?,?,?,?)',(v['platform'],account_id,json.dumps(profile),v['discovered_at']))
