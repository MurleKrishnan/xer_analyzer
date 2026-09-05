"""
AUTHENTICATION SERVICE
=======================
Business logic for user registration, login, and org management.
Uses Werkzeug's password hashing (bundled with Flask — no extra deps).
"""

import re
import uuid
import logging
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db
from auth_models import Organization, User, Workspace, WorkspaceMembership, Invitation

logger = logging.getLogger(__name__)


class AuthService:
    """User authentication and organization management."""

    # ═══════════════════════════════════════════
    # REGISTRATION
    # ═══════════════════════════════════════════

    @staticmethod
    def register_new_org(org_name, email, password, full_name):
        """
        Register a new organization with the first user as owner.
        Returns (user_dict, error_message) tuple.
        """
        if not email or not password or not org_name:
            return None, "All fields are required"

        email = email.strip().lower()
        
        if not AuthService._is_valid_email(email):
            return None, "Invalid email address"
        
        if len(password) < 8:
            return None, "Password must be at least 8 characters"
        
        db = get_db()
        try:
            # Check if email already exists
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                return None, "Email already registered. Please log in instead."

            # Create org
            slug = AuthService._slugify(org_name)
            # Ensure slug unique
            base_slug = slug
            counter = 1
            while db.query(Organization).filter(Organization.slug == slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1

            org = Organization(
                name=org_name,
                slug=slug,
                plan='free',
                max_users=5,
                max_projects=25,
            )
            db.add(org)
            db.flush()

            # Create owner user
            user = User(
                org_id=org.id,
                email=email,
                password_hash=generate_password_hash(password),
                full_name=full_name.strip() or email.split('@')[0],
                role='owner',
                is_active=True,
                is_verified=True,  # Auto-verify first user
            )
            db.add(user)
            db.flush()

            # Create default workspace
            ws = Workspace(
                org_id=org.id,
                name='Default Workspace',
                description='Your first workspace. Rename or create more as needed.',
                color='#3b82f6',
                created_by_user_id=user.id,
            )
            db.add(ws)
            db.flush()

            # Add owner as workspace member
            membership = WorkspaceMembership(
                workspace_id=ws.id,
                user_id=user.id,
                role='owner',
            )
            db.add(membership)

            db.commit()
            db.refresh(user)
            
            logger.info(f"✅ New org registered: {org_name} ({email})")
            return user.to_dict(), None

        except Exception as e:
            db.rollback()
            logger.exception(f"Registration failed: {e}")
            return None, f"Registration failed: {str(e)}"
        finally:
            db.close()

    @staticmethod
    def accept_invitation(token, password, full_name):
        """Accept an invitation and create user account."""
        if not token or not password:
            return None, "Missing invitation token or password"

        db = get_db()
        try:
            inv = db.query(Invitation).filter(Invitation.token == token).first()
            if not inv:
                return None, "Invalid or expired invitation"
            
            if inv.accepted_at:
                return None, "Invitation already used"
            
            if inv.expires_at and inv.expires_at < datetime.utcnow():
                return None, "Invitation has expired"
            
            existing = db.query(User).filter(User.email == inv.email).first()
            if existing:
                return None, "This email already has an account. Please log in."

            user = User(
                org_id=inv.org_id,
                email=inv.email,
                password_hash=generate_password_hash(password),
                full_name=full_name.strip() or inv.email.split('@')[0],
                role=inv.role,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            
            inv.accepted_at = datetime.utcnow()
            
            db.commit()
            db.refresh(user)
            
            return user.to_dict(), None
        except Exception as e:
            db.rollback()
            logger.exception(f"Invitation accept failed: {e}")
            return None, str(e)
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # LOGIN
    # ═══════════════════════════════════════════

    @staticmethod
    def login(email, password):
        """
        Verify credentials and return user dict.
        Returns (user_dict, error_message).
        """
        if not email or not password:
            return None, "Email and password required"

        email = email.strip().lower()
        db = get_db()
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return None, "Invalid email or password"
            
            if not user.is_active:
                return None, "Account is disabled. Contact your organization admin."
            
            if not user.password_hash:
                return None, "This account uses SSO. Please log in with your SSO provider."
            
            if not check_password_hash(user.password_hash, password):
                return None, "Invalid email or password"
            
            # Update last_login
            user.last_login = datetime.utcnow()
            db.commit()
            db.refresh(user)
            
            logger.info(f"🔐 Login: {email}")
            return user.to_dict(), None
        except Exception as e:
            db.rollback()
            logger.exception(f"Login failed: {e}")
            return None, str(e)
        finally:
            db.close()

    @staticmethod
    def get_user_by_id(user_id):
        db = get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            return user.to_dict() if user else None
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # INVITATIONS
    # ═══════════════════════════════════════════

    @staticmethod
    def create_invitation(org_id, email, role, inviter_user_id):
        """Create an email invitation. Returns invitation link."""
        if role not in ('admin', 'manager', 'viewer'):
            return None, "Invalid role"

        email = email.strip().lower()
        if not AuthService._is_valid_email(email):
            return None, "Invalid email"

        db = get_db()
        try:
            existing_user = db.query(User).filter(User.email == email).first()
            if existing_user:
                return None, "This email already has an account"

            # Delete any old pending invites for the same email+org
            db.query(Invitation).filter(
                Invitation.org_id == org_id,
                Invitation.email == email,
                Invitation.accepted_at.is_(None)
            ).delete()

            token = uuid.uuid4().hex + uuid.uuid4().hex  # 64 chars
            inv = Invitation(
                org_id=org_id,
                email=email,
                role=role,
                token=token,
                invited_by_user_id=inviter_user_id,
                expires_at=datetime.utcnow() + timedelta(days=14),
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)
            
            return {'token': token, 'email': email, 'role': role, 'expires_at': inv.expires_at.isoformat()}, None
        except Exception as e:
            db.rollback()
            logger.exception(f"Invitation failed: {e}")
            return None, str(e)
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # USER MANAGEMENT
    # ═══════════════════════════════════════════

    @staticmethod
    def list_org_users(org_id):
        db = get_db()
        try:
            users = db.query(User).filter(User.org_id == org_id).order_by(User.created_at).all()
            return [u.to_dict() for u in users]
        finally:
            db.close()

    @staticmethod
    def update_user_role(user_id, new_role, actor_user_id):
        if new_role not in ('owner', 'admin', 'manager', 'viewer'):
            return False, "Invalid role"

        db = get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "User not found"
            
            # Owner cannot demote themselves if they're the last owner
            if user.role == 'owner' and new_role != 'owner':
                other_owners = db.query(User).filter(
                    User.org_id == user.org_id,
                    User.role == 'owner',
                    User.id != user.id
                ).count()
                if other_owners == 0:
                    return False, "Cannot remove the last owner"

            user.role = new_role
            db.commit()
            logger.info(f"🎭 Role changed for user {user.email}: {new_role} (by {actor_user_id})")
            return True, None
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    @staticmethod
    def deactivate_user(user_id, actor_user_id):
        db = get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, "User not found"
            
            if user.role == 'owner':
                other_owners = db.query(User).filter(
                    User.org_id == user.org_id,
                    User.role == 'owner',
                    User.id != user.id,
                    User.is_active == True
                ).count()
                if other_owners == 0:
                    return False, "Cannot deactivate the last active owner"

            user.is_active = False
            db.commit()
            return True, None
        except Exception as e:
            db.rollback()
            return False, str(e)
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # WORKSPACES
    # ═══════════════════════════════════════════

    @staticmethod
    def list_workspaces(org_id, user_id=None):
        """List workspaces user has access to."""
        db = get_db()
        try:
            # For simplicity: all users in org can see all workspaces (fine-grained WS mgmt in future)
            workspaces = db.query(Workspace).filter(Workspace.org_id == org_id).order_by(Workspace.name).all()
            return [ws.to_dict() for ws in workspaces]
        finally:
            db.close()

    @staticmethod
    def create_workspace(org_id, name, description, color, user_id):
        db = get_db()
        try:
            ws = Workspace(
                org_id=org_id,
                name=name,
                description=description or '',
                color=color or '#3b82f6',
                created_by_user_id=user_id,
            )
            db.add(ws)
            db.flush()
            
            # Auto-add creator as member
            membership = WorkspaceMembership(workspace_id=ws.id, user_id=user_id, role='admin')
            db.add(membership)
            
            db.commit()
            db.refresh(ws)
            return ws.to_dict(), None
        except Exception as e:
            db.rollback()
            return None, str(e)
        finally:
            db.close()

    # ═══════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════

    @staticmethod
    def _is_valid_email(email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def _slugify(name):
        s = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
        s = re.sub(r'\s+', '-', s.strip())
        return s[:80] or 'org'
