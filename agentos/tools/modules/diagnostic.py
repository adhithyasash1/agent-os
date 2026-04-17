import os
import psutil
import time
from ..core import tool

_START_TIME = time.time()

@tool(
    name="system_diagnostic",
    description="Retrieve live diagnostic telemetry for the local host and agent runtime. Includes memory, CPU, and uptime.",
    args_schema={"type": "object", "properties": {}},
    profiles=["full"]
)
async def _diagnostic(args: dict, ctx: dict) -> dict:
    try:
        uptime_seconds = int(time.time() - _START_TIME)
        
        cpu_usage = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        
        return {
            "status": "ok",
            "output": {
                "process_uptime_seconds": uptime_seconds,
                "host_cpu_percent": cpu_usage,
                "host_memory_free_gb": round(mem.available / (1024 ** 3), 2),
                "host_memory_total_gb": round(mem.total / (1024 ** 3), 2),
                "pid": os.getpid()
            }
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
