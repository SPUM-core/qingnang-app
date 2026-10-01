import os; os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import sys; sys.path.insert(0, 'e:/工作/qingnang-APP/backend')
from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
with engine.connect() as conn:
    r = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'cases' ORDER BY ordinal_position"
    ))
    print('=== cases columns ===')
    for row in r.fetchall():
        print(f'  {row[0]}')
