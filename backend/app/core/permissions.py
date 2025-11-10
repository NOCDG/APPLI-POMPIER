# app/core/permissions.py
from typing import Iterable
from app.db.models import RoleEnum, User

FULL_ACCESS = {RoleEnum.ADMIN, RoleEnum.OFFICIER}
TEAM_EDIT   = {RoleEnum.CHEF_EQUIPE, RoleEnum.ADJ_CHEF_EQUIPE}
READ_ALL    = {RoleEnum.OPE} | FULL_ACCESS

def roles_of(user: User) -> set[RoleEnum]:
    return {ur.role for ur in user.roles} | {RoleEnum.AGENT}  # héritage AGENT

def is_full_access(user: User) -> bool:
    return bool(roles_of(user) & FULL_ACCESS)

def can_read_all(user: User) -> bool:
    return bool(roles_of(user) & READ_ALL)

def can_edit_team(user: User, team_id: int | None) -> bool:
    rs = roles_of(user)
    if rs & FULL_ACCESS:
        return True
    if team_id is None:
        return False
    return (rs & TEAM_EDIT) and (user.equipe_id == team_id)

def can_read_team(user: User, team_id: int | None) -> bool:
    rs = roles_of(user)
    if rs & READ_ALL:
        return True
    if team_id is None:
        return False
    # AGENT (et tous rôles héritent d'AGENT) peuvent lire leur équipe
    return user.equipe_id == team_id
