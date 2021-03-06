#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#   Author  :   cold
#   E-mail  :   wh_linux@126.com
#   Date    :   14/04/21 09:43:21
#   Desc    :   命令解析
#
import re
import logging
import inspect

from twqq.objects import UniqueIds

logger = logging.getLogger("magpie")


def register(command, replace=None):
    """ 将函数注册为命令

    :param command: 命令正则匹配模式
    :param replace: 替代命令
    """
    def wrapper(func):
        func._command = command
        func._replace = replace
        return func
    return wrapper


class Command(object):

    def __init__(self, xmpp_client, qq_client):
        self.xmpp_client = xmpp_client
        self.qq_client = qq_client
        self._command_map = {}
        self._load_commands()

    def _load_commands(self):
        for _, handler in inspect.getmembers(self, callable):
            if not hasattr(handler, "_command"):
                continue

            self._command_map[handler._command] = (
                re.compile(handler._command, flags=re.M | re.S),
                handler, handler._replace
            )

    def parse(self, command):
        for pattern, handler, _ in self._command_map.values():
            sre = pattern.match(command)
            if sre:
                handler(*sre.groups(), **sre.groupdict())
                return True

    @register(r'-help')
    def help_info(self):
        """ 显示帮助信息
        """
        info = [u"命令列表"]
        for command, (_, handler, replace) in self._command_map.items():
            command = command if replace is None else replace
            doc = handler.__doc__.decode("utf-8") if handler.__doc__ else u""
            info.append(u"{0}    {1}".format(command, doc.strip()))

        self.xmpp_client.send_control_msg("\n".join(info))

    @register("-list")
    def list_online_friends(self):
        """ 获取在线好友
        """
        friends = self.qq_client.hub.get_friends()
        cate_map = {}
        for cate in friends.categories:
            cate_map[cate.index] = {"name": cate.name, "sort":  cate.sort,
                                        "list": []}
        logger.info(u"分组信息: {0!r}".format(cate_map))

        for item in friends.info:
            if item.status in ["online", "away"]:
                try:
                    cate_map[item.categories]["list"].append(item)
                except KeyError:
                    logger.info(u"{0} 分组错误: {1!r}".format(item.nick, cate_map),
                                exc_info=True)

        lst = [(x.get("sort"), x.get("name"), x.get("list"))
               for x in cate_map.values()]

        lst = sorted(lst, key=lambda x: x[0])
        info = [u"在线好友列表"]
        for _, name, _list in lst:
            info.append(u"== {0} ==".format(name))
            for item in _list:
                if item.markname:
                    nick = u"{0}({1})".format(item.markname, item.nick)
                else:
                    nick = item.nick

                info.append(u"({1}){0}[{2}]".format(nick, item._id,
                                                    item.status))

        self.xmpp_client.send_control_msg("\n".join(info))

    @register("-glist")
    def list_groups(self):
        """ 获取群列表
        """
        info = [u"群列表"]
        groups = self.qq_client.hub.get_groups()
        if groups:
            for item in groups.groups:
                info.append(u"({0}) {1}".format(item._id, item.name))
        self.xmpp_client.send_control_msg("\n".join(info))

    @register("-dlist")
    def list_discu(self):
        """ 获取讨论组列表
        """
        info = [u"讨论组列表"]
        discu = self.qq_client.hub.get_discu()
        if discu:
            for item in discu.discus:
                info.append(u"({0}) {1}".format(item._id, item.name))
        self.xmpp_client.send_control_msg("\n".join(info))

    @register(r'^#(\d+)(.*)', "#id content")
    def send_at_message(self, _id, content):
        """ 给id发送消息, id 是对象的唯一id, content 是发送的内容
        """
        self.qq_client.send_message_with_aid(_id, content)

    @register(r"-qn (\d+)", "-qn id")
    def get_qq_account(self, _id):
        """ 获取QQ号码/群号码
        """
        uin, _type = UniqueIds.get(int(_id))

        if _type == UniqueIds.T_FRI:
            tys = u"QQ号码"
            friends = self.qq_client.hub.get_friends()
            name = friends.get_show_name(uin)
        elif _type == UniqueIds.T_GRP:
            tys = u"群号"
            groups = self.qq_client.hub.get_groups()
            name = groups.get_group_name(uin)
        else:
            self.xmpp_client.send_control_msg(u"{0} 不是群或者好友".format(_id))
            return

        account = self.qq_client.hub.get_account(uin, _type)
        if account:
            msg = u"{0} 的{2}是 {1}".format(name, account, tys)
        else:
            msg = u"获取{0}的{1}失败".format(name, tys)
        self.xmpp_client.send_control_msg(msg)

    @register(r'-restart')
    def restart_webqq(self):
        """ 重新登录WebQQ
        """
        self.xmpp_client.send_status(u"重新登陆...")
        self.qq_client.hub.disconnect()
        self.qq_client.hub.connect()

    @register(r'-stop')
    def stop_webqq(self):
        """ 退出WebQQ
        """
        self.xmpp_client.send_status(u"WebQQ登出")
        self.qq_client.disconnect()

    @register(r'-start')
    def start_webqq(self):
        """ 启动WebQQ
        """
        self.xmpp_client.send_status(u"WebQQ登录中")
        self.qq_client.connect()

    @register(r'-gr (\d+)', '-gr id')
    def refresh_group(self, _id):
        """ 手动刷新 id 对应群的成员信息
        """
        r, info = self.qq_client.hub.refresh_group_info(_id)
        if not r:
            self.xmpp_client.send_control_msg(u"[S] {0}".format(info))
        else:
            self.xmpp_client.send_control_msg(u"[S] 刷新 {0} 成员信息"
                                              .format(info))

    @register(r'-fr')
    def refresh_friend_info(self):
        self.qq_client.hub.refresh_friend_info()
        self.xmpp_client.send_control_msg(u"[S] 刷新好友信息")
