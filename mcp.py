# -*- coding: utf-8 -*-
"""
mcp.py — minimal MCP (Model Context Protocol) stdio client for Agent KH.
Spawns configured MCP servers, performs the JSON-RPC handshake,
lists their tools and calls them. Zero dependencies (stdlib only).

Config (config.json):
  "mcp_servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:/Users/you/Documents"]
    },
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "/tmp/test.db"]
    }
  }
"""
import json
import queue
import subprocess
import threading
import time

PROTOCOL_VERSION = "2024-11-05"


class MCPError(Exception):
    pass


class MCPClient:
    def __init__(self, name, command, args=None, env=None, timeout=30):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env
        self.timeout = timeout
        self._id = 0
        self._pending = {}
        self._lock = threading.Lock()
        self.proc = None
        self.tools = []

    def _next_id(self):
        self._id += 1
        return self._id

    def start(self):
        try:
            self.proc = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, bufsize=1,
                env=self.env)
        except FileNotFoundError:
            raise MCPError("command not found: %s" % self.command)
        threading.Thread(target=self._reader, daemon=True).start()
        # initialize handshake
        res = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "agentkh", "version": "3.0"},
        })
        if not isinstance(res, dict):
            raise MCPError("bad initialize response")
        self._notify("notifications/initialized", {})
        listed = self._request("tools/list", {})
        self.tools = (listed or {}).get("tools", [])
        return self.tools

    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            mid = msg.get("id")
            if mid is not None:
                with self._lock:
                    q = self._pending.pop(mid, None)
                if q is not None:
                    q.put(msg)
            # notifications without id are ignored

    def _request(self, method, params):
        mid = self._next_id()
        q = queue.Queue()
        with self._lock:
            self._pending[mid] = q
        payload = {"jsonrpc": "2.0", "id": mid,
                   "method": method, "params": params or {}}
        try:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise MCPError("server pipe broken")
        try:
            msg = q.get(timeout=self.timeout)
        except queue.Empty:
            raise MCPError("timeout waiting for %s" % method)
        if "error" in msg:
            raise MCPError(str(msg["error"])[:300])
        return msg.get("result")

    def _notify(self, method, params):
        try:
            self.proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "method": method,
                 "params": params or {}}) + "\n")
            self.proc.stdin.flush()
        except Exception:
            pass

    def call_tool(self, tool_name, arguments):
        res = self._request("tools/call", {"name": tool_name,
                                           "arguments": arguments or {}})
        parts = []
        for c in (res or {}).get("content", []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            elif c.get("type") == "image":
                parts.append("[image returned: %s]" %
                             (c.get("mimeType", "image")))
        text = "\n".join(parts)[:8000]
        if (res or {}).get("isError"):
            text = "MCP tool error: " + text
        return text or "(empty result)"

    def stop(self):
        try:
            if self.proc:
                self.proc.terminate()
        except Exception:
            pass


class MCPManager:
    """Owns all configured servers; exposes their tools in Agent KH format."""
    def __init__(self, servers_cfg):
        self.servers_cfg = servers_cfg or {}
        self.clients = {}
        self.errors = {}

    def start_all(self):
        for name, cfg in self.servers_cfg.items():
            if not isinstance(cfg, dict) or not cfg.get("command"):
                continue
            client = MCPClient(name, cfg["command"], cfg.get("args"),
                               cfg.get("env"))
            try:
                tools = client.start()
                self.clients[name] = client
                print("🔌 MCP '%s': %d tools" % (name, len(tools)))
            except Exception as e:
                self.errors[name] = str(e)[:160]
                print("⚠️ MCP '%s' failed: %s" % (name, str(e)[:120]))

    def tool_defs(self):
        """Agent KH-style tool defs. Names: mcp_<server>__<tool>."""
        defs = []
        for sname, client in self.clients.items():
            for t in client.tools:
                tname = "mcp_%s__%s" % (sname, t.get("name"))
                schema = t.get("inputSchema") or {"type": "object",
                                                  "properties": {}}
                defs.append({
                    "name": tname, "approval": True,
                    "desc": "[MCP:%s] %s" % (sname,
                                             t.get("description", "")[:200]),
                    "schema": schema,
                    "_mcp": (sname, t.get("name")),
                })
        return defs

    def call(self, server_name, tool_name, arguments):
        client = self.clients.get(server_name)
        if not client:
            raise MCPError("MCP server not connected: %s" % server_name)
        return client.call_tool(tool_name, arguments)

    def stop_all(self):
        for c in self.clients.values():
            c.stop()

    def status(self):
        return {"connected": sorted(self.clients.keys()),
                "failed": self.errors}
