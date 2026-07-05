"""Data access for the Projects module."""
from __future__ import annotations

from datetime import date

from sqlalchemy import case, func, select

from app.database.models.projects import Milestone, Project, ProjectStatus, Task, TaskStatus
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    def active_projects(self) -> list[Project]:
        stmt = select(Project).where(Project.status == ProjectStatus.ACTIVE)
        return list(self.session.execute(stmt).scalars().all())

    def projects_between(self, start: date, end: date) -> list[Project]:
        stmt = select(Project).where(Project.start_date >= start, Project.start_date <= end)
        return list(self.session.execute(stmt).scalars().all())

    def count_by_status(self) -> list[tuple[str, int]]:
        """Project count grouped by status (enum value, count)."""
        stmt = (
            select(Project.status, func.count().label("total"))
            .group_by(Project.status)
            .order_by(func.count().desc())
        )
        return [(status.value, int(count)) for status, count in self.session.execute(stmt).all()]


class TaskRepository(BaseRepository[Task]):
    model = Task

    def tasks_by_project(self, project_id: int) -> list[Task]:
        stmt = select(Task).where(Task.project_id == project_id)
        return list(self.session.execute(stmt).scalars().all())

    def completion_rate_by_project(self) -> list[tuple[str, float]]:
        stmt = (
            select(
                Project.name,
                func.count(Task.id).label("total"),
                func.sum(case((Task.status == TaskStatus.DONE, 1), else_=0)).label("done"),
            )
            .join(Task, Task.project_id == Project.id)
            .group_by(Project.id)
        )
        rows = self.session.execute(stmt).all()
        return [
            (name, round(float(done or 0) / total * 100, 2) if total else 0.0)
            for name, total, done in rows
        ]


class MilestoneRepository(BaseRepository[Milestone]):
    model = Milestone

    def upcoming_milestones(self, as_of: date, limit: int = 10) -> list[Milestone]:
        stmt = (
            select(Milestone)
            .where(Milestone.achieved.is_(False), Milestone.due_date >= as_of)
            .order_by(Milestone.due_date.asc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
