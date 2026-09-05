"""
MULTI-TENANT AUTH MODELS
=========================
Organization → Users (with roles) → Workspaces → Projects

Roles:
- OWNER   : Full control incl. billing/delete org
- ADMIN   : Manage users, workspaces, all projects
- MANAGER : Create/edit projects in assigned workspaces
- VIEWER  : Read-only access to assigned workspaces
- GUEST   : Legacy mode — no account, backward compat
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from database import Base


class Organization(Base):
    """A tenant — typically one company/customer."""
    __tablename__ = 'organizations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    domain = Column(String(255))  # e.g., "acmecorp.com" for auto-join
    
    plan = Column(String(50), default='free')  # free, pro, enterprise
    max_users = Column(Integer, default=5)
    max_projects = Column(Integer, default=25)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSON, default=dict)

    users = relationship('User', back_populates='organization', cascade='all, delete-orphan')
    workspaces = relationship('Workspace', back_populates='organization', cascade='all, delete-orphan')


class User(Base):
    """A user account. Belongs to one organization."""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255))  # nullable for SSO users
    full_name = Column(String(255), nullable=False)
    
    role = Column(String(20), default='viewer')  # owner, admin, manager, viewer
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    settings = Column(JSON, default=dict)
    
    # SSO fields (for future Google/Microsoft/Okta integration)
    sso_provider = Column(String(50))  # google, microsoft, okta
    sso_subject_id = Column(String(255))

    organization = relationship('Organization', back_populates='users')
    workspace_memberships = relationship('WorkspaceMembership', back_populates='user', cascade='all, delete-orphan')

    def to_dict(self, include_sensitive=False):
        d = {
            'id': self.id,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'org_id': self.org_id,
            'org_name': self.organization.name if self.organization else '',
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_sensitive:
            d['sso_provider'] = self.sso_provider
        return d


class Workspace(Base):
    """A workspace within an organization (e.g., a program or division)."""
    __tablename__ = 'workspaces'

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True)
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    color = Column(String(20), default='#3b82f6')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_user_id = Column(Integer, ForeignKey('users.id'))
    
    organization = relationship('Organization', back_populates='workspaces')
    memberships = relationship('WorkspaceMembership', back_populates='workspace', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'org_id': self.org_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class WorkspaceMembership(Base):
    """Explicit user-workspace access (for granular permissions)."""
    __tablename__ = 'workspace_memberships'

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(20), default='viewer')  # can override user's org role for this workspace
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    workspace = relationship('Workspace', back_populates='memberships')
    user = relationship('User', back_populates='workspace_memberships')

    __table_args__ = (Index('idx_ws_user', 'workspace_id', 'user_id', unique=True),)


class Invitation(Base):
    """Pending email invitations to join an organization."""
    __tablename__ = 'invitations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False)
    
    email = Column(String(255), nullable=False)
    role = Column(String(20), default='viewer')
    token = Column(String(64), unique=True, nullable=False, index=True)
    
    invited_by_user_id = Column(Integer, ForeignKey('users.id'))
    accepted_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
