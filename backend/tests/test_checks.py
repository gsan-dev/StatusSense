from __future__ import annotations

import asyncio

import dns.exception
import dns.resolver
import pytest

from app.checks.dns_check import check_dns
from app.checks.http_check import check_http
from app.checks.ping_check import _LATENCY_RE
from app.checks.tcp_check import check_tcp


async def test_check_http_success(local_http_server):
    host, port = local_http_server
    result = await check_http(f"http://{host}:{port}/", timeout_seconds=5)
    assert result.success is True
    assert result.http_status == 200
    assert result.latency_ms is not None


async def test_check_http_error_status(local_http_server):
    host, port = local_http_server
    result = await check_http(f"http://{host}:{port}/fail", timeout_seconds=5)
    assert result.success is False
    assert result.http_status == 500


async def test_check_http_connection_refused():
    result = await check_http("http://127.0.0.1:1/", timeout_seconds=2)
    assert result.success is False
    assert result.error_message is not None


async def test_check_tcp_success(local_http_server):
    host, port = local_http_server
    result = await check_tcp(f"{host}:{port}", timeout_seconds=5)
    assert result.success is True
    assert result.latency_ms is not None


async def test_check_tcp_invalid_target_format():
    result = await check_tcp("sin-puerto", timeout_seconds=2)
    assert result.success is False


async def test_check_tcp_connection_refused():
    result = await check_tcp("127.0.0.1:1", timeout_seconds=2)
    assert result.success is False


async def test_check_dns_success(monkeypatch):
    class FakeRdata:
        def to_text(self):
            return "192.168.0.1"

    def fake_resolve(self, target, rtype):
        return [FakeRdata()]

    monkeypatch.setattr(dns.resolver.Resolver, "resolve", fake_resolve)
    result = await check_dns("example.internal", timeout_seconds=5)
    assert result.success is True
    assert result.latency_ms is not None


async def test_check_dns_nxdomain(monkeypatch):
    def fake_resolve(self, target, rtype):
        raise dns.resolver.NXDOMAIN()

    monkeypatch.setattr(dns.resolver.Resolver, "resolve", fake_resolve)
    result = await check_dns("no-existe.invalid", timeout_seconds=5)
    assert result.success is False
    assert result.error_message == "NXDOMAIN"


def test_ping_latency_regex_parses_windows_output():
    sample = "Reply from 1.1.1.1: bytes=32 time=12ms TTL=57"
    match = _LATENCY_RE.search(sample)
    assert match is not None
    assert float(match.group(1)) == 12.0


def test_ping_latency_regex_parses_linux_output():
    sample = "64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=8.23 ms"
    match = _LATENCY_RE.search(sample)
    assert match is not None
    assert float(match.group(1)) == 8.23
