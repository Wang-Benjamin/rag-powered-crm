from ..user_database import user_db, User, UserActivity
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class UserTracker:
    """Track user activities and store in user database"""
    
    def track_login(self, user_claims: Dict[str, Any]) -> None:
        """Track user login"""
        try:
            # Create or update user
            user = User(
                user_id=user_claims.get('sub', ''),
                email=user_claims.get('email', ''),
                name=user_claims.get('name', ''),
                avatar_url=user_claims.get('picture', ''),
                provider='google'
            )
            
            user_db.add_or_update_user(user)
            
            # Log login activity
            activity = UserActivity(
                user_id=user.user_id,
                activity_type='login',
                activity_data={
                    'timestamp': user_claims.get('iat'),
                    'provider': 'google',
                    'ip_address': None  # Could be added from request
                }
            )
            
            user_db.add_user_activity(activity)
            logger.info(f"Tracked login for user: {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to track user login: {e}")
    
    def track_activity(self, user_id: str, activity_type: str, activity_data: Dict[str, Any]) -> None:
        """Track general user activity"""
        try:
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                activity_data=activity_data
            )
            
            user_db.add_user_activity(activity)
            logger.info(f"Tracked activity '{activity_type}' for user: {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to track user activity: {e}")
    
    def track_crm_activity(self, user_id: str, action: str, customer_id: Optional[int] = None, details: Optional[Dict[str, Any]] = None) -> None:
        """Track CRM-related activities"""
        activity_data = {
            'action': action,
            'customer_id': customer_id,
            'details': details if details is not None else {}
        }
        
        self.track_activity(user_id, 'crm_activity', activity_data)
    
    def track_chat_activity(self, user_id: str, session_id: str, message_count: int = 1) -> None:
        """Track chat activities"""
        activity_data = {
            'session_id': session_id,
            'message_count': message_count
        }
        
        self.track_activity(user_id, 'chat_activity', activity_data)
    
    def track_calendar_activity(self, user_id: str, action: str, event_details: Optional[Dict[str, Any]] = None) -> None:
        """Track calendar activities"""
        activity_data = {
            'action': action,
            'event_details': event_details if event_details is not None else {}
        }
        
        self.track_activity(user_id, 'calendar_activity', activity_data)

# Global tracker instance
user_tracker = UserTracker() 