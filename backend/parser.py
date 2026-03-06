"""Subscription content parser — converts raw subscription data into Mihomo proxy dicts."""

import base64
import json
import re
from urllib.parse import urlparse, parse_qs, unquote


def fetch_and_parse(content: str) -> list[dict]:
    """Parse subscription content into a list of Mihomo proxy dicts.

    Tries Clash YAML first, then base64 decode, then raw URI lines.
    """
    content = content.strip()

    # 1. Try Clash YAML (look for "proxies" key)
    try:
        import yaml
        data = yaml.safe_load(content)
        if isinstance(data, dict) and "proxies" in data:
            proxies = data["proxies"]
            if isinstance(proxies, list):
                return [p for p in proxies if isinstance(p, dict)]
    except Exception:
        pass

    # 2. Try base64 decode
    try:
        decoded = base64.b64decode(content + "==").decode("utf-8", errors="ignore")
        if "://" in decoded:
            content = decoded
    except Exception:
        pass

    # 3. Parse as URI lines
    lines = content.splitlines()
    results = []
    for line in lines:
        line = line.strip()
        if not line or not "://" in line:
            continue
        proxy = _parse_uri(line)
        if proxy:
            results.append(proxy)
    return results


def _parse_uri(uri: str) -> dict | None:
    """Route to protocol-specific parser based on URI prefix."""
    uri = uri.strip()
    if uri.startswith("vmess://"):
        return _parse_vmess(uri)
    elif uri.startswith("vless://"):
        return _parse_vless(uri)
    elif uri.startswith("trojan://"):
        return _parse_trojan(uri)
    elif uri.startswith("ss://"):
        return _parse_ss(uri)
    elif uri.startswith("ssr://"):
        return _parse_ssr(uri)
    elif uri.startswith("hysteria2://") or uri.startswith("hy2://"):
        return _parse_hysteria2(uri)
    return None


def _parse_vmess(uri: str) -> dict | None:
    """Decode base64 JSON after vmess://. Extract Mihomo fields."""
    try:
        raw = uri[len("vmess://"):]
        # Add padding if needed
        raw = raw + "=" * (-len(raw) % 4)
        data = json.loads(base64.b64decode(raw).decode("utf-8", errors="ignore"))

        proxy = {
            "name": data.get("ps", "vmess"),
            "type": "vmess",
            "server": data.get("add", ""),
            "port": int(data.get("port", 0)),
            "uuid": data.get("id", ""),
            "alterId": int(data.get("aid", 0)),
            "cipher": data.get("scy", "auto"),
        }

        net = data.get("net", "")
        tls = data.get("tls", "")

        if tls:
            proxy["tls"] = True
            sni = data.get("sni", "")
            if sni:
                proxy["servername"] = sni

        if net == "ws":
            proxy["network"] = "ws"
            ws_opts = {}
            path = data.get("path", "")
            if path:
                ws_opts["path"] = path
            host = data.get("host", "")
            if host:
                ws_opts["headers"] = {"Host": host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        elif net == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = {}
            grpc_service = data.get("path", "")
            if grpc_service:
                grpc_opts["grpc-service-name"] = grpc_service
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts
        elif net and net != "tcp":
            proxy["network"] = net

        return proxy
    except Exception:
        return None


def _parse_vless(uri: str) -> dict | None:
    """Parse vless://uuid@host:port?params#name."""
    try:
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)

        def param(key: str, default: str = "") -> str:
            return params.get(key, [default])[0]

        proxy = {
            "name": unquote(parsed.fragment) or "vless",
            "type": "vless",
            "server": parsed.hostname or "",
            "port": parsed.port or 0,
            "uuid": parsed.username or "",
        }

        security = param("security")
        if security == "tls":
            proxy["tls"] = True
            sni = param("sni")
            if sni:
                proxy["servername"] = sni
            fp = param("fp")
            if fp:
                proxy["client-fingerprint"] = fp
        elif security == "reality":
            proxy["tls"] = True
            proxy["reality-opts"] = {}
            sni = param("sni")
            if sni:
                proxy["servername"] = sni
            pbk = param("pbk")
            if pbk:
                proxy["reality-opts"]["public-key"] = pbk
            sid = param("sid")
            if sid:
                proxy["reality-opts"]["short-id"] = sid
            fp = param("fp")
            if fp:
                proxy["client-fingerprint"] = fp

        net_type = param("type", "tcp")
        if net_type == "ws":
            proxy["network"] = "ws"
            ws_opts = {}
            path = param("path")
            if path:
                ws_opts["path"] = unquote(path)
            host = param("host")
            if host:
                ws_opts["headers"] = {"Host": host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        elif net_type == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = {}
            service = param("serviceName")
            if service:
                grpc_opts["grpc-service-name"] = service
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts
        elif net_type and net_type != "tcp":
            proxy["network"] = net_type

        flow = param("flow")
        if flow:
            proxy["flow"] = flow

        return proxy
    except Exception:
        return None


def _parse_trojan(uri: str) -> dict | None:
    """Parse trojan://password@host:port?params#name."""
    try:
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)

        def param(key: str, default: str = "") -> str:
            return params.get(key, [default])[0]

        proxy = {
            "name": unquote(parsed.fragment) or "trojan",
            "type": "trojan",
            "server": parsed.hostname or "",
            "port": parsed.port or 0,
            "password": unquote(parsed.username or ""),
        }

        sni = param("sni") or param("peer")
        if sni:
            proxy["sni"] = sni

        net_type = param("type", "tcp")
        if net_type == "ws":
            proxy["network"] = "ws"
            ws_opts = {}
            path = param("path")
            if path:
                ws_opts["path"] = unquote(path)
            host = param("host")
            if host:
                ws_opts["headers"] = {"Host": host}
            if ws_opts:
                proxy["ws-opts"] = ws_opts
        elif net_type == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = {}
            service = param("serviceName")
            if service:
                grpc_opts["grpc-service-name"] = service
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts

        return proxy
    except Exception:
        return None


