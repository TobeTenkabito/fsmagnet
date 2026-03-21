"""
探测本机硬件配置，用于动态计算最优参数
"""
import os
import shutil
import psutil
import platform


class SystemProbe:
    def __init__(self):
        self.cpu_count = psutil.cpu_count(logical=True)
        self.cpu_physical = psutil.cpu_count(logical=False) or 1
        mem = psutil.virtual_memory()
        self.total_ram_gb = mem.total / (1024 ** 3)
        self.free_ram_gb = mem.available / (1024 ** 3)
        self.is_windows = platform.system() == "Windows"
        self.is_linux = platform.system() == "Linux"

    def optimal_connections(self) -> int:
        """
        根据 CPU 核数和 RAM 计算最优连接数
        经验公式：min(cpu*150, ram_gb*80, 2000)
        """
        by_cpu = self.cpu_count * 150
        by_ram = int(self.total_ram_gb * 80)
        return max(100, min(by_cpu, by_ram, 2000))

    def optimal_cache_size_blocks(self) -> int:
        """
        计算 libtorrent cache_size（单位：16KB块）
        取空闲内存的 25%，最小 256MB，最大 4GB
        """
        target_bytes = min(
            max(256 * 1024 * 1024, int(self.free_ram_gb * 0.25 * 1024 ** 3)),
            4 * 1024 ** 3,
        )
        return target_bytes // (16 * 1024)

    def optimal_cache_mb(self) -> int:
        return self.optimal_cache_size_blocks() * 16 // 1024

    def disk_is_ssd(self, path: str = ".") -> bool:
        """
        简单判断目标路径是否在 SSD 上
        Windows: 用 PowerShell 查询；Linux: 读 /sys/block
        """
        try:
            if self.is_linux:
                partition = self._get_partition(path)
                dev = os.path.basename(partition)
                # 去掉分区号
                dev = dev.rstrip("0123456789")
                rotational = f"/sys/block/{dev}/queue/rotational"
                if os.path.exists(rotational):
                    with open(rotational) as f:
                        return f.read().strip() == "0"
        except Exception:
            pass
        return True  # 默认当 SSD 处理（激进策略）

    def _get_partition(self, path: str) -> str:
        path = os.path.abspath(path)
        best = ""
        for part in psutil.disk_partitions():
            if path.startswith(part.mountpoint) and len(part.mountpoint) > len(best):
                best = part.device
        return best

    def summary(self) -> dict:
        return {
            "cpu_count": self.cpu_count,
            "cpu_physical": self.cpu_physical,
            "total_ram_gb": round(self.total_ram_gb, 1),
            "free_ram_gb": round(self.free_ram_gb, 1),
            "optimal_connections": self.optimal_connections(),
            "optimal_cache_mb": self.optimal_cache_mb(),
            "disk_is_ssd": self.disk_is_ssd(),
            "platform": platform.system(),
        }


# 全局单例
probe = SystemProbe()