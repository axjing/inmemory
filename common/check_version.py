import torch
import torchaudio
# import torchcodec
# import onnxruntime as ort
# print("可用执行提供器：", ort.get_available_providers())
# 输出包含 ['CUDAExecutionProvider', 'CPUExecutionProvider'] 则成功
# 检查PyTorch版本
print(f"PyTorch版本：{torch.__version__}")
print(f"CUDA是否可用：{torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"CUDA版本：{torch.version.cuda}")
    print(f"CUDA架构：{torch.cuda.get_arch_list()}")
    print(f"CUDA当前设备：{torch.cuda.current_device()}")
    print(f"CUDA设备名称：{torch.cuda.get_device_name(torch.cuda.current_device())}")
    print(f"CUDA设备数量：{torch.cuda.device_count()}")
    print(f"CUDA内存占用：{torch.cuda.memory_allocated() / 1024 ** 3:.2f} GB")
    print(f"CUDA内存缓存：{torch.cuda.memory_reserved() / 1024 ** 3:.2f} GB")
    print(f"CUDA最大内存分配：{torch.cuda.max_memory_allocated() / 1024 ** 3:.2f} GB")
    print(f"CUDA最大内存缓存：{torch.cuda.max_memory_reserved() / 1024 ** 3:.2f} GB")


# # 检查TorchCodec版本
# print(f"TorchCodec版本：{torchcodec.__version__}")
# print(f"TorchCodec是否可用：{torchcodec.is_available()}")

# # 检查torchaudio后端
# torchaudio.set_audio_backend("torchcodec")
# print(f"当前音频后端：{torchaudio.get_audio_backend()}")

# # # 测试加载音频（替换为你的WAV路径）
# # wav_path = "你的测试音频.wav"
# speech, sr = torchaudio.load(wav_path)
# print(f"音频加载成功！形状：{speech.shape}，采样率：{sr}")