"""
GPU detection and device management.
All ML models use get_device() to pick GPU or CPU gracefully.
"""
_device = None

def get_device():
    global _device
    if _device is not None:
        return _device
    try:
        import torch
        if torch.cuda.is_available():
            # Quick smoke test to confirm kernels actually work
            torch.tensor([1.0]).cuda()
            _device = 'cuda'
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024**2)
            print(f"🖥️  GPU detected: {gpu_name} ({vram}MB VRAM) — using CUDA", flush=True)
        else:
            _device = 'cpu'
            print("💻 No GPU available — using CPU (ML models will be slower)", flush=True)
    except Exception:
        _device = 'cpu'
    return _device


def gpu_available():
    return get_device() == 'cuda'


def vram_mb():
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory // (1024**2)
    except Exception:
        pass
    return 0
