#!/usr/bin/env python3
"""
Memory Profiler — NPU + CUDA Dual Backend.

Step 1: memory_stats() probes at key training points.
Step 2: memory._record_memory_history() + _snapshot() for full allocation trace.

Auto-detects available backend (NPU or CUDA) at import time.
No-op when neither is available.

Usage:
    from mem_profiler import (
        print_memory_breakdown,    # Step 1: allocated/reserved/frag breakdown
        reset_peak_stats,          # Reset peak tracking
        MemorySnapshot,            # Step 2: allocation trace context manager
    )

    # Step 1: probe at key points
    print_memory_breakdown("after-optimizer-init")
    reset_peak_stats()
    # ... training ...
    print_memory_breakdown("after-fwd-bwd-step1")

    # Step 2: capture allocation trace
    with MemorySnapshot(output_dir="./mem_snapshots", tag="step2"):
        loss = model(**batch).loss
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
"""

import os
import pickle
import torch


# ═══════════════════════════════════════════════════════════════════
# Backend Detection
# ═══════════════════════════════════════════════════════════════════

_BACKEND = None   # 'npu' | 'cuda' | None
_BACKEND_MODULE = None

try:
    import torch_npu  # noqa: F401
    _BACKEND = 'npu'
    _BACKEND_MODULE = torch.npu
except ImportError:
    pass

if _BACKEND is None:
    try:
        if torch.cuda.is_available():
            _BACKEND = 'cuda'
            _BACKEND_MODULE = torch.cuda
    except Exception:
        pass


def _get_backend():
    """Return ('npu'|'cuda'|None, module|None)."""
    return _BACKEND, _BACKEND_MODULE


def _check_available():
    """Raise RuntimeError if no backend available."""
    if _BACKEND is None:
        raise RuntimeError(
            "No NPU or CUDA available. mem_profiler requires torch_npu or torch.cuda."
        )


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _gb(val):
    """Bytes → GiB string, handles None/0 gracefully."""
    if not val:
        return "0.00 GiB"
    return f"{val / (1024**3):.2f} GiB"


# ═══════════════════════════════════════════════════════════════════
# Step 1: memory_stats() Breakdown
# ═══════════════════════════════════════════════════════════════════

def print_memory_breakdown(tag: str = "", device: int = 0):
    """
    Print detailed memory breakdown at current point.

    Call at key training points:
      - after model + optimizer init (baseline)
      - after forward (activation peak)
      - after backward (grad + activation peak)
      - after optimizer.step() (optimizer states)

    Works on NPU and CUDA.
    """
    _check_available()
    mod = _BACKEND_MODULE

    try:
        stats = mod.memory_stats(device)
    except Exception:
        print(f"[MEM #{device}] [{tag}] memory_stats() not available")
        return

    if not stats:
        print(f"[MEM #{device}] [{tag}] memory_stats() returned empty dict")
        return

    allocated = stats.get("allocated_bytes.all.current", 0)
    reserved  = stats.get("reserved_bytes.all.current", 0)
    active    = stats.get("active_bytes.all.current", 0)
    inactive  = stats.get("inactive_bytes.all.current", 0)
    max_alloc = mod.max_memory_allocated(device)
    max_resv  = mod.max_memory_reserved(device)

    frag = reserved - allocated

    sep = "=" * 64
    print(f"\n{sep}")
    print(f"  Memory Breakdown [{tag}]  (device={device}, backend={_BACKEND})")
    print(f"{sep}")
    print(f"  allocated  (tensors):    {_gb(allocated)}")
    print(f"  reserved   (cached):     {_gb(reserved)}")
    print(f"  ─────────────────────────────")
    print(f"  allocator overhead:      {_gb(frag)}")
    print(f"  ─────────────────────────────")
    print(f"  active:                  {_gb(active)}")
    print(f"  inactive:                {_gb(inactive)}")
    print(f"  max_allocated (peak):    {_gb(max_alloc)}")
    print(f"  max_reserved  (peak):    {_gb(max_resv)}")
    print(f"{sep}\n")

    return stats


