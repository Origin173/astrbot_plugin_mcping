import json
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import StarTools

STORE_FILE = "servers.json"


class ServerStore:
    """按群隔离的 MC 服务器列表存储，每台服务器可附带自定义名称。"""

    def __init__(self, plugin_name: str):
        self._path = StarTools.get_data_dir(plugin_name) / STORE_FILE
        self._groups: dict[str, list[dict]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            self._groups = {}
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            groups = data.get("groups", {})
            self._groups = {}
            for group_id, servers in groups.items():
                if not isinstance(servers, list):
                    continue
                migrated: list[dict] = []
                for entry in servers:
                    if isinstance(entry, str):
                        # 兼容旧格式：纯字符串地址 → {address, name}
                        migrated.append({"address": entry, "name": ""})
                    elif isinstance(entry, dict):
                        migrated.append(entry)
                if migrated:
                    self._groups[str(group_id)] = migrated
        except Exception as e:
            logger.warning(f"读取服务器列表失败，将使用空列表：{e}")
            self._groups = {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"groups": self._groups}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_scope_key(self, group_id: str, unified_msg_origin: str) -> str:
        return group_id if group_id else unified_msg_origin

    def list_servers(self, scope_key: str) -> list[dict]:
        """返回 [{"address": ..., "name": ...}, ...]"""
        return list(self._groups.get(scope_key, []))

    def add_server(
        self, scope_key: str, address: str, name: str = ""
    ) -> tuple[bool, str]:
        address = address.strip()
        if not address:
            return False, "服务器地址不能为空"

        servers = self._groups.setdefault(scope_key, [])
        normalized = address.casefold()
        if any(s["address"].casefold() == normalized for s in servers):
            return False, f"服务器 {address} 已在列表中"

        servers.append({"address": address, "name": name.strip()})
        self._save()
        label = f"{name}（{address}）" if name.strip() else address
        return True, f"已添加服务器：{label}"

    def remove_server(self, scope_key: str, address: str) -> tuple[bool, str]:
        address = address.strip()
        if not address:
            return False, "请提供要删除的服务器地址"

        servers = self._groups.get(scope_key, [])
        normalized = address.casefold()
        for index, entry in enumerate(servers):
            if entry["address"].casefold() == normalized:
                removed = servers.pop(index)
                if not servers:
                    self._groups.pop(scope_key, None)
                self._save()
                label = (
                    f'{removed["name"]}（{removed["address"]}）'
                    if removed["name"]
                    else removed["address"]
                )
                return True, f"已删除服务器：{label}"

        return False, f"未找到服务器：{address}"
