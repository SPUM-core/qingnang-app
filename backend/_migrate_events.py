"""先建 trajectory_events 表，种子跳过（曾银鸾无 case）"""
import psycopg2

DDL = """
CREATE TABLE IF NOT EXISTS trajectory_events (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    age INTEGER NOT NULL,
    day INTEGER,
    event_type VARCHAR(16) NOT NULL,
    label TEXT,
    direction VARCHAR(8),
    damage JSONB,
    boost JSONB,
    duration_days INTEGER DEFAULT 540,
    source VARCHAR(16) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

conn = psycopg2.connect('postgresql://qingnang:WOe4I3PsZod5VtDrLqMmTCb6@localhost:5432/qingnang')
cur = conn.cursor()
cur.execute(DDL)
cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='trajectory_events')")
print(f'✅ trajectory_events 表存在: {cur.fetchone()[0]}')

# 查 case 里有哪些用户 + 他们有多少 observations
cur.execute("""
    SELECT u.id, u.nickname, COUNT(o.id) AS obs_count
    FROM users u LEFT JOIN cases c ON c.user_id=u.id
    LEFT JOIN observations o ON o.case_id=c.id
    WHERE c.id IS NOT NULL
    GROUP BY u.id, u.nickname
""")
for row in cur.fetchall():
    print(f'  user_id={row[0]} nickname={row[1]} obs_count={row[2]}')

conn.commit()
conn.close()
