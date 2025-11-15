import requests

PNJ_API = "https://edge-api.pnj.io/ecom-frontend/v1/get-gold-price?zone=11"

def fetch_pnj_table():
    resp = requests.get(PNJ_API, timeout=15)
    resp.raise_for_status()

    payload = resp.json()

    data = payload["data"]          # list các bản ghi
    branch = payload.get("chinhanh")
    updated = payload.get("updateDate")

    rows = []
    for item in data:
        tensp  = item["tensp"]
        giamua = item["giamua"]
        giaban = item["giaban"]

        rows.append((tensp, giamua, giaban))

    return rows, branch, updated

if __name__ == "__main__":
    rows, branch, updated = fetch_pnj_table()
    print("Chi nhánh:", branch, "- cập nhật:", updated)
    for name, buy, sell in rows:
        print(f"{name}: Mua {buy:,} - Bán {sell:,}")
