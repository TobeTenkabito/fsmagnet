"""
协议加密配置（MSE/PE - Message Stream Encryption）
libtorrent 已内置，这里封装为统一接口
"""
import libtorrent as lt


def get_encryption_settings(force: bool = True) -> dict:
    """
    返回 libtorrent 加密相关设置字典

    force=True  → 强制加密，拒绝明文连接（最大程度绕过 ISP DPI）
    force=False → 优先加密，允许回退明文（兼容性更好）
    """
    if force:
        return {
            "out_enc_policy": lt.enc_policy.forced,
            "in_enc_policy":  lt.enc_policy.forced,
            "allowed_enc_level": lt.enc_level.both,   # RC4 + plaintext header
        }
    else:
        return {
            "out_enc_policy": lt.enc_policy.enabled,
            "in_enc_policy":  lt.enc_policy.enabled,
            "allowed_enc_level": lt.enc_level.both,
        }


def get_encryption_description(force: bool = True) -> str:
    if force:
        return "MSE/PE 强制加密（RC4，拒绝明文）"
    return "MSE/PE 优先加密（允许明文回退）"
