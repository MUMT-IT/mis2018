"""Verify the staff plan visibility predicate against relational data."""
import ast
from pathlib import Path

from sqlalchemy import Column, ForeignKey, Integer, create_engine, or_
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


def test_staff_can_track_coordinated_plans_without_exposing_unrelated_plans():
    base = declarative_base()

    class Plan(base):
        __tablename__ = 'plans'
        id = Column(Integer, primary_key=True)
        fiscal_year = Column(Integer)
        budget_proposer_id = Column(Integer)
        operator_staff_id = Column(Integer)
        committee_members = relationship('Member')

    class Member(base):
        __tablename__ = 'members'
        id = Column(Integer, primary_key=True)
        plan_id = Column(Integer, ForeignKey('plans.id'))
        staff_id = Column(Integer)

    source = ast.parse((Path(__file__).resolve().parents[1] / 'app/staff/views.py').read_text())
    helper = next(node for node in source.body if isinstance(node, ast.FunctionDef)
                  and node.name == '_staff_related_procurement_plan_filter')
    scope = dict(or_=or_, ProcurementPlan=Plan, ProcurementPlanCommitteeMember=Member)
    exec(compile(ast.Module(body=[helper], type_ignores=[]), '<staff plan visibility>', 'exec'), scope)
    predicate = scope['_staff_related_procurement_plan_filter']
    engine = create_engine('sqlite://')
    base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add_all([
            Plan(id=1, fiscal_year=2570, operator_staff_id=42),
            Plan(id=2, fiscal_year=2570, budget_proposer_id=42),
            Plan(id=3, fiscal_year=2570, committee_members=[Member(staff_id=42)]),
            Plan(id=4, fiscal_year=2570, operator_staff_id=42, budget_proposer_id=42,
                 committee_members=[Member(staff_id=42)]),
            Plan(id=5, fiscal_year=2570, operator_staff_id=99, budget_proposer_id=99,
                 committee_members=[Member(staff_id=99)]),
            Plan(id=6, fiscal_year=2569, operator_staff_id=42),
        ])
        session.commit()
        plans = session.query(Plan).filter(Plan.fiscal_year == 2570, predicate(42)).order_by(Plan.id).all()
        assert [plan.id for plan in plans] == [1, 2, 3, 4]
        years = session.query(Plan.fiscal_year).filter(predicate(42)).distinct().all()
        assert {year for year, in years} == {2569, 2570}
        assert session.query(Plan).filter(Plan.id == 1, predicate(42)).one().id == 1
        assert session.query(Plan).filter(Plan.id == 5, predicate(42)).first() is None
        assert session.query(Plan).filter(predicate(100)).all() == []
    finally:
        session.close()
        engine.dispose()
