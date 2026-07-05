"""Projects module service — orchestrates repositories + domain rules.

This is the only layer the Streamlit pages talk to for Projects data;
pages never import repositories or models directly.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.metrics import track
from app.database.models.projects import Project, ProjectStatus, Task, TaskStatus
from app.domain import projects_rules
from app.repositories.projects_repository import (
    MilestoneRepository,
    ProjectRepository,
    TaskRepository,
)

logger = get_logger("services.projects")


class ProjectsService:
    def __init__(self, session: Session):
        self.session = session
        self.projects = ProjectRepository(session)
        self.tasks = TaskRepository(session)
        self.milestones = MilestoneRepository(session)

    @track("projects.create_project")
    def create_project(
        self,
        code: str,
        name: str,
        start_date: date,
        target_end_date: date,
        budget: float,
        sponsor_department_id: int | None = None,
    ) -> Project:
        projects_rules.validate_budget(budget)
        projects_rules.validate_dates(start_date, target_end_date)

        project = Project(
            code=code,
            name=name,
            sponsor_department_id=sponsor_department_id,
            status=ProjectStatus.PLANNING,
            start_date=start_date,
            target_end_date=target_end_date,
            budget=budget,
        )
        self.projects.add(project)
        logger.info("Created project %s (%s)", code, name)
        return project

    @track("projects.transition_project")
    def transition_project(self, project_id: int, target_status: ProjectStatus) -> Project:
        project = self.projects.get(project_id)
        projects_rules.assert_transition(project.status, target_status)
        project.status = target_status
        self.session.flush()
        logger.info("Project %s moved to %s", project.code, target_status.value)
        return project

    @track("projects.add_task")
    def add_task(
        self,
        project_id: int,
        title: str,
        estimated_hours: float,
        assignee_employee_id: int | None = None,
        due_date: date | None = None,
    ) -> Task:
        task = Task(
            project_id=project_id,
            title=title,
            assignee_employee_id=assignee_employee_id,
            status=TaskStatus.TODO,
            due_date=due_date,
            estimated_hours=estimated_hours,
        )
        self.tasks.add(task)
        logger.info("Added task '%s' to project %s", title, project_id)
        return task

    @track("projects.complete_task")
    def complete_task(self, task_id: int) -> Task:
        task = self.tasks.get(task_id)
        task.status = TaskStatus.DONE
        self.session.flush()
        logger.info("Task %s marked done", task.title)
        return task

    @track("projects.project_health_report")
    def project_health_report(self) -> list[dict]:
        active = self.projects.active_projects()
        rates = dict(self.tasks.completion_rate_by_project())
        return [
            {
                "project": project.name,
                "completion_rate": rates.get(project.name, 0.0),
                "status": project.status.value,
            }
            for project in active
        ]

    @track("projects.status_breakdown")
    def status_breakdown(self) -> list[tuple[str, int]]:
        return self.projects.count_by_status()

    def upcoming_milestones(self, as_of: date, limit: int = 10):
        return self.milestones.upcoming_milestones(as_of, limit)
