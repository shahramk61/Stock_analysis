import torch
def _gpu_device():
    if torch.cuda.is_available():
        try:
            torch.tensor([1.0]).cuda()
            return 'cuda'
        except Exception:
            pass
    return 'cpu'