"""Flink health check client for dashboard."""
import aiohttp
from typing import Dict, List, Optional
from loguru import logger

from src.config import settings


class FlinkQueries:
    """Client for Flink health checks and job monitoring."""

    def __init__(self):
        self._base_url = settings.flink_ui_url

    async def check_health(self) -> Dict:
        """Check Flink JobManager health.
        
        Returns:
            Dict with health status and overview
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Get overview to check if JobManager is running
                async with session.get(
                    f"{self._base_url}/v1/overview",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'healthy': True,
                            'task_managers': data.get('taskmanagers', 0),
                            'slots_total': data.get('slots-total', 0),
                            'slots_available': data.get('slots-available', 0),
                            'jobs_running': data.get('jobs-running', 0),
                            'jobs_finished': data.get('jobs-finished', 0),
                            'jobs_cancelled': data.get('jobs-cancelled', 0),
                            'jobs_failed': data.get('jobs-failed', 0),
                        }
                    else:
                        return {
                            'healthy': False,
                            'error': f"HTTP {response.status}"
                        }
        except aiohttp.ClientError as e:
            logger.error(f"Flink health check failed: {e}")
            return {'healthy': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Flink health check failed: {e}")
            return {'healthy': False, 'error': str(e)}

    async def get_jobs(self) -> List[Dict]:
        """Get list of Flink jobs.
        
        Returns:
            List of job status dictionaries
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/v1/jobs",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('jobs', [])
                    return []
        except Exception as e:
            logger.error(f"Failed to get Flink jobs: {e}")
            return []

    async def get_job_details(self, job_id: str) -> Optional[Dict]:
        """Get details for a specific job.
        
        Args:
            job_id: Flink job ID
            
        Returns:
            Job details dict or None
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self._base_url}/v1/jobs/{job_id}",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except Exception as e:
            logger.error(f"Failed to get job details for {job_id}: {e}")
            return None

    async def check_jobs_health(self) -> Dict:
        """Check health of Flink jobs.
        
        Returns:
            Dict with job health status
        """
        jobs = await self.get_jobs()
        
        if not jobs:
            return {
                'healthy': False,
                'jobs_found': 0,
                'error': 'No jobs found'
            }
        
        job_statuses = {}
        running_count = 0
        failed_count = 0
        
        for job in jobs:
            job_id = job.get('id', 'unknown')
            status = job.get('status', 'UNKNOWN')
            job_statuses[job_id] = status
            
            if status == 'RUNNING':
                running_count += 1
            elif status == 'FAILED':
                failed_count += 1
        
        return {
            'healthy': running_count > 0 and failed_count == 0,
            'jobs_found': len(jobs),
            'running': running_count,
            'failed': failed_count,
            'job_statuses': job_statuses,
        }

    async def health_check(self) -> Dict:
        """Full health check combining JobManager and jobs.
        
        Returns:
            Dict with overall health status
        """
        jm_health = await self.check_health()
        jobs_health = await self.check_jobs_health()
        
        return {
            'healthy': jm_health.get('healthy', False) and jobs_health.get('healthy', False),
            'jobmanager': jm_health,
            'jobs': jobs_health,
        }
