"""
Base job class for all background tasks.
"""

from abc import ABC, abstractmethod
from datetime import datetime


class BaseJob(ABC):
    """Base class for all background jobs."""
    
    def __init__(self, name, supabase_client):
        """
        Initialize the job.
        
        Args:
            name: Name of the job
            supabase_client: Supabase client instance
        """
        self.name = name
        self.supabase = supabase_client
        self.last_run = None
        self.run_count = 0
    
    @abstractmethod
    def execute(self):
        """
        Execute the job logic. Must be implemented by subclasses.
        
        Returns:
            dict: Job execution result with 'success', 'message', and optional 'data'
        """
        pass
    
    def run(self):
        """
        Run the job and update tracking information.
        
        Returns:
            dict: Job execution result
        """
        try:
            result = self.execute()
            self.last_run = datetime.now()
            self.run_count += 1
            return result
        except Exception as e:
            self.last_run = datetime.now()
            self.run_count += 1
            return {
                'success': False,
                'message': f"Job {self.name} failed: {str(e)}",
                'error': str(e)
            }
    
    def get_status(self):
        """Get current job status."""
        return {
            'name': self.name,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'run_count': self.run_count
        }

