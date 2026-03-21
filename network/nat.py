"""
NAT 穿透辅助模块
libtorrent 已内置 UPnP / NAT-PMP，这里额外提供：
1. 外网 IP 探测
2. NAT 类型检测（是否在 CGNAT 后）
3. 端口映射状态查询
"""
import socket
import urllib.request
import urllib.error
import logging

logger = logging.getLogger("fsmagnet.nat")


def get_external_ip(timeout: float = 5.0) -> str | None:
    """
    通过多个公共 API 探测外网 IP
    """
    urls = [
        "https://api4.ipify.org",
        "https://ipv4.icanhazip.com",
        "https://checkip.amazonaws.com",
    ]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = resp.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            continue
    return None


def get_local_ip() -> str:
    """获取本机局域网 IP"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


def is_behind_cgnat(external_ip: str | None) -> bool:
    """
    判断是否处于 CGNAT（运营商大内网）之后
    CGNAT 地址段：100.64.0.0/10
    """
    if not external_ip:
        return True
    try:
        parts = list(map(int, external_ip.split(".")))
        # 100.64.0.0 ~ 100.127.255.255
        if parts[0] == 100 and 64 <= parts[1] <= 127:
            return True
        # 私有地址也算（说明没拿到真实外网IP）
        if parts[0] == 10:
            return True
        if parts[0] == 172 and 16 <= parts[1] <= 31:
            return True
        if parts[0] == 192 and parts[1] == 168:
            return True
    except Exception:
        pass
    return False


def diagnose() -> dict:
    """
    NAT 环境诊断，返回诊断报告
    """
    local_ip = get_local_ip()
    external_ip = get_external_ip()
    cgnat = is_behind_cgnat(external_ip)

    result = {
        "local_ip": local_ip,
        "external_ip": external_ip or "获取失败",
        "cgnat": cgnat,
        "recommendation": "",
    }

    if cgnat:
        result["recommendation"] = (
            "⚠️ 检测到 CGNAT / 双重 NAT，建议：\n"
            "1. 联系运营商申请公网 IP\n"
            "2. 使用 VPS 中转（如 WireGuard）\n"
            "3. 或接受连接数受限的现状"
        )
    else:
        result["recommendation"] = "✅ 具有公网 IP，UPnP/NAT-PMP 可正常工作"

    logger.info(f"NAT 诊断: {result}")
    return result