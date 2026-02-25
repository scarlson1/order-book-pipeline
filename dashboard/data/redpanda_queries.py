"""Redpanda health check client for dashboard."""
import asyncio
import socket
import aiohttp
from typing import Dict
from loguru import logger

from src.config import settings


class RedpandaQueries:
    """Client for Redpanda health checks and monitoring."""

    def __init__(self):
        self._base_url = settings.redpanda_admin_url
        self._kafka_port = settings.redpanda_kafka_port

    async def check_health(self) -> Dict:
        """Check Redpanda cluster health.
        
        Returns:
            Dict with health status and details
        """
        try:
            # Use the Admin API to check cluster health
            async with aiohttp.ClientSession() as session:
                # Try the cluster health endpoint
                async with session.get(
                    f"{self._base_url}/v1/cluster/health_overview",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            'healthy': data.get('is_healthy', False),
                            'controller_id': data.get('controller_id'),
                            'version': data.get('cluster_version'),
                        }
                    else:
                        return {
                            'healthy': False,
                            'error': f"HTTP {response.status}"
                        }
        except asyncio.TimeoutError:
            logger.warning("Redpanda health check timeout")
            return {'healthy': False, 'error': 'timeout'}
        except Exception as e:
            logger.error(f"Redpanda health check failed: {e}")
            return {'healthy': False, 'error': str(e)}

    async def get_broker_status(self) -> Dict:
        """Get broker connection status.
        
        Returns:
            Dict with broker info
        """
        try:
            # Check if we can connect to Kafka API
            host = self._base_url.replace("http://", "").replace("https://", "").split(":")[0]
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, self._kafka_port))
            sock.close()
            
            return {
                'connected': result == 0,
                'kafka_port': self._kafka_port,
                'host': host
            }
        except Exception as e:
            logger.error(f"Redpanda broker check failed: {e}")
            return {'connected': False, 'error': str(e)}

    async def health_check(self) -> Dict:
        """Full health check combining all checks.
        
        Returns:
            Dict with overall health status
        """
        health = await self.check_health()
        broker = await self.get_broker_status()
        
        return {
            'healthy': health.get('healthy', False) and broker.get('connected', False),
            'cluster': health,
            'broker': broker,
        }
