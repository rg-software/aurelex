"""Minimal CONNECT forward proxy for reverse-tethering an offline test phone.

The phone has no internet (no SIM / rejected Wi-Fi), so Android's global
http_proxy is pointed at 127.0.0.1:PORT and that port is served by this
script over `adb reverse tcp:PORT tcp:PORT`. CONNECT tunnels bytes through
untouched, so the app's TLS handshake and certificate validation happen
end to end against the real host (GitHub Pages / release assets) — nothing
is intercepted, and no CA install is needed on the phone.

Usage (two shells, PC online, USB adb connected):

    python scripts/dev-connect-proxy.py 8888
    adb reverse tcp:8888 tcp:8888
    adb shell settings put global http_proxy 127.0.0.1:8888
    # ... use the app's "Add from remote" pane ...
    adb shell settings put global http_proxy :0
    adb reverse --remove tcp:8888

Stdlib only. Handles CONNECT (what HTTPS needs); anything else gets 405.
"""
import socket
import sys
import threading

BUF = 65536


def relay(src, dst):
    try:
        while True:
            data = src.recv(BUF)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass


def handle(conn):
    try:
        req = conn.recv(4096).decode("iso-8859-1")
        if not req:
            return
        line = req.splitlines()[0]
        parts = line.split()
        if len(parts) != 3 or parts[0] != "CONNECT":
            conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return
        target = parts[1]
        host, _, port = target.rpartition(":")
        if not host or not port.isdigit():
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return
        upstream = socket.create_connection((host, int(port)), timeout=10)
        conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        threading.Thread(target=relay, args=(conn, upstream), daemon=True).start()
        relay(upstream, conn)
        upstream.close()
    except Exception as exc:  # noqa: BLE001 - dev tool, log and drop
        print(f"proxy err: {exc}", flush=True)
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8888
    srv = socket.create_server(("127.0.0.1", port))
    print(f"CONNECT proxy listening on 127.0.0.1:{port}", flush=True)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    main()
