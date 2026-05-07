"""Microsoft 365 domain authentication for manager email sync"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import httpx
import json

logger = logging.getLogger(__name__)

class MicrosoftDomainAuth:
    """Microsoft 365 application permissions authentication"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        """
        Initialize Microsoft domain auth
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Application (client) ID
            client_secret: Client secret
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self.access_token = None
        self.token_expires_at = None
    
    async def get_access_token(self) -> str:
        """Get application access token with Mail.Read.All permission"""
        if self.access_token and self.token_expires_at and self.token_expires_at > datetime.now(timezone.utc):
            return self.access_token
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_url,
                    data={
                        'grant_type': 'client_credentials',
                        'client_id': self.client_id,
                        'client_secret': self.client_secret,
                        'scope': 'https://graph.microsoft.com/.default'
                    }
                )
                
                if response.status_code != 200:
                    raise Exception(f"Token request failed: {response.status_code} - {response.text}")
                
                token_data = response.json()
                self.access_token = token_data['access_token']
                expires_in = token_data.get('expires_in', 3600)
                self.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in - 300)  # 5 min buffer
                
                logger.info("Successfully obtained Microsoft Graph application token")
                return self.access_token
                
        except Exception as e:
            logger.error(f"Error getting Microsoft access token: {e}")
            raise
    
    async def get_domain_users(self, domain_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all users in the organization"""
        try:
            token = await self.get_access_token()
            
            async with httpx.AsyncClient() as client:
                url = f"{self.graph_url}/users"
                params = {
                    '$select': 'id,mail,userPrincipalName,displayName,department',
                    '$top': 999
                }
                
                if domain_filter:
                    params['$filter'] = f"endswith(mail,'{domain_filter}') or endswith(userPrincipalName,'{domain_filter}')"
                
                response = await client.get(
                    url,
                    params=params,
                    headers={'Authorization': f'Bearer {token}'}
                )
                
                if response.status_code != 200:
                    raise Exception(f"Users request failed: {response.status_code} - {response.text}")
                
                users = response.json().get('value', [])
                logger.info(f"Retrieved {len(users)} users from Microsoft Graph")
                return users
                
        except Exception as e:
            logger.error(f"Error getting domain users: {e}")
            return []
    
    async def get_user_emails(
        self, 
        user_id: str, 
        days_back: int = 30,
        max_results: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get emails for a specific user using application permissions
        
        Args:
            user_id: Microsoft Graph user ID
            days_back: Number of days back to retrieve emails
            max_results: Maximum number of emails to retrieve
            
        Returns:
            List of email data
        """
        try:
            token = await self.get_access_token()
            
            # Build date filter
            date_filter = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat().replace('+00:00', 'Z')
            
            async with httpx.AsyncClient() as client:
                url = f"{self.graph_url}/users/{user_id}/messages"
                params = {
                    '$select': 'id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,bodyPreview',
                    '$filter': f"receivedDateTime ge {date_filter}",
                    '$orderby': 'receivedDateTime desc',
                    '$top': min(max_results, 1000)  # Microsoft Graph limit
                }
                
                messages = []
                
                # Handle pagination
                while url and len(messages) < max_results:
                    response = await client.get(
                        url,
                        params=params if not messages else None,  # Only use params on first request
                        headers={'Authorization': f'Bearer {token}'}
                    )
                    
                    if response.status_code != 200:
                        logger.error(f"Messages request failed for user {user_id}: {response.text}")
                        break
                    
                    data = response.json()
                    batch_messages = data.get('value', [])
                    messages.extend(batch_messages)
                    
                    # Get next page URL
                    url = data.get('@odata.nextLink')
                    params = None  # Clear params for subsequent requests
                    
                    # Rate limiting
                    if len(batch_messages) > 0:
                        await asyncio.sleep(0.1)  # Small delay between requests
                
                logger.info(f"Retrieved {len(messages)} messages for user {user_id}")
                return messages[:max_results]  # Ensure we don't exceed max_results
                
        except Exception as e:
            logger.error(f"Error getting emails for user {user_id}: {e}")
            return []
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user information by email address"""
        try:
            token = await self.get_access_token()
            
            async with httpx.AsyncClient() as client:
                url = f"{self.graph_url}/users/{email}"
                response = await client.get(
                    url,
                    headers={'Authorization': f'Bearer {token}'}
                )
                
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"Found Microsoft user for {email}")
                    return user_data
                else:
                    logger.warning(f"Could not find Microsoft user for {email}: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting Microsoft user by email {email}: {e}")
            return None
    
    def validate_credentials(self) -> bool:
        """Validate that the Microsoft credentials are provided"""
        try:
            if not all([self.tenant_id, self.client_id, self.client_secret]):
                logger.error("Missing required Microsoft credentials")
                return False
            
            # Basic format validation
            if not self.tenant_id or len(self.tenant_id) < 10:
                logger.error("Invalid tenant_id format")
                return False
            
            if not self.client_id or len(self.client_id) < 10:
                logger.error("Invalid client_id format")
                return False
            
            if not self.client_secret or len(self.client_secret) < 10:
                logger.error("Invalid client_secret format")
                return False
            
            logger.info("Microsoft credentials validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Error validating Microsoft credentials: {e}")
            return False
    
    def parse_email_addresses(self, recipients: List[Dict]) -> List[str]:
        """Parse email addresses from Microsoft Graph recipients format"""
        emails = []
        if not recipients:
            return emails
        
        for recipient in recipients:
            if 'emailAddress' in recipient and 'address' in recipient['emailAddress']:
                emails.append(recipient['emailAddress']['address'].lower().strip())
        
        return emails
    
    def extract_email_body(self, message: Dict, prefer_text: bool = True) -> str:
        """Extract email body from Microsoft Graph message"""
        body = ""

        if message.get('body'):
            body_data = message['body']
            if body_data.get('contentType') == 'text' or prefer_text:
                body = body_data.get('content', '')
            else:
                # For HTML content, use bodyPreview as fallback
                body = message.get('bodyPreview', body_data.get('content', ''))

        return body  # Return full email body
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the Microsoft Graph connection"""
        try:
            logger.info("Testing Microsoft Graph connection...")
            
            # Try to get access token
            token = await self.get_access_token()
            
            # Try to get organization info
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.graph_url}/organization",
                    headers={'Authorization': f'Bearer {token}'}
                )
                
                if response.status_code == 200:
                    org_data = response.json()
                    org_info = org_data.get('value', [{}])[0]
                    
                    return {
                        'success': True,
                        'message': 'Microsoft Graph connection successful',
                        'organization': org_info.get('displayName', 'Unknown'),
                        'tenant_id': self.tenant_id
                    }
                else:
                    return {
                        'success': False,
                        'message': f'Failed to connect to Microsoft Graph: {response.text}'
                    }
                    
        except Exception as e:
            logger.error(f"Error testing Microsoft Graph connection: {e}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }

# Import asyncio at module level
import asyncio