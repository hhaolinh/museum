"""Private loopback service launched and stopped by the native macOS host."""
import os
import signal
import sys
import threading
import time
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    if not os.environ.get('CABINET_DATA_DIR') or len(os.environ.get('CABINET_DESKTOP_TOKEN', '')) < 32:
        raise RuntimeError('The desktop service must be started by Cabinet.')
    from waitress import create_server
    from app import app
    server = create_server(app, host='127.0.0.1', port=0, threads=4, clear_untrusted_proxy_headers=True)

    def stop(_signal=None, _frame=None):
        server.close()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    parent = int(os.environ.get('CABINET_PARENT_PID', '0'))
    if parent > 1:
        def watch_parent():
            while True:
                time.sleep(2)
                try:
                    os.kill(parent, 0)
                except ProcessLookupError:
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
        threading.Thread(target=watch_parent, daemon=True).start()
    print(f'CABINET_READY {server.effective_port}', flush=True)
    try:
        server.run()
    finally:
        server.close()


if __name__ == '__main__':
    main()
