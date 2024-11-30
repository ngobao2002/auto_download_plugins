import requests
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import zipfile

# URL API của WordPress
API_URL = "https://api.wordpress.org/plugins/info/1.2/"
SAVE_FOLDER = "wordpress_plugins"  # Thư mục để lưu các plugin tải về
UNZIP_FOLDER = "unzipped_plugins"  # Thư mục để lưu các plugin đã giải nén
MIN_ACTIVE_INSTALLS = 1000  # Chỉ tải các plugin có số lượng active installs >= giá trị này
CSV_FILE = "plugins_info.csv"  # Tên file CSV để lưu thông tin plugin

# Số lượng luồng tối đa (tăng để tải nhanh hơn, giảm nếu mạng chậm)
MAX_WORKERS = 5


def fetch_plugins(page=1, per_page=100):
    """Lấy danh sách plugin từ API"""
    params = {
        "action": "query_plugins",
        "request[page]": page,
        "request[per_page]": per_page,
    }
    response = requests.get(API_URL, params=params)
    response.raise_for_status()  # Báo lỗi nếu request thất bại
    return response.json()


def save_plugins_to_csv(plugins):
    """Lưu thông tin plugin vào file CSV"""
    if not plugins:
        return

    # Chuyển danh sách plugin thành DataFrame
    df = pd.DataFrame(plugins)
    
    # Nếu file chưa tồn tại, tạo mới và thêm header
    if not os.path.exists(CSV_FILE):
        df.to_csv(CSV_FILE, index=False, mode="w", header=True)
    else:
        # Nếu file đã tồn tại, thêm dữ liệu mà không ghi đè header
        df.to_csv(CSV_FILE, index=False, mode="a", header=False)
    print(f"Saved {len(plugins)} plugins to {CSV_FILE}")


def download_plugin(plugin):
    """Tải plugin từ URL về thư mục local"""
    plugin_slug = plugin.get("slug")
    download_url = plugin.get("download_link")

    if not plugin_slug or not download_url:
        return f"Skipped: {plugin_slug} (No download link)"

    try:
        print(f"Downloading {plugin_slug}...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        # Đảm bảo thư mục lưu trữ tồn tại
        os.makedirs(SAVE_FOLDER, exist_ok=True)

        # Lưu file zip
        zip_path = os.path.join(SAVE_FOLDER, f"{plugin_slug}.zip")
        with open(zip_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)

        # Giải nén file zip sau khi tải về
        unzip_plugin(zip_path, plugin_slug)
        return f"Downloaded and unzipped: {plugin_slug}"
    except Exception as e:
        return f"Failed: {plugin_slug} ({e})"


def unzip_plugin(zip_path, plugin_slug):
    """Giải nén file zip vào thư mục unzipped_plugins và xóa file zip sau khi hoàn tất"""
    try:
        print(f"Unzipping {plugin_slug}...")
        os.makedirs(UNZIP_FOLDER, exist_ok=True)
        unzip_path = os.path.join(UNZIP_FOLDER, plugin_slug)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(unzip_path)

        print(f"Unzipped: {plugin_slug} to {unzip_path}")

        # Xóa file ZIP sau khi giải nén thành công
        os.remove(zip_path)
        print(f"Deleted ZIP file: {zip_path}")
    except zipfile.BadZipFile:
        print(f"Failed to unzip: {plugin_slug} (Bad zip file)")
    except Exception as e:
        print(f"Error during unzipping {plugin_slug}: {e}")


def main():
    """Hàm chính để lấy danh sách và tải plugin"""
    page = 1
    all_plugins_info = []

    while True:
        print(f"Fetching plugins from page {page}...")
        data = fetch_plugins(page=page)
        plugins = data.get("plugins", [])
        if not plugins:
            print("No more plugins found.")
            break

        # Lọc các plugin theo tiêu chí
        filtered_plugins = [
            {
                "slug": plugin.get("slug"),
                "name": plugin.get("name"),
                "active_installs": plugin.get("active_installs", 0),
                "download_link": plugin.get("download_link"),
                "version": plugin.get("version"),
                "author": plugin.get("author"),
            }
            for plugin in plugins
            if plugin.get("active_installs", 0) >= MIN_ACTIVE_INSTALLS
        ]

        # Lưu thông tin plugin vào CSV
        save_plugins_to_csv(filtered_plugins)

        # Tải plugin song song
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = executor.map(download_plugin, filtered_plugins)
            for result in results:
                print(result)

        all_plugins_info.extend(filtered_plugins)
        page += 1


if __name__ == "__main__":
    main()
