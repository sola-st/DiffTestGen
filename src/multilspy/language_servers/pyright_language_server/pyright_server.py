"""
Pyright language server adapter for multilspy.
This launches `pyright-langserver --stdio` and provides minimal initialize params.
"""

import json
import logging
import os
import pathlib
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from multilspy.multilspy_logger import MultilspyLogger
from multilspy.language_server import LanguageServer
from multilspy.lsp_protocol_handler.server import ProcessLaunchInfo
from multilspy.lsp_protocol_handler.lsp_types import InitializeParams
from multilspy.multilspy_config import MultilspyConfig
from multilspy.lsp_protocol_handler.lsp_constants import LSPConstants


class PyrightServer(LanguageServer):
    """
    Pyright-based Python Language Server.
    """

    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger, repository_root_path: str):
        # Allow overriding the pyright command via env var MULTILSP_PYRIGHT_CMD
        pyright_cmd = os.getenv("MULTILSP_PYRIGHT_CMD", "pyright-langserver --stdio")
        # start pyright language server in stdio mode
        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=pyright_cmd, cwd=repository_root_path),
            "python",
        )

    def _get_initialize_params(self, repository_absolute_path: str) -> InitializeParams:
        # Minimal initialize params compatible with pyright
        d: InitializeParams = {
            "processId": os.getpid(),
            "rootPath": repository_absolute_path,
            "rootUri": pathlib.Path(repository_absolute_path).as_uri(),
            "capabilities": {},
            "workspaceFolders": [
                {"uri": pathlib.Path(repository_absolute_path).as_uri(), "name": os.path.basename(repository_absolute_path)}
            ],
        }
        return d

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator["PyrightServer"]:
        # register a few handlers and start
        async def do_nothing(params):
            return

        async def window_log_message(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        async with super().start_server():
            self.logger.log("Starting pyright-langserver server process", logging.INFO)

            # Ensure a simple pyrightconfig.json exists so pyright indexes the workspace similarly to Pylance.
            try:
                cfg_path = os.path.join(self.repository_root_path, "pyrightconfig.json")
                if not os.path.exists(cfg_path):
                    extra_paths_env = os.getenv("MULTILSP_PYRIGHT_EXTRA_PATHS", "")
                    if extra_paths_env:
                        extra_paths = [p for p in extra_paths_env.split(os.pathsep) if p]
                    else:
                        # default helpful extra path for common repo layouts
                        extra_paths = ["src"]

                    py_ver = os.getenv("MULTILSP_PYTHON_VERSION", "3.11")
                    pyright_cfg = {
                        "executionEnvironments": [
                            {"root": ".", "extraPaths": extra_paths, "pythonVersion": py_ver}
                        ],
                        "typeCheckingMode": "basic",
                        "reportMissingImports": False,
                        "useLibraryCodeForTypes": True,
                    }
                    try:
                        with open(cfg_path, "w", encoding="utf-8") as _f:
                            json.dump(pyright_cfg, _f, indent=2)
                        self.logger.log(f"Wrote pyrightconfig.json to {cfg_path}", logging.INFO)
                    except Exception:
                        # non-fatal; continue without writing
                        pass
            except Exception:
                pass

            await self.server.start()
            initialize_params = self._get_initialize_params(self.repository_root_path)

            self.logger.log(
                "Sending initialize request from LSP client to pyright and awaiting response",
                logging.INFO,
            )
            try:
                # Be permissive about the initialize response since pyright capabilities differ from jedi
                init_response = await self.server.send.initialize(initialize_params)
            except Exception:
                init_response = None

            # notify initialized regardless; if server returned capabilities we don't assert on them
            try:
                self.server.notify.initialized({})
            except Exception:
                pass

            # Pre-open a small set of Python files under the repo so pyright will index them
            try:
                # determine search roots: use extraPaths if provided, otherwise repo root
                extra_paths_env = os.getenv("MULTILSP_PYRIGHT_EXTRA_PATHS", "")
                if extra_paths_env:
                    search_roots = [os.path.join(self.repository_root_path, p) for p in extra_paths_env.split(os.pathsep) if p]
                else:
                    search_roots = [self.repository_root_path]

                max_files = 300
                opened = 0
                for root in search_roots:
                    for dirpath, dirnames, filenames in os.walk(root):
                        for fn in filenames:
                            if not fn.endswith(".py"):
                                continue
                            abs_path = os.path.join(dirpath, fn)
                            rel = os.path.relpath(abs_path, self.repository_root_path)
                            rel_posix = pathlib.Path(rel).as_posix()
                            try:
                                # use LanguageServer.open_file context manager to open/close cleanly
                                with self.open_file(rel_posix):
                                    pass
                            except Exception:
                                # non-fatal
                                pass
                            opened += 1
                            if opened >= max_files:
                                break
                        if opened >= max_files:
                            break
                    if opened >= max_files:
                        break

                # give server a short time to process indexing
                await asyncio.sleep(0.8)
            except Exception:
                pass

            yield self

            try:
                await self.server.shutdown()
                await self.server.stop()
            except Exception:
                pass
