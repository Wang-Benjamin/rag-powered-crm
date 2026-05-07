"""Google Workspace authentication with domain-wide delegation for service accounts."""

import os
import json
from typing import Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)

class GoogleWorkspaceAuth:
    """Handle Google Workspace service account authentication with domain-wide delegation."""
    
    def __init__(self, service_account_path: str, workspace_domain: str):
        """
        Initialize Google Workspace authentication.
        
        Args:
            service_account_path: Path to service account JSON file
            workspace_domain: Google Workspace domain (e.g., 'prelude.com')
        """
        self.service_account_path = service_account_path
        self.workspace_domain = workspace_domain
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/admin.directory.user.readonly'
        ]
        
        # Validate service account file exists
        if not os.path.exists(service_account_path):
            raise FileNotFoundError(f"Service account file not found: {service_account_path}")
        
        logger.info(f"Initialized Google Workspace auth for domain: {workspace_domain}")
    
    def create_gmail_service(self, user_email: str):
        """
        Create Gmail service impersonating the specified user.
        
        Args:
            user_email: Email of user to impersonate
            
        Returns:
            Gmail API service object
            
        Raises:
            ValueError: If user email is not in workspace domain
            HttpError: If service account lacks domain-wide delegation permissions
        """
        # Validate user belongs to workspace domain
        if not user_email.endswith(f"@{self.workspace_domain}"):
            raise ValueError(f"User {user_email} not in workspace domain {self.workspace_domain}")
        
        try:
            # Load service account credentials
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=self.scopes
            )
            
            # Create delegated credentials for the user
            delegated_credentials = credentials.with_subject(user_email)
            
            # Build Gmail service
            gmail_service = build("gmail", "v1", credentials=delegated_credentials)
            
            logger.info(f"Created Gmail service for user: {user_email}")
            return gmail_service
            
        except Exception as e:
            logger.error(f"Failed to create Gmail service for {user_email}: {str(e)}")
            if "unauthorized_client" in str(e):
                raise HttpError(
                    resp=None,
                    content=f"Domain-wide delegation not configured for service account. "
                    f"Ensure service account has been authorized in Google Workspace Admin Console."
                )
            raise
    
    def create_admin_service(self, admin_email: str):
        """
        Create Admin SDK service for user directory operations.
        
        Args:
            admin_email: Email of admin user to impersonate
            
        Returns:
            Admin SDK Directory service object
        """
        if not admin_email.endswith(f"@{self.workspace_domain}"):
            raise ValueError(f"Admin {admin_email} not in workspace domain {self.workspace_domain}")
        
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=self.scopes
            )
            
            delegated_credentials = credentials.with_subject(admin_email)
            admin_service = build("admin", "directory_v1", credentials=delegated_credentials)
            
            logger.info(f"Created Admin service for admin: {admin_email}")
            return admin_service
            
        except Exception as e:
            logger.error(f"Failed to create Admin service for {admin_email}: {str(e)}")
            raise
    
    def validate_domain_access(self, test_email: str) -> bool:
        """
        Test if service account can access a user's Gmail (validation).
        
        Args:
            test_email: Email to test access for
            
        Returns:
            True if access successful, False otherwise
        """
        try:
            gmail_service = self.create_gmail_service(test_email)
            # Try to get user profile (minimal operation)
            profile = gmail_service.users().getProfile(userId='me').execute()
            logger.info(f"Domain access validated for {test_email}")
            return True
        except Exception as e:
            logger.warning(f"Domain access validation failed for {test_email}: {str(e)}")
            return False


class ServiceAccountAuthError(Exception):
    """Service account authentication failed."""
    pass


class DomainDelegationError(Exception):
    """Domain-wide delegation not configured properly."""
    pass