def reset_peak_stats(device: int = 0):
    """Reset peak memory stats. Call after model init to start fresh."""
    _check_available()
    mod = _BACKEND_MODULE
    mod.reset_peak_memory_stats(device)
    mod.reset_accumulated_memory_stats(device)
    mod.reset_max_memory_allocated(device)
    mod.reset_max_memory_cached(device)


# ═══════════════════════════════════════════════════════════════════
# Step 2: Memory Snapshot (Allocation Trace)
# ═══════════════════════════════════════════════════════════════════

class MemorySnapshot:
    """
    Context manager for memory allocation tracing.

    Usage:
        with MemorySnapshot(output_dir="./mem_snapshots", tag="sp1_step2"):
            loss = model(**batch).loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
        # Saves snapshot_{tag}.pkl + snapshot_{tag}.html

    Or manual:
        snap = MemorySnapshot(tag="step3")
        snap.start()
        # ... training ...
        snap.stop()
        snap.save()
    """

    def __init__(self, output_dir: str = "./mem_snapshots", tag: str = "snapshot"):
        self.output_dir = output_dir
        self.tag = tag
        self.snapshot = None
        self._entered = False

    def start(self):
        """Enable memory history recording."""
        _check_available()
        mod = _BACKEND_MODULE
        mod.empty_cache()
        mod.reset_peak_memory_stats()
        try:
            # Both torch.npu and torch.cuda use the same _record_memory_history API
            # (PyTorch 2.6+ unified memory tracing)
            mod.memory._record_memory_history()
        except Exception as e:
            print(f"[Snapshot] WARNING: _record_memory_history failed: {e}")
        self._entered = True

    def stop(self):
        """Capture snapshot and disable recording."""
        _check_available()
        mod = _BACKEND_MODULE
        try:
            self.snapshot = mod.memory._snapshot()
        except Exception as e:
            print(f"[Snapshot] WARNING: _snapshot() failed: {e}")
            self.snapshot = None
        try:
            mod.memory._record_memory_history(None)
        except Exception:
            pass
        self._entered = False

    def save(self):
        """Save the captured snapshot to disk."""
        os.makedirs(self.output_dir, exist_ok=True)
        if self.snapshot is None:
            print(f"[Snapshot] No snapshot data to save for tag='{self.tag}'")
            return

        pkl_path = os.path.join(self.output_dir, f"snapshot_{self.tag}.pkl")
        with open(pkl_path, "wb") as f:
            pickle.dump(self.snapshot, f)
        print(f"[Snapshot] Saved to {pkl_path}")

        # Try to generate HTML visualization
        try:
            html = self._render_html()
            html_path = os.path.join(self.output_dir, f"snapshot_{self.tag}.html")
            with open(html_path, "w") as f:
                f.write(html)
            print(f"[Snapshot] HTML viz saved to {html_path}")
        except Exception as e:
            print(f"[Snapshot] HTML viz generation failed (non-critical): {e}")

    def _render_html(self) -> str:
        """Try to render snapshot as HTML."""
        if self.snapshot is None:
            return "<html><body>No snapshot data</body></html>"
        try:
            # Try backend-specific viz first
            mod = _BACKEND_MODULE
            try:
                from torch.npu._memory_viz import profile_plot
                return profile_plot(self.snapshot)
            except ImportError:
                pass
            try:
                from torch.cuda._memory_viz import profile_plot
                return profile_plot(self.snapshot)
            except ImportError:
                pass
        except Exception:
            pass

        return (f"<html><body><p>Snapshot saved to {self.output_dir}/snapshot_{self.tag}.pkl. "
                f"Use PyTorch Memory Visualizer to inspect.</p></body></html>")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        self.save()
        return False


# ═══════════════════════════════════════════════════════════════════
# Quick Test
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    backend, mod = _get_backend()
    if backend is None:
        print("[mem_profiler] No NPU or CUDA backend available. Running in dry-run mode.")
        print("  Functions will raise RuntimeError if called without a backend.")
    else:
        print(f"[mem_profiler] Backend: {backend}")
        print_memory_breakdown("quick-test")
