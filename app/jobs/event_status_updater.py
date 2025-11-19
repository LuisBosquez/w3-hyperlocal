"""
Job to automatically update event statuses from 'active' to 'past'.
"""

from datetime import datetime, date, time
from .base_job import BaseJob


class EventStatusUpdater(BaseJob):
    """Job that updates event statuses based on scheduled date/time."""
    
    def __init__(self, supabase_client):
        super().__init__("EventStatusUpdater", supabase_client)
    
    def execute(self):
        """
        Check all active events and update their status to 'past' if
        the current datetime exceeds their scheduled datetime.
        
        Returns:
            dict: Execution result
        """
        if not self.supabase:
            return {
                'success': False,
                'message': 'Supabase client not available'
            }
        
        try:
            # Get all active events
            response = self.supabase.table('destinations').select(
                'id, scheduled_date, scheduled_time, status'
            ).eq('status', 'active').execute()
            
            if not response.data:
                return {
                    'success': True,
                    'message': 'No active events to check',
                    'data': {'updated': 0}
                }
            
            events = response.data
            now = datetime.now()
            updated_count = 0
            
            for event in events:
                # Skip cancelled events
                if event.get('status') == 'cancelled':
                    continue
                
                # Parse scheduled date
                scheduled_date = event.get('scheduled_date')
                if not scheduled_date:
                    continue
                
                # Parse scheduled time (can be None for all-day events)
                scheduled_time = event.get('scheduled_time')
                
                # Create datetime object for comparison
                if scheduled_time:
                    # Parse time string (format: HH:MM:SS or HH:MM)
                    time_parts = scheduled_time.split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    second = int(time_parts[2]) if len(time_parts) > 2 else 0
                    event_datetime = datetime.combine(
                        datetime.strptime(scheduled_date, '%Y-%m-%d').date(),
                        time(hour, minute, second)
                    )
                else:
                    # For all-day events, compare date only (end of day)
                    event_date = datetime.strptime(scheduled_date, '%Y-%m-%d').date()
                    event_datetime = datetime.combine(event_date, time(23, 59, 59))
                
                # Check if event is in the past
                if now > event_datetime:
                    # Update status to 'past'
                    update_response = self.supabase.table('destinations').update({
                        'status': 'past'
                    }).eq('id', event['id']).execute()
                    
                    if update_response.data:
                        updated_count += 1
            
            return {
                'success': True,
                'message': f'Updated {updated_count} event(s) to past status',
                'data': {
                    'checked': len(events),
                    'updated': updated_count
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error updating event statuses: {str(e)}',
                'error': str(e)
            }

