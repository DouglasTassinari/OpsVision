from datetime import date

from app.database.models.projects import Milestone, Project, ProjectStatus, Task, TaskStatus
from app.repositories.projects_repository import (
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
)


def _make_project(session, status=ProjectStatus.ACTIVE, code="PRJ-1") -> Project:
    project = Project(
        code=code,
        name="Warehouse Rollout",
        status=status,
        start_date=date(2026, 1, 1),
        target_end_date=date(2026, 6, 1),
        budget=50000,
    )
    session.add(project)
    session.flush()
    return project


def test_active_projects_filters_by_status(session):
    active = _make_project(session, status=ProjectStatus.ACTIVE, code="PRJ-1")
    _make_project(session, status=ProjectStatus.PLANNING, code="PRJ-2")

    repo = ProjectRepository(session)
    result = repo.active_projects()

    assert [p.id for p in result] == [active.id]


def test_projects_between_filters_by_start_date(session):
    early = _make_project(session, code="PRJ-3")
    early.start_date = date(2026, 1, 10)
    late = _make_project(session, code="PRJ-4")
    late.start_date = date(2026, 5, 1)
    session.flush()

    repo = ProjectRepository(session)
    result = repo.projects_between(date(2026, 1, 1), date(2026, 2, 1))

    assert [p.id for p in result] == [early.id]


def test_completion_rate_by_project_computes_percentage(session):
    project = _make_project(session)
    session.add_all(
        [
            Task(project_id=project.id, title="A", status=TaskStatus.DONE, estimated_hours=1),
            Task(project_id=project.id, title="B", status=TaskStatus.DONE, estimated_hours=1),
            Task(project_id=project.id, title="C", status=TaskStatus.TODO, estimated_hours=1),
            Task(project_id=project.id, title="D", status=TaskStatus.IN_PROGRESS, estimated_hours=1),
        ]
    )
    session.flush()

    repo = TaskRepository(session)
    rows = repo.completion_rate_by_project()

    assert rows == [("Warehouse Rollout", 50.0)]


def test_tasks_by_project_returns_only_its_tasks(session):
    project = _make_project(session, code="PRJ-5")
    other = _make_project(session, code="PRJ-6")
    session.add_all(
        [
            Task(project_id=project.id, title="A", estimated_hours=1),
            Task(project_id=other.id, title="B", estimated_hours=1),
        ]
    )
    session.flush()

    repo = TaskRepository(session)
    result = repo.tasks_by_project(project.id)

    assert [t.title for t in result] == ["A"]


def test_upcoming_milestones_excludes_achieved_and_past(session):
    project = _make_project(session, code="PRJ-7")
    upcoming = Milestone(
        project_id=project.id, name="Phase 1", due_date=date(2026, 2, 1), achieved=False
    )
    achieved = Milestone(
        project_id=project.id, name="Kickoff", due_date=date(2026, 2, 2), achieved=True
    )
    past = Milestone(
        project_id=project.id, name="Old", due_date=date(2025, 1, 1), achieved=False
    )
    session.add_all([upcoming, achieved, past])
    session.flush()

    repo = MilestoneRepository(session)
    result = repo.upcoming_milestones(date(2026, 1, 1))

    assert [m.name for m in result] == ["Phase 1"]


def test_count_by_status_groups_all_projects(session):
    _make_project(session, status=ProjectStatus.ACTIVE, code="PRJ-20")
    _make_project(session, status=ProjectStatus.ACTIVE, code="PRJ-21")
    _make_project(session, status=ProjectStatus.COMPLETED, code="PRJ-22")

    repo = ProjectRepository(session)
    rows = repo.count_by_status()

    assert rows == [("active", 2), ("completed", 1)]