def _parse_ss(uri: str) -> dict | None:
    """Parse SIP002 format ss://base64(method:password)@host:port#name
    or ss://base64(method:password@host:port)#name.
    """
    try:
        rest = uri[len("ss://"):]

        # Extract fragment (name)
        name = "ss"
        if "#" in rest:
            rest, fragment = rest.rsplit("#", 1)
            name = unquote(fragment)

        # SIP002 format: base64@host:port
        if "@" in rest:
            userinfo, hostport = rest.rsplit("@", 1)
            # Decode userinfo
            try:
                userinfo = base64.b64decode(userinfo + "==").decode("utf-8", errors="ignore")
            except Exception:
                pass
            if ":" not in userinfo:
                return None
            method, password = userinfo.split(":", 1)
            # Parse host:port
            parsed = urlparse(f"ss://{hostport}")
            server = parsed.hostname or hostport.split(":")[0]
            port = parsed.port or int(hostport.split(":")[-1])
        else:
            # Legacy: entire thing is base64
            decoded = base64.b64decode(rest + "==").decode("utf-8", errors="ignore")
            if "@" not in decoded:
                return None
            userinfo, hostport = decoded.rsplit("@", 1)
            method, password = userinfo.split(":", 1)
            server = hostport.split(":")[0]
            port = int(hostport.split(":")[1])

        return {
            "name": name,
            "type": "ss",
            "server": server,
            "port": port,
            "cipher": method,
            "password": password,
        }
    except Exception:
        return None


def _parse_ssr(uri: str) -> dict | None:
    """Decode base64 after ssr://, split by : to get server, port, protocol, method, obfs, password."""
    try:
        raw = uri[len("ssr://"):]
        decoded = base64.b64decode(raw + "==").decode("utf-8", errors="ignore")

        # Format: server:port:protocol:method:obfs:password_base64/?params
        main_part = decoded.split("/?")[0]
        parts = main_part.split(":")
        if len(parts) < 6:
            return None

        server = parts[0]
        port = int(parts[1])
        protocol = parts[2]
        method = parts[3]
        obfs = parts[4]
        password_b64 = parts[5]

        try:
            password = base64.b64decode(password_b64 + "==").decode("utf-8", errors="ignore")
        except Exception:
            password = password_b64

        # Extract name from params if available
        name = "ssr"
        if "/?" in decoded:
            param_str = decoded.split("/?")[1]
            param_pairs = parse_qs(param_str)
            remarks_b64 = param_pairs.get("remarks", [""])[0]
            if remarks_b64:
                try:
                    name = base64.b64decode(remarks_b64 + "==").decode("utf-8", errors="ignore")
                except Exception:
                    name = remarks_b64

        return {
            "name": name,
            "type": "ssr",
            "server": server,
            "port": port,
            "cipher": method,
            "password": password,
            "protocol": protocol,
            "obfs": obfs,
        }
    except Exception:
        return None


def _parse_hysteria2(uri: str) -> dict | None:
    """Parse hysteria2://password@host:port?params#name (also hy2://)."""
    try:
        # Normalize prefix
        if uri.startswith("hy2://"):
            uri = "hysteria2://" + uri[len("hy2://"):]

        parsed = urlparse(uri)
        params = parse_qs(parsed.query)

        def param(key: str, default: str = "") -> str:
            return params.get(key, [default])[0]

        proxy = {
            "name": unquote(parsed.fragment) or "hysteria2",
            "type": "hysteria2",
            "server": parsed.hostname or "",
            "port": parsed.port or 0,
            "password": unquote(parsed.username or ""),
        }

        sni = param("sni")
        if sni:
            proxy["sni"] = sni

        insecure = param("insecure")
        if insecure == "1":
            proxy["skip-cert-verify"] = True

        obfs = param("obfs")
        if obfs:
            proxy["obfs"] = obfs
            obfs_password = param("obfs-password")
            if obfs_password:
                proxy["obfs-password"] = obfs_password

        return proxy
    except Exception:
        return None
