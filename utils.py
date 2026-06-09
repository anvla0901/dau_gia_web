ADMIN_UPGRADE_CODE = "HUMG2024"


def fmt_price(amount):
    if amount is None:
        return "—"
    return f"{int(amount):,}đ".replace(",", ".")


def fmt_status(status):
    mapping = {
        "pending":   "Chờ duyệt",
        "active":    "Đang đấu giá",
        "completed": "Đã hoàn thành",
        "rejected":  "Đã từ chối",
        "failed":    "Không có người mua",
    }
    return mapping.get(status, status)
