import urllib.request
import subprocess
import concurrent.futures
import os
import zipfile
import json
import sys

def main():
    token = subprocess.check_output(['gh', 'auth', 'token']).decode().strip()
    
    # 1. Get latest workflow run artifact
    repo = '10n01/Materialious'
    artifacts_url = f'https://api.github.com/repos/{repo}/actions/artifacts?per_page=1'
    req = urllib.request.Request(artifacts_url, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json'
    })
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    
    if not data.get('artifacts'):
        print("No artifacts found!")
        sys.exit(1)
        
    latest_art = data['artifacts'][0]
    art_id = latest_art['id']
    art_name = latest_art['name']
    print(f"Latest Artifact: {art_name} (ID: {art_id}, size: {latest_art['size_in_bytes'] / (1024*1024):.2f} MB)")

    # 2. Get pre-signed download URL (handling 302 redirect)
    dl_url = f'https://api.github.com/repos/{repo}/actions/artifacts/{art_id}/zip'
    req = urllib.request.Request(dl_url, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json'
    })

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(req)
        blob_url = None
    except urllib.error.HTTPError as e:
        blob_url = e.headers.get('Location')

    if not blob_url:
        print("Failed to get blob url")
        sys.exit(1)

    print("Resolved Azure Blob URL.")
    
    head_req = urllib.request.Request(blob_url, method='HEAD')
    with urllib.request.urlopen(head_req) as resp:
        total_size = int(resp.headers['Content-Length'])

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, 'release_apks')
    out_zip = os.path.join(out_dir, 'fast_tv.zip')
    os.makedirs(out_dir, exist_ok=True)
    
    with open(out_zip, 'wb') as f:
        f.seek(total_size - 1)
        f.write(b'\0')

    num_threads = 16
    chunk_size = (total_size + num_threads - 1) // num_threads

    def download_part(idx, start, end):
        r = urllib.request.Request(blob_url, headers={'Range': f'bytes={start}-{end}'})
        with urllib.request.urlopen(r) as resp:
            data = resp.read()
            with open(out_zip, 'r+b') as f:
                f.seek(start)
                f.write(data)
        print(f"Part {idx+1}/{num_threads} completed ({len(data)} bytes)", flush=True)

    print(f"Downloading with {num_threads} parallel threads...")
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i in range(num_threads):
            start = i * chunk_size
            end = min(total_size - 1, (i + 1) * chunk_size - 1)
            if start <= end:
                futures.append(executor.submit(download_part, i, start, end))
        concurrent.futures.wait(futures)

    print("Download completed! Extracting APK...", flush=True)
    with zipfile.ZipFile(out_zip, 'r') as z:
        z.extractall(out_dir)
    print("Extracted successfully!", flush=True)
    if os.path.exists(out_zip):
        os.remove(out_zip)
    for f in os.listdir(out_dir):
        if f.endswith('.apk'):
            print(f"Found APK: {f} ({os.path.getsize(os.path.join(out_dir, f))} bytes)", flush=True)

if __name__ == '__main__':
    main()
