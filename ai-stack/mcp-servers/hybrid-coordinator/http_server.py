"""
http_server.py — R2.8 compatibility shim.

Phase R2.8 (Strangler Fig): all implementation code moved to http_server_impl.py.
This shim re-exports the public API (init, run_http_mode) so server.py and any
other callers continue to work without modification.

Route registration and middleware pipeline are owned by router.py / create_app().
Domain service modules own their own route handlers.

R2.9 (after nixos-rebuild + aq-qa 0 pass): delete this file and http_server_impl.py;
server.py imports router.create_app() and domain service configure() directly.
"""

from http_server_impl import init, run_http_mode  # noqa: F401
