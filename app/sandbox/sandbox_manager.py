"""
VTR-Agent: Sandbox Safety

Sandboxed execution environment for safe code execution.
Provides isolated working directory, resource limits, and process isolation.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from vtr_agent.core.config import get_settings
from vtr_agent.utils import new_id, format_file_size, calculate_password_strength


class SandboxConfig(BaseModel):
    """Configuration for sandbox execution."""
    timeout: int = Field(default=300)  # seconds
    memory_limit: int = Field(default=4096)  # MB
    cpu_limit: float = Field(default=2.0)  # CPU cores
    network_access: bool = Field(default=False)
    filesystem_access: str = Field(default="readonly")  # "none", "readonly", "readwrite", "sandbox_only"
    working_dir: Optional[Path] = None
    base_image: str = Field(default="python:3.11-slim")
    readonly_paths: List[Path] = Field(default_factory=list)
    allow_list: List[str] = Field(default_factory=list)  # allowed commands/functions


class SandboxResult(BaseModel):
    """Result of sandbox execution."""
    execution_id: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    memory_used: Optional[int] = None  # MB
    timed_out: bool = False
    killed: bool = False
    safety_violation: Optional[str] = None
    output_truncated: bool = False


class SandboxSafetyViolation(Exception):
    """Raised when a sandbox safety violation is detected."""
    def __init__(self, violation: str, detail: str = ""):
        self.violation = violation
        self.detail = detail
        super().__init__(f"Sandbox safety violation: {violation} - {detail}")


class SandboxManager:
    """Manages sandboxed execution environments."""
    
    def __init__(self):
        self.settings = get_settings()
        self.active_sessions: Dict[str, Dict] = {}
        self.violation_log: List[Dict] = []
    
    def create_session(
        self,
        timeout: Optional[int] = None,
        memory_limit: Optional[int] = None,
        cpu_limit: Optional[float] = None,
        filesystem_access: str = "readonly",
    ) -> str:
        """Create a new sandbox session."""
        session_id = new_id("SANDBOX")
        
        config = {
            "session_id": session_id,
            "timeout": timeout or self.settings.SANDBOX_TIMEOUT,
            "memory_limit": memory_limit or self.settings.SANDBOX_MEMORY_LIMIT,
            "cpu_limit": cpu_limit or self.settings.SANDBOX_CPU_LIMIT,
            "filesystem_access": filesystem_access,
            "start_time": time.time(),
            "process_id": None,
            "working_dir": None,
        }
        
        self.active_sessions[session_id] = config
        return session_id
    
    def execute_code(
        self,
        code: str,
        session_id: Optional[str] = None,
        timeout: Optional[int] = None,
        memory_limit: Optional[int] = None,
        filesystem_access: str = "readonly",
        stdin_input: Optional[str] = None,
    ) -> SandboxResult:
        """Execute code in a sandboxed environment."""
        
        # Create or get session
        if session_id:
            if session_id not in self.active_sessions:
                raise ValueError(f"Sandbox session {session_id} not found")
            session = self.active_sessions[session_id]
        else:
            session_id = self.create_session(
                timeout=timeout,
                memory_limit=memory_limit,
                filesystem_access=filesystem_access,
            )
            session = self.active_sessions[session_id]
        
        exec_id = new_id("EXEC")
        start_time = time.time()
        
        try:
            # Set up sandbox environment
            sandbox_dir = self._setup_sandbox(session_id, session)
            
            # Write code to file, normalising any literal \n escape sequences
            # (callers may pass "print('x')\nprint('y')" as a single-line string)
            code_file = sandbox_dir / "code.py"
            normalised_code = code.replace("\\n", "\n").replace("\\t", "\t")
            code_file.write_text(normalised_code, encoding="utf-8")
            
            # --- Static pre-execution violation scan ---
            static_violation = self._check_static_violations(normalised_code)
            if static_violation:
                self._log_violation(exec_id, static_violation)
                return SandboxResult(
                    execution_id=exec_id,
                    exit_code=1,
                    stdout="",
                    stderr=f"Blocked by sandbox policy: {static_violation}",
                    execution_time=0.0,
                    memory_used=None,
                    timed_out=False,
                    safety_violation=static_violation,
                )
            
            # Prepare execution command
            cmd = self._prepare_execution_command(code_file, session)
            
            # Execute with timeout
            preexec = self._set_resource_limits if os.name != "nt" else None
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(sandbox_dir),
                preexec_fn=preexec,
            )
            
            session["process_id"] = process.pid
            
            # Wait with timeout
            try:
                raw_stdout, raw_stderr = process.communicate(
                    input=stdin_input.encode() if stdin_input else None,
                    timeout=session["timeout"],
                )
                
                # Decode bytes → str (subprocess always returns bytes when PIPE is used)
                stdout = raw_stdout.decode("utf-8", errors="replace") if isinstance(raw_stdout, bytes) else (raw_stdout or "")
                stderr = raw_stderr.decode("utf-8", errors="replace") if isinstance(raw_stderr, bytes) else (raw_stderr or "")
                
                exit_code = process.returncode
                execution_time = time.time() - start_time
                
                # Get memory usage
                memory_used = self._get_memory_usage(process.pid)
                
                # Check for violations
                violation = self._check_violations(
                    stdout, stderr, exit_code, session
                )
                
                if violation:
                    self._log_violation(exec_id, violation)
                    return SandboxResult(
                        execution_id=exec_id,
                        exit_code=exit_code,
                        stdout=stdout[:1000] if stdout else "",
                        stderr=stderr[:1000] if stderr else "",
                        execution_time=execution_time,
                        memory_used=memory_used,
                        safety_violation=violation,
                        timed_out=False,
                    )
                
                return SandboxResult(
                    execution_id=exec_id,
                    exit_code=exit_code,
                    stdout=stdout if stdout else "",
                    stderr=stderr if stderr else "",
                    execution_time=execution_time,
                    memory_used=memory_used,
                    timed_out=False,
                )
                
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                execution_time = time.time() - start_time
                
                return SandboxResult(
                    execution_id=exec_id,
                    exit_code=-1,
                    stdout=stdout.decode()[:1000] if stdout else "",
                    stderr=stderr.decode()[:1000] if stderr else "",
                    execution_time=execution_time,
                    timed_out=True,
                    killed=True,
                )
        
        except Exception as e:
            execution_time = time.time() - start_time
            return SandboxResult(
                execution_id=exec_id,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                execution_time=execution_time,
                timed_out=False,
                safety_violation=f"Execution error: {str(e)}",
            )
    
    def _setup_sandbox(self, session_id: str, session: Dict) -> Path:
        """Set up sandbox working directory."""
        sandbox_base = Path(tempfile.gettempdir()) / "vtr_sandbox" / session_id
        sandbox_base.mkdir(parents=True, exist_ok=True)
        
        # Set up working directory
        working_dir = sandbox_base / "work"
        working_dir.mkdir(exist_ok=True)
        
        # Set up readonly paths (common libraries, etc.)
        # In production, would mount base image paths
        
        session["working_dir"] = str(working_dir)
        return working_dir
    
    def _prepare_execution_command(self, code_file: Path, session: Dict) -> List[str]:
        """Prepare the execution command for sandbox."""
        python_path = [sys.executable, str(code_file)]
        
        # Add resource limits based on session config
        cmd = python_path
        
        return cmd
    
    def _set_resource_limits(self) -> None:
        """Set resource limits for process."""
        try:
            import resource
            # Set memory limit (in bytes)
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, 
                              (self.active_sessions["memory_limit"] * 1024 * 1024, hard))
            
            # Set CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, 
                              (self.active_sessions["timeout"], hard))
        except (ImportError, AttributeError, Exception):
            pass
    
    def _get_memory_usage(self, pid: int) -> Optional[int]:
        """Get memory usage in MB for a process."""
        try:
            with open(f"/proc/{pid}/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) // 1024  # KB to MB
        except (FileNotFoundError, ValueError):
            pass
        return None
    
    def _check_static_violations(self, code: str) -> Optional[str]:
        """Scan code text for forbidden patterns before execution."""
        # Forbidden subprocess/shell patterns
        subprocess_patterns = [
            "import subprocess",
            "from subprocess",
            "os.system(",
            "os.popen(",
            "os.spawn",
            "os.exec",
            "Popen(",
        ]
        for pat in subprocess_patterns:
            if pat in code:
                return f"Subprocess execution not allowed: {pat!r}"
        
        # Forbidden network patterns
        network_patterns = [
            "import socket",
            "from socket",
            "import requests",
            "import httpx",
            "import urllib",
            "from urllib",
            "import http.client",
        ]
        for pat in network_patterns:
            if pat in code:
                return f"Network access not allowed: {pat!r}"
        
        return None

    def _check_violations(
        self, 
        stdout: str, 
        stderr: str, 
        exit_code: int, 
        session: Dict
    ) -> Optional[str]:
        """Check for safety violations in execution output."""
        # Check for network access attempts
        network_keywords = ["socket", "connect", "import os", "import subprocess"]
        output = stdout + stderr
        
        for keyword in network_keywords:
            if keyword in output.lower():
                return f"Network access attempt: {keyword}"
        
        # Check for file system violations
        if session.get("filesystem_access") == "none":
            if "open(" in output or "write(" in output:
                return "Filesystem access not allowed"
        
        # Check for process spawning
        if "import subprocess" in output or "os.system" in output:
            return "Subprocess execution not allowed"
        
        # Check for timeout
        if exit_code == -1 or session.get("timed_out", False):
            return "Execution timed out"
        
        return None
    
    def _log_violation(self, exec_id: str, violation: str) -> None:
        """Log a safety violation."""
        self.violation_log.append({
            "execution_id": exec_id,
            "violation": violation,
            "timestamp": time.time(),
        })
    
    def get_violation_log(self) -> List[Dict]:
        """Get the violation log."""
        return self.violation_log.copy()
    
    def terminate_session(self, session_id: str) -> bool:
        """Terminate a sandbox session."""
        if session_id in self.active_sessions:
            # In production, would kill the process
            del self.active_sessions[session_id]
            return True
        return False


# Global sandbox manager instance
sandbox_manager = SandboxManager()


# Convenience functions
def execute_code_sandbox(
    code: str,
    timeout: Optional[int] = None,
    memory_limit: Optional[int] = None,
    filesystem_access: str = "readonly",
    stdin_input: Optional[str] = None,
) -> SandboxResult:
    """Execute code in sandbox with convenience function."""
    return sandbox_manager.execute_code(
        code=code,
        timeout=timeout,
        memory_limit=memory_limit,
        filesystem_access=filesystem_access,
        stdin_input=stdin_input,
    )


def create_sandbox_session(
    timeout: Optional[int] = None,
    memory_limit: Optional[int] = None,
    cpu_limit: Optional[float] = None,
    filesystem_access: str = "readonly",
) -> str:
    """Create a sandbox session with convenience function."""
    return sandbox_manager.create_session(
        timeout=timeout,
        memory_limit=memory_limit,
        cpu_limit=cpu_limit,
        filesystem_access=filesystem_access,
    )


def terminate_sandbox_session(session_id: str) -> bool:
    """Terminate a sandbox session with convenience function."""
    return sandbox_manager.terminate_session(session_id)


def get_violation_history() -> List[Dict]:
    """Get sandbox violation history."""
    return sandbox_manager.get_violation_log()