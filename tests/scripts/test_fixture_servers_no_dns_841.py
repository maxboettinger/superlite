"""#841: the fixture HTTP servers bind without HTTPServer's reverse-DNS lookup (socket.getfqdn)."""
import subprocess
import sys

from _fixtures import FIXTURES

SCRIPT = r'''
import http.client, socket, sys, threading
def no_dns(*a, **k):
    raise AssertionError("socket.getfqdn called")
socket.getfqdn = no_dns
if sys.argv[1] == "probe":
    import fixture_site
    srv = fixture_site.create_server()
    path = "/echo"
else:
    from minisheet.server import create_server
    from minisheet.workbook import Workbook
    srv = create_server(Workbook())
    path = "/nope"
host, port = srv.server_address[:2]
assert (srv.server_name, srv.server_port) == (host, port), (srv.server_name, srv.server_port)
t = threading.Thread(target=srv.handle_request, daemon=True)
t.start()
conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
conn.request("GET", path)
print(conn.getresponse().status)
t.join(10)
srv.server_close()
'''


def _run(kind, src):
    return subprocess.run([sys.executable, "-c", SCRIPT, kind], cwd=src, capture_output=True, text=True, timeout=60)


def test_probe_fixture_binds_without_dns_841():
    r = _run("probe", FIXTURES / "probe_server" / "src")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["200"]


def test_minisheet_fixture_binds_without_dns_841():
    r = _run("sheet", FIXTURES / "review_basic" / "src")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["404"]
