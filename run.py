import uvicorn
import signal
import sys

def handle_exit(signum, frame):
    print("Received signal to terminate, shutting down gracefully")
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)
    
    # Start the uvicorn server
    uvicorn.run("app:app", host="0.0.0.0", port=8001, log_level="info")
