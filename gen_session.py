#!/usr/bin/env python3
"""ساخت SESSION_STRING برای Pyrofork
اجرا:  API_ID=... API_HASH=... python gen_session.py
"""
import asyncio, os
from pyrogram import Client


async def main():
    async with Client("gen", api_id=int(os.environ["API_ID"]),
                      api_hash=os.environ["API_HASH"], in_memory=True) as app:
        print("\nSESSION_STRING:\n" + await app.export_session_string())


asyncio.run(main())
