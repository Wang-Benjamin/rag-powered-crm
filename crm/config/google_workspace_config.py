"""Configuration management for Google Workspace service account authentication."""

import os
import json
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class GoogleWorkspaceConfig:
    """Configuration for Google Workspace service account authentication."""
    
    service_account_path: Optional[str] = None
    service_account_info: Optional[dict] = None
    workspace_domain: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> 'GoogleWorkspaceConfig':
        """
        Load Google Workspace configuration from environment variables.
        
        Environment variables:
        - GOOGLE_SERVICE_ACCOUNT_PATH: Path to service account JSON file
        - GOOGLE_SERVICE_ACCOUNT_JSON: Base64 encoded service account JSON
        - GOOGLE_WORKSPACE_DOMAIN: Google Workspace domain name
        
        Returns:
            GoogleWorkspaceConfig instance
            
        Raises:
            ValueError: If no valid configuration found
        """
        # Try service account file path first
        service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
        if service_account_path:
            # Handle relative paths by making them absolute
            if not os.path.isabs(service_account_path):
                # Make relative to the project root (prelude-platform-new)
                current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # Go up to prelude-crm/src
                project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up to prelude-platform-new
                service_account_path = os.path.join(project_root, service_account_path)
            
            if os.path.exists(service_account_path):
                workspace_domain = os.getenv('GOOGLE_WORKSPACE_DOMAIN')
                if not workspace_domain:
                    raise ValueError("GOOGLE_WORKSPACE_DOMAIN environment variable required")
                    
                logger.info(f"Using service account file: {service_account_path}")
                return cls(
                    service_account_path=service_account_path,
                    workspace_domain=workspace_domain
                )
            else:
                logger.warning(f"Service account file not found at: {service_account_path}")
        
        # Try service account JSON from environment variable
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if service_account_json:
            try:
                import base64
                decoded_json = base64.b64decode(service_account_json).decode('utf-8')
                service_account_info = json.loads(decoded_json)
                
                workspace_domain = os.getenv('GOOGLE_WORKSPACE_DOMAIN')
                if not workspace_domain:
                    raise ValueError("GOOGLE_WORKSPACE_DOMAIN environment variable required")
                
                logger.info("Using service account JSON from environment variable")
                return cls(
                    service_account_info=service_account_info,
                    workspace_domain=workspace_domain
                )
            except Exception as e:
                logger.error(f"Failed to decode service account JSON from environment: {e}")
                raise ValueError(f"Invalid GOOGLE_SERVICE_ACCOUNT_JSON format: {e}")
        
        # Default local development path
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "secrets",
            "email-loading-service-account-key.json"
        )
        
        if os.path.exists(default_path):
            workspace_domain = os.getenv('GOOGLE_WORKSPACE_DOMAIN', 'preludeos.com')
            logger.info(f"Using default service account file: {default_path}")
            return cls(
                service_account_path=default_path,
                workspace_domain=workspace_domain
            )
        
        raise ValueError(
            "No Google Workspace service account configuration found. "
            "Set GOOGLE_SERVICE_ACCOUNT_PATH or GOOGLE_SERVICE_ACCOUNT_JSON environment variables."
        )
    
    def get_service_account_path(self) -> str:
        """
        Get service account file path, creating temporary file if using JSON info.
        
        Returns:
            Path to service account JSON file
        """
        if self.service_account_path:
            return self.service_account_path
        
        if self.service_account_info:
            # Create temporary file from JSON info
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                prefix='service_account_',
                delete=False
            )
            json.dump(self.service_account_info, temp_file, indent=2)
            temp_file.close()
            
            logger.info(f"Created temporary service account file: {temp_file.name}")
            return temp_file.name
        
        raise ValueError("No service account path or info available")
    
    def validate(self) -> bool:
        """
        Validate the configuration is complete and accessible.
        
        Returns:
            True if configuration is valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        if not self.workspace_domain:
            raise ValueError("Workspace domain is required")
        
        if not (self.service_account_path or self.service_account_info):
            raise ValueError("Service account path or info is required")
        
        if self.service_account_path and not os.path.exists(self.service_account_path):
            raise ValueError(f"Service account file not found: {self.service_account_path}")
        
        return True