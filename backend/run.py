import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=int(os.getenv("SENTINEL_PORT", "8733")),
        workers=1,
        proxy_headers=True,
        server_header=False,
        access_log=os.getenv("ACCESS_LOG", "false").lower() == "true",
    )
