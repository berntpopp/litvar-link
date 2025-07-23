"""HTTP server entry point for LitVar-Link."""

import uvicorn

from litvar_link.app import app
from litvar_link.config import settings

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_config=None,  # Use our custom logging
        access_log=False,  # Disable uvicorn access log
    )
