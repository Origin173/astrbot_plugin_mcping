import astrbot.core.message.components as Comp
from astrbot.api.event import filter
from astrbot.api.star import Context, Star
from astrbot.core.platform import AstrMessageEvent

from astrbot.api import logger

from .data_source import query_server_status
from .server_store import ServerStore

PLUGIN_NAME = "astrbot_plugin_mcping"


class MCPingPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.store = ServerStore(PLUGIN_NAME)

    def _get_scope_key(self, event: AstrMessageEvent) -> str:
        return self.store.get_scope_key(
            event.get_group_id(), event.unified_msg_origin
        )

    @staticmethod
    def _is_group_admin(event: AstrMessageEvent) -> bool:
        """检查发送者是否为群管理员或群主。

        兼容 OneBot v11（sender.role）与 QQ 官方（member.roles）等平台。
        """
        # AstrBot 系统管理员始终放行
        try:
            if event.is_admin():
                return True
        except Exception:
            pass

        try:
            raw = event.message_obj.raw_message

            # 路径1: OneBot v11 — sender.role
            sender = getattr(raw, "sender", None)
            if sender is not None:
                role = (
                    sender.get("role", "")
                    if isinstance(sender, dict)
                    else getattr(sender, "role", "")
                )
                if role in ("owner", "admin"):
                    return True

            # 路径2: QQ 官方 / 其他平台 — member.roles（list）
            member = getattr(raw, "member", None)
            if member is not None:
                roles: list = (
                    member.get("roles", [])
                    if isinstance(member, dict)
                    else getattr(member, "roles", [])
                )
                if isinstance(roles, list):
                    for r in roles:
                        rl = str(r).lower()
                        # QQ 官方角色：群主/管理员 或 role_id 4/3
                        if rl in ("owner", "admin", "群主", "管理员", "4", "3"):
                            return True

            # 路径3: raw 本身是 dict
            if isinstance(raw, dict):
                s = raw.get("sender", {})
                if isinstance(s, dict) and s.get("role", "") in ("owner", "admin"):
                    return True
                m = raw.get("member", {})
                if isinstance(m, dict):
                    for r in m.get("roles", []):
                        if str(r).lower() in ("owner", "admin", "群主", "管理员", "4", "3"):
                            return True
        except Exception:
            return False

        return False

    @staticmethod
    def _parse_input(raw: str) -> tuple[str, str]:
        """从原始输入中分离 地址 与 名称。"""
        raw = raw.strip()
        if " " in raw:
            addr, _, name = raw.partition(" ")
            return addr.strip(), name.strip()
        return raw, ""

    def _parse_command_args(
        self, event: AstrMessageEvent, command: str
    ) -> tuple[str, str]:
        """从原始消息中提取命令参数，解决 AstrBot 只传首词的问题。

        /addsvr gxucraft.cn 生存服  → ("gxucraft.cn", "生存服")
        """
        text = event.message_str.strip()
        # 去除指令前缀和命令名
        for prefix in ("/", "。"):
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        if text.lower().startswith(command.lower()):
            text = text[len(command):].strip()
        return self._parse_input(text)

    @filter.command("mcp", alias={"mcping", "MCP"}, desc="获取 Minecraft JE/BE 服务器 Motd 图片信息")
    async def on_command(self, event: AstrMessageEvent, server_ip: str | None = None):
        if not server_ip:
            yield event.plain_result("未提供服务器IP/域名")
            return
        address, name = self._parse_command_args(event, "mcp") or self._parse_input(server_ip)
        status_img = await query_server_status(address, server_name=name)
        if status_img:
            yield event.chain_result([Comp.Image.fromBytes(status_img)])
        else:
            yield event.plain_result("查询失败")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("addsvr", desc="添加本群 MC 服务器（仅群管理员）")
    async def addsvr(self, event: AstrMessageEvent, server_ip: str | None = None):
        if not self._is_group_admin(event):
            yield event.plain_result("仅群管理员可添加服务器")
            return
        if not server_ip:
            yield event.plain_result(
                "用法：/addsvr <服务器地址> [名称]\n"
                "例如：/addsvr gxucraft.cn 生存服"
            )
            return

        address, name = self._parse_command_args(event, "addsvr")
        logger.info(f"addsvr parsed: address={address}, name={name}")
        ok, message = self.store.add_server(
            self._get_scope_key(event), address, name
        )
        yield event.plain_result(message)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.command("delsvr", desc="删除本群 MC 服务器（仅群管理员）")
    async def delsvr(self, event: AstrMessageEvent, server_ip: str | None = None):
        if not self._is_group_admin(event):
            yield event.plain_result("仅群管理员可删除服务器")
            return
        if not server_ip:
            yield event.plain_result("用法：/delsvr <服务器地址>\n例如：/delsvr gxucraft.cn")
            return

        ok, message = self.store.remove_server(self._get_scope_key(event), server_ip)
        yield event.plain_result(message)

    @filter.command("status", desc="查询本群已添加的 MC 服务器状态")
    async def status(self, event: AstrMessageEvent, server_ip: str | None = None):
        scope_key = self._get_scope_key(event)
        servers = self.store.list_servers(scope_key)

        if server_ip:
            address, name = self._parse_command_args(event, "status") or self._parse_input(server_ip)
            targets = [{"address": address, "name": name}]
        elif not event.get_group_id():
            yield event.plain_result("私聊中请使用 /status <服务器地址> 查询指定服务器。")
            return
        elif servers:
            targets = servers
        else:
            yield event.plain_result(
                "当前群聊尚未添加服务器。\n"
                "群管理员可使用 /addsvr <地址> [名称] 添加服务器。"
            )
            return

        failed: list[str] = []
        sent = False
        for entry in targets:
            address = entry["address"]
            name = entry.get("name", "")
            logger.info(f"querying server: address={address}, name={name}")
            status_img = await query_server_status(address, server_name=name)
            if status_img:
                sent = True
                yield event.chain_result([Comp.Image.fromBytes(status_img)])
            else:
                failed.append(name or address)

        if failed:
            yield event.plain_result("以下服务器查询失败：\n" + "\n".join(failed))
        elif not sent:
            yield event.plain_result("查询失败")
