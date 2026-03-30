import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)
try:
    # 向 Google DNS 发一个 UDP 包
    sock.sendto(b"\x00" * 16, ("8.8.8.8", 53))
    print("✅ UDP 发包成功")
except Exception as e:
    print(f"❌ UDP 发包失败: {e}")
finally:
    sock.close()
