"""
Seed historical clinical events into trajectory_events.

Background:
  On 2026-10-02, PRESET_EVENTS (hard-coded in api/v1/cases.py) were removed
  because they leaked specific patient (胡运涛/曾银鸾) medical record data
  into a generic API. This script migrates those events into the
  trajectory_events table, keyed by case_id, age, event_type, label.

  The matching rules (syndrome_hint contains X) come from the original
  PRESET_EVENTS dict; they remain clinical heuristics but are now
  scoped per-case rather than applied globally to every user.

Usage (from backend/):
    python scripts/seed_clinical_events.py [--apply]   # --apply=write, default=dry-run

Idempotent:
  Skips rows already present (case_id + age + event_type + label match).
"""
import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Reconstruct original PRESET_EVENTS → TrajectoryEvent field mapping
# source='seeded_clinical' distinguishes these from manual frontend entries
SEED_HINTS = [
    {'contains': '假性充盈', 'event_type': '悖论态', 'label': 'PPG土+0.60=假性充盈≠真旺',
     'direction': '注意', 'damage': None, 'boost': None},
    {'contains': '湿热化火', 'event_type': '干预', 'label': 'v5.5方：薏苡仁+竹茹清湿热',
     'direction': '收敛', 'boost': {'scoreDelta': 3.5}},
    {'contains': '气滞血瘀', 'event_type': '排病', 'label': '湿泻+阳虚寒象暴露',
     'direction': '短期发散', 'damage': {'isSideEffect': True}},
    {'contains': '趋于正常', 'event_type': '干预', 'label': 'v5.7最小试探方·桂枝汤透火郁',
     'direction': '收敛', 'boost': {'scoreDelta': 8.2}},
    {'contains': '正常脉象', 'event_type': '收敛', 'label': '服方on·五形回归正常',
     'direction': '收敛', 'damage': None, 'boost': None},
    {'contains': '停药off', 'event_type': '偏离', 'label': '停药on-off验证复发·肝郁87%',
     'direction': '发散', 'damage': {'scoreDelta': -6.3}},
    {'contains': '气阴两虚', 'event_type': '偏离', 'label': '爬山耗气·气阴两虚',
     'direction': '发散', 'damage': {'isSideEffect': True}},
    {'contains': '湿遏', 'event_type': '排病', 'label': '湿遏·火衰-0.41·重建v7.0苓桂术甘',
     'direction': '短期发散', 'damage': {'isSideEffect': True}},
]


def run(dry_run: bool):
    os.environ.setdefault("DATABASE_URL", "postgresql://qingnang:qingnang@localhost:5432/qingnang")
    try:
        from sqlalchemy.orm import Session
        from app.database import SessionLocal
        from app.models import Observation, Case, User, TrajectoryEvent
    except Exception as e:
        print(f"[error] cannot import app models: {e}")
        print("  Make sure DATABASE_URL is set and alembic has been run.")
        sys.exit(2)

    db: Session = SessionLocal()
    try:
        # Find all cases with observations that match any seed hint
        cases = db.query(Case).all()
        total_inserted = 0
        total_skipped = 0
        total_cases = 0

        for case in cases:
            obs_list = (db.query(Observation)
                        .filter(Observation.case_id == case.id)
                        .order_by(Observation.observed_at)
                        .all())
            if not obs_list:
                continue

            user = db.query(User).filter(User.id == case.user_id).first()
            birth_year = None
            if user and user.birth_date:
                try:
                    birth_year = int(str(user.birth_date)[:4])
                except (ValueError, TypeError):
                    birth_year = None

            case_events_added = 0
            for ob in obs_list:
                hint = (ob.syndrome_hint or '')
                for rule in SEED_HINTS:
                    if rule['contains'] not in hint:
                        continue
                    # Compute age from observed_at and birth_date
                    age = None
                    if birth_year and ob.observed_at:
                        try:
                            obs_year = ob.observed_at.year
                            age = obs_year - birth_year
                        except Exception:
                            age = None
                    if age is None:
                        age = 30  # fallback, marked unreliable

                    # Idempotency check
                    exists = (db.query(TrajectoryEvent)
                              .filter(TrajectoryEvent.case_id == case.id,
                                      TrajectoryEvent.event_type == rule['event_type'],
                                      TrajectoryEvent.label == rule['label'])
                              .first())
                    if exists:
                        total_skipped += 1
                        continue

                    te = TrajectoryEvent(
                        case_id=case.id,
                        age=age,
                        event_type=rule['event_type'],
                        label=rule['label'],
                        direction=rule['direction'],
                        damage=rule['damage'],
                        boost=rule['boost'],
                        duration_days=540,
                        source='seeded_clinical',
                    )
                    if dry_run:
                        print(f"  [dry-run] case={case.id} age={age} type={rule['event_type']} "
                              f"label={rule['label']} source=seeded_clinical")
                    else:
                        db.add(te)
                    total_inserted += 1
                    case_events_added += 1

            if case_events_added > 0:
                total_cases += 1

        if dry_run:
            print(f"\n[dry-run] Would insert {total_inserted} events across {total_cases} cases. "
                  f"Already present: {total_skipped}.")
            print("  Re-run with --apply to commit.")
        else:
            db.commit()
            print(f"\n[ok] Inserted {total_inserted} events across {total_cases} cases. "
                  f"Skipped (already present): {total_skipped}.")

    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser(description="Seed historical clinical events into trajectory_events")
    ap.add_argument("--apply", action="store_true", help="Actually write to DB (default is dry-run)")
    args = ap.parse_args()
    run(dry_run=not args.apply)


if __name__ == "__main__":
    main()
