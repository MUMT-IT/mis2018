"""Compatibility shim for optional linebot-sdk dependency.

The legacy app imports linebot classes from several blueprints during app
startup. In environments where the SDK is not installed, we still want the
application to import cleanly so unrelated modules can load.
"""
from __future__ import annotations

try:  # pragma: no cover - exercised only when the real dependency exists
    from linebot import LineBotApi, WebhookHandler
    from linebot.exceptions import InvalidSignatureError, LineBotApiError
    from linebot.models import (
        MessageEvent,
        TextMessage,
        TextSendMessage,
        BubbleContainer,
        BoxComponent,
        TextComponent,
        FlexSendMessage,
        CarouselContainer,
        FillerComponent,
        ButtonComponent,
        URIAction,
        MessageAction,
        ImagemapSendMessage,
        BaseSize,
        MessageImagemapAction,
        ImagemapArea,
        URIImagemapAction,
        ImageComponent,
    )
except Exception:  # pragma: no cover - fallback for local/dev environments
    class _LinebotPlaceholder:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs


    class LineBotApi(_LinebotPlaceholder):
        def reply_message(self, *args, **kwargs):
            raise RuntimeError('linebot-sdk is not installed')

        def push_message(self, *args, **kwargs):
            raise RuntimeError('linebot-sdk is not installed')


    class WebhookHandler(_LinebotPlaceholder):
        def add(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def handle(self, *args, **kwargs):
            raise RuntimeError('linebot-sdk is not installed')


    class LineBotApiError(Exception):
        pass


    class InvalidSignatureError(Exception):
        pass


    class MessageEvent(_LinebotPlaceholder):
        pass


    class TextMessage(_LinebotPlaceholder):
        pass


    class TextSendMessage(_LinebotPlaceholder):
        pass


    class BubbleContainer(_LinebotPlaceholder):
        pass


    class BoxComponent(_LinebotPlaceholder):
        pass


    class TextComponent(_LinebotPlaceholder):
        pass


    class FlexSendMessage(_LinebotPlaceholder):
        pass


    class CarouselContainer(_LinebotPlaceholder):
        pass


    class FillerComponent(_LinebotPlaceholder):
        pass


    class ButtonComponent(_LinebotPlaceholder):
        pass


    class URIAction(_LinebotPlaceholder):
        pass


    class MessageAction(_LinebotPlaceholder):
        pass


    class ImagemapSendMessage(_LinebotPlaceholder):
        pass


    class BaseSize(_LinebotPlaceholder):
        pass


    class MessageImagemapAction(_LinebotPlaceholder):
        pass


    class ImagemapArea(_LinebotPlaceholder):
        pass


    class URIImagemapAction(_LinebotPlaceholder):
        pass


    class ImageComponent(_LinebotPlaceholder):
        pass
