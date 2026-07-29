from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
DRIVE_CLIENT_PATH = ROOT / "plugins" / "google-drive" / "drive_client.py"
spec = importlib.util.spec_from_file_location("google_drive_pagination_client", DRIVE_CLIENT_PATH)
drive_client = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(drive_client)


class FakeResponse:
    def __init__(self, payload, content=b"file-bytes"):
        self.payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, handler):
        self.handler = handler
        self.calls = []
        self.post_calls = []

    def get(self, url, params=None):
        params = dict(params or {})
        self.calls.append((url, params))
        return FakeResponse(self.handler(url, params))

    def post(self, url, params=None, **kwargs):
        params = dict(params or {})
        self.post_calls.append((url, params, kwargs))
        return FakeResponse({"id": "uploaded", "name": "asset.png"})

    def close(self):
        return None


def make_client(handler):
    client = drive_client.DriveClient("token")
    client._client.close()
    client._client = FakeHttpClient(handler)
    return client


def test_list_children_collects_pages_and_preserves_shared_drive_flags():
    def handler(_url, params):
        if params.get("pageToken") == "next":
            return {"files": [{"id": "b", "name": "B"}]}
        return {"files": [{"id": "a", "name": "A"}], "nextPageToken": "next"}

    client = make_client(handler)
    files = client.list_children("folder", all_drives=True)

    assert [item["id"] for item in files] == ["a", "b"]
    assert len(client._client.calls) == 2
    assert client._client.calls[0][1]["supportsAllDrives"] == "true"
    assert client._client.calls[1][1]["includeItemsFromAllDrives"] == "true"
    assert client._client.calls[1][1]["pageToken"] == "next"


def test_recursive_search_collects_every_query_page_and_walks_child_folders():
    def handler(_url, params):
        query = params.get("q", "")
        token = params.get("pageToken")
        if "mimeType = 'application/vnd.google-apps.folder'" in query:
            if "'root' in parents" in query:
                return {"files": [{"id": "child", "name": "Child", "mimeType": "application/vnd.google-apps.folder"}]}
            return {"files": []}
        if "'root' in parents" in query:
            if token == "image-next":
                return {"files": [{"id": "root-2", "name": "root-2.png"}]}
            return {"files": [{"id": "root-1", "name": "root-1.png"}], "nextPageToken": "image-next"}
        if "'child' in parents" in query:
            return {"files": [{"id": "child-1", "name": "child-1.png"}]}
        return {"files": []}

    client = make_client(handler)
    files = client.search_files(["image/png"], parent_id="root")

    assert [item["id"] for item in files] == ["root-1", "root-2", "child-1"]
    image_page_calls = [params for _url, params in client._client.calls if params.get("pageToken") == "image-next"]
    assert len(image_page_calls) == 1


def test_shared_drive_metadata_download_export_create_and_upload_send_support_flags():
    client = make_client(lambda _url, _params: {"id": "shared-file", "name": "Asset"})

    assert client.get_file_meta("shared-file")["id"] == "shared-file"
    assert client.download_file("shared-file") == b"file-bytes"
    assert client.export_file("shared-file") == b"file-bytes"
    client.ensure_folder("Generated", "shared-parent")
    client.upload_file("asset.png", b"data", "image/png", "shared-parent")

    assert client._client.calls[0][1]["supportsAllDrives"] == "true"
    assert client._client.calls[1][1]["supportsAllDrives"] == "true"
    assert client._client.calls[2][1]["supportsAllDrives"] == "true"
    assert client._client.calls[3][1]["supportsAllDrives"] == "true"
    assert client._client.calls[3][1]["includeItemsFromAllDrives"] == "true"
    assert client._client.post_calls[0][1]["supportsAllDrives"] == "true"
    assert client._client.post_calls[1][1]["supportsAllDrives"] == "true"


def test_operational_and_compatibility_drive_clients_stay_in_sync():
    compat_path = ROOT / "api" / "plugins" / "google-drive" / "drive_client.py"
    assert DRIVE_CLIENT_PATH.read_bytes() == compat_path.read_bytes()


def test_shared_with_me_and_shared_drives_collect_all_pages():
    def handler(url, params):
        if url.endswith("/drives"):
            if params.get("pageToken") == "drive-next":
                return {"drives": [{"id": "d2", "name": "Drive 2"}]}
            return {"drives": [{"id": "d1", "name": "Drive 1"}], "nextPageToken": "drive-next"}
        if params.get("pageToken") == "shared-next":
            return {"files": [{"id": "s2", "name": "Shared 2"}]}
        return {"files": [{"id": "s1", "name": "Shared 1"}], "nextPageToken": "shared-next"}

    client = make_client(handler)

    assert [item["id"] for item in client.list_shared_with_me_folders()] == ["s1", "s2"]
    assert [item["id"] for item in client.list_shared_drives()] == ["d1", "d2"]
