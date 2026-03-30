import libtorrent as lt
import time

print(f"libtorrent 版本: {lt.version}")

# 最简单的 session，不加任何多余设置
ses = lt.session()
ses.apply_settings({
    "listen_interfaces": "0.0.0.0:6881",
    "enable_dht": True,
})

# 加 bootstrap 节点
nodes = [
    ("67.215.246.10",   6881),
    ("82.221.103.244",  6881),
    ("87.98.162.88",    6881),
    ("95.211.198.146",  25401),
]
for host, port in nodes:
    ses.add_dht_node((host, port))

print("等待 DHT 建立连接，每5秒打印一次...")
for i in range(12):
    time.sleep(5)
    s = ses.status()
    print(
        f"[{(i+1)*5}s] "
        f"DHT节点={s.dht_nodes} "
        f"监听端口={ses.listen_port()} "
        f"DHT上传={s.dht_upload_rate}B/s "
        f"DHT下载={s.dht_download_rate}B/s"
    )
    if s.dht_nodes > 0:
        print("✅ DHT 正常！")
        break